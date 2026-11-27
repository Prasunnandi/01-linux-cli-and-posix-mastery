# Day 43: Service Lifecycle Management - systemctl Internals, Signals, and Process Isolation

## 1. The Anatomy of a systemctl Invocation

When a systems administrator types `systemctl restart nginx.service`, the command does not directly manipulate the Nginx process. Instead, `systemctl` acts as a thin D-Bus client:
1. It connects to the system bus (`/var/run/dbus/system_bus_socket`) or direct systemd private socket (`/run/systemd/private`).
2. It invokes the D-Bus method `org.freedesktop.systemd1.Manager.RestartUnit("nginx.service", "replace")`.
3. PID 1 intercepts the call, validates polkit authorization rules, creates an asynchronous transaction job, and inserts it into the transaction engine.
4. PID 1 executes the unit state machine, issuing POSIX signals, monitoring cgroup state, and responding to `systemctl` once the job completes or times out (`TimeoutSec=90s`).

```
+--------------------------------------------------------------------------+
|                       systemctl EXECUTION PATH                           |
+--------------------------------------------------------------------------+
|  User Space CLI: systemctl restart nginx.service                         |
|  1. Construct D-Bus Method Call: org.freedesktop.systemd1.Manager        |
|  2. Transmit Message over AF_UNIX socket: /run/systemd/private           |
+--------------------------------------------------------------------------+
                                    |
                                    v D-Bus IPC
+--------------------------------------------------------------------------+
|                             PID 1 DAEMON                                 |
|  3. Validate Polkit Authorization (UID 0 vs non-root)                    |
|  4. Enqueue Job to Transaction Queue (JobType: JOB_RESTART)              |
|  5. Stop Phase:                                                          |
|     - Send SIGTERM to Nginx cgroup (/sys/fs/cgroup/system.slice/nginx)   |
|     - Arm TimeoutStopSec= timer                                          |
|     - Await cgroup empty notification or send SIGKILL                    |
|  6. Start Phase:                                                         |
|     - fork() + setns() + chroot() + unshare() (Namespace sandboxing)     |
|     - execve("/usr/sbin/nginx")                                          |
+--------------------------------------------------------------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: Service State Machine

A systemd service transitions through states defined in `src/core/service.h`. Below is the actual C enumeration and control struct from systemd:

```c
/* Real systemd Architecture excerpted from src/core/service.h */
typedef enum ServiceState {
    SERVICE_DEAD,
    SERVICE_CONDITION,
    SERVICE_START_PRE,
    SERVICE_START,
    SERVICE_START_POST,
    SERVICE_RUNNING,
    SERVICE_RELOAD,
    SERVICE_STOP,
    SERVICE_STOP_WATCHDOG,
    SERVICE_STOP_SIGTERM,
    SERVICE_STOP_SIGKILL,
    SERVICE_STOP_POST,
    SERVICE_FINAL_WATCHDOG,
    SERVICE_FINAL_SIGTERM,
    SERVICE_FINAL_SIGKILL,
    SERVICE_FAILED,
    SERVICE_AUTO_RESTART,
    SERVICE_CLEANING,
    _SERVICE_STATE_MAX,
    _SERVICE_STATE_INVALID = -EINVAL,
} ServiceState;

typedef enum ServiceRestart {
    SERVICE_RESTART_NO,
    SERVICE_RESTART_ON_SUCCESS,
    SERVICE_RESTART_ON_FAILURE,
    SERVICE_RESTART_ON_ABNORMAL,
    SERVICE_RESTART_ON_WATCHDOG,
    SERVICE_RESTART_ON_ABORT,
    SERVICE_RESTART_ALWAYS,
    _SERVICE_RESTART_MAX
} ServiceRestart;

struct Service {
    Unit                        meta;
    ServiceType                 type;
    ServiceState                state;
    ServiceRestart              restart;

    /* Process Identification */
    pid_t                       main_pid;
    pid_t                       control_pid;
    int                         main_pid_known:1;

    /* Timing Limits and Deadlines */
    usec_t                      timeout_start_usec;
    usec_t                      timeout_stop_usec;
    usec_t                      restart_usec;
    usec_t                      watchdog_usec;

    /* Kill Mode Configuration */
    KillMode                    kill_mode;      /* KILL_CONTROL_GROUP, KILL_PROCESS, KILL_NONE */
    int                         kill_signal;    /* Default SIGTERM */

    /* Execution Parameters */
    ExecCommand                 *exec_command[_SERVICE_EXEC_COMMAND_MAX];
    ExecContext                 exec_context;   /* Namespaces, SecComp, User, Caps */
};
```

---

## 3. Mathematical Foundations: Exponential Restart Backoff

When high-availability services experience environmental failures (e.g., DNS resolution failure or network partition), immediate restart loops cause CPU starvation and log flooding. 

systemd implements exponential backoff throttling via `RestartSec=`, governed by:
$$T_{	ext{delay}}(n) = \min\left(T_{	ext{base}} 	imes 2^{n-1}, T_{	ext{max}}ight)$$
where $n$ is the consecutive restart attempt count, $T_{	ext{base}}$ is the initial delay, and $T_{	ext{max}}$ is the ceiling.

To prevent infinite thrashing, systemd enforces the **Start Rate Limit**:
$$	ext{FailedAttempts}(\Delta t) \le 	ext{StartLimitBurst} \quad 	ext{within} \quad \Delta t = 	ext{StartLimitIntervalSec}$$

If this threshold is breached, systemd transitions the service to `SERVICE_FAILED` with the status `failed (Result: start-limit-hit)` and refuses to trigger further restarts until manual intervention (`systemctl reset-failed`) occurs.

---

## 4. Compilable C Implementation: Double-Forking Daemon with Clean SIGTERM Drain

Legacy UNIX services use `Type=forking`. The service forks twice to detach from the controlling terminal, writes its PID to a file, and terminates the intermediate parent.

Save the following program as `forking_service.c`:

```c
/*
 * forking_service.c - Classical POSIX Double-Fork Daemon
 * Demonstrates:
 * 1. Double-fork idiom to isolate from controlling tty
 * 2. Creating a new session with setsid()
 * 3. Atomic PID file writing
 * 4. Graceful SIGTERM connection draining
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread forking_service.c -o forking_service
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>

static volatile sig_atomic_t g_running = 1;

static void sigterm_handler(int sig)
{
    (void)sig;
    g_running = 0;
}

void daemonize(const char *pid_file_path)
{
    /* Step 1: First fork to background */
    pid_t pid = fork();
    if (pid < 0) exit(EXIT_FAILURE);
    if (pid > 0) exit(EXIT_SUCCESS); /* Parent exits */

    /* Step 2: Create new session and detach from controlling terminal */
    if (setsid() < 0) exit(EXIT_FAILURE);

    /* Step 3: Second fork prevents daemon from ever re-acquiring a TTY */
    pid = fork();
    if (pid < 0) exit(EXIT_FAILURE);
    if (pid > 0) exit(EXIT_SUCCESS);

    /* Step 4: Reset file mode creation mask */
    umask(0);

    /* Step 5: Change working directory to root */
    if (chdir("/") < 0) exit(EXIT_FAILURE);

    /* Step 6: Close and redirect standard file descriptors to /dev/null */
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);
    open("/dev/null", O_RDONLY);  /* stdin = 0 */
    open("/dev/null", O_RDWR);    /* stdout = 1 */
    open("/dev/null", O_RDWR);    /* stderr = 2 */

    /* Step 7: Write PID file atomically */
    int pfd = open(pid_file_path, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (pfd >= 0) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%d\n", getpid());
        write(pfd, buf, strlen(buf));
        close(pfd);
    }
}

int main(int argc, char *argv[])
{
    const char *pid_file = (argc > 1) ? argv[1] : "/tmp/my_service.pid";

    struct sigaction sa;
    sa.sa_handler = sigterm_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    sigaction(SIGTERM, &sa, NULL);

    daemonize(pid_file);

    /* Main daemon worker loop */
    while (g_running) {
        sleep(1);
    }

    /* Cleanup PID file on clean exit */
    unlink(pid_file);
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The KillMode=process Zombie Accumulation

Under SysVinit, stopping a service frequently left orphaned worker processes behind because shell scripts relied on killing only the PID listed in `/var/run/daemon.pid`.

In 2018, an enterprise software vendor configured their Java analytics server with:
```ini
[Service]
KillMode=process
```
The application utilized a native C library that spawned detached child processes for media transcoding. During an incident, the Java process became unresponsive and was restarted by systemd via `systemctl restart analytics.service`.

Because `KillMode=process` was explicitly set, systemd sent `SIGTERM` **only to the main Java process**, completely ignoring the transcoder worker children. Over a 48-hour period of intermittent restarts, more than 8,000 orphaned media worker processes accumulated on the hypervisors, exhausting available RAM, pinning CPU cores at 100%, and causing kernel Out-Of-Memory (OOM) killer panics.

**The Fix**:
Always use the default `KillMode=control-group`. In this mode, systemd inspects `/sys/fs/cgroup/system.slice/<unit>` and atomically sends `SIGTERM` (and eventually `SIGKILL`) to **every single process** inside the cgroup, completely eliminating orphan leaks regardless of how deeply processes double-fork.

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Subsystem Impact |
| :--- | :--- | :--- |
| `systemctl status <unit>` | Runtime State | Shows PID, cgroup tree, memory/CPU usage, and last 10 journal entries. |
| `systemctl kill -s SIGKILL <unit>` | Force Kill | Sends `SIGKILL` directly across the unit's entire cgroup slice. |
| `systemctl reset-failed <unit>` | Reset Throttling | Clears the `start-limit-hit` error flag and counter after crash loops. |
| `systemctl isolate <target>` | Switch Runlevel | Stops all services not required by the specified target (e.g., rescue mode). |
| `systemctl mask <unit>` | Hard Disable | Symlinks unit to `/dev/null`, preventing manual or automated activation. |
