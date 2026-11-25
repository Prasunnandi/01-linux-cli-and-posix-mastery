# Day 27: Job Control: &, nohup, disown, jobs, fg, bg

## 1. Architectural Foundations: POSIX Sessions & Process Groups
In Unix systems, processes are organized into a strict hierarchy to manage terminal signals and window management:
- **Process (PID)**: A single executing task.
- **Process Group (PGID)**: A collection of related processes (e.g., all commands in a pipeline `cat | grep | awk` share the same PGID). Signals sent to a negative PID (e.g. `kill -SIGTERM -1050`) are broadcast to every process in that group!
- **Session (SID)**: A collection of process groups bound to a single **Controlling Terminal (`tty`)**.

```
+----------------------------------------------------------------------------+
| SESSION (SID: 500, e.g. SSH Terminal /dev/pts/1)                           |
+----------------------------------------------------------------------------+
       |                                               |
       v                                               v
+-------------------------------+       +-------------------------------+
| FOREGROUND PROCESS GROUP      |       | BACKGROUND PROCESS GROUP      |
|   (PGID: 501, e.g. vim)       |       |   (PGID: 502, e.g. python &)  |
|   - Receives stdin from tty   |       |   - Blocked from stdin (SIGTTIN)
|   - Receives Ctrl+C (SIGINT)  |       |   - Continues CPU execution   |
+-------------------------------+       +-------------------------------+
```

---

## 2. The SIGHUP Mechanism & Terminal Disconnection
When an SSH session drops, the kernel detects carrier loss on the pseudo-terminal:
1. The kernel sends **`SIGHUP` (Signal 1 - Hangup)** to the controlling process (the login shell).
2. The login shell broadcasts `SIGHUP` to all child process groups in its session.
3. By default, `SIGHUP` terminates processes instantly!

### Preserving Background Processes: `nohup` vs `disown`

| Feature | `nohup COMMAND &` | `COMMAND &; disown` |
| :--- | :--- | :--- |
| **Execution Point** | Invoked **before** starting the command. | Executed **after** starting the command. |
| **Signal Handling** | Ignores `SIGHUP` at process creation. | Removes the job from Bash's internal job table. |
| **I/O Redirection** | Automatically redirects stdout/stderr to `nohup.out`. | Keeps stdout/stderr bound to terminal (can crash on write). |
| **Terminal Close** | Process survives terminal close reliably. | Process survives shell `SIGHUP`, but crashes if writing to closed pty! |

---

## 3. Production Masterclass: Compilable C Daemonization Engine (Double-Fork)

Save as `daemon_engine.c` and compile with `gcc -Wall -Wextra -O2 daemon_engine.c -o daemon_engine`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>

void daemonize(void) {
    // Step 1: First fork (detach from parent shell)
    pid_t pid = fork();
    if (pid < 0) exit(1);
    if (pid > 0) exit(0); // Parent shell exits, returning control to terminal

    // Step 2: Create a new Session and become Session Leader
    if (setsid() < 0) exit(1); // Detaches from controlling terminal completely!

    // Step 3: Ignore SIGHUP
    signal(SIGHUP, SIG_IGN);

    // Step 4: Second fork (guarantees daemon can NEVER re-acquire a controlling terminal)
    pid = fork();
    if (pid < 0) exit(1);
    if (pid > 0) exit(0);

    // Step 5: Reset file creation mask
    umask(0);

    // Step 6: Change working directory to root to prevent unmounting filesystem
    chdir("/");

    // Step 7: Close and redirect standard file descriptors to /dev/null
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);

    int null_fd = open("/dev/null", O_RDWR);
    dup2(null_fd, STDIN_FILENO);
    dup2(null_fd, STDOUT_FILENO);
    dup2(null_fd, STDERR_FILENO);
}

int main(void) {
    printf("[+] Initiating daemonization sequence...\n");
    daemonize();

    // The process is now a 100% detached background daemon
    // Write heartbeat to a log file
    FILE *fp = fopen("/tmp/daemon_heartbeat.log", "w");
    if (fp) {
        fprintf(fp, "Daemon alive with PID: %d, Parent PID: %d\n", getpid(), getppid());
        fclose(fp);
    }

    return 0;
}
```

---

## 4. Production Post-Mortem: The Dropped Migration Disaster
### The Outage
A database engineer initiated a 4-hour schema migration over an SSH session:
```bash
python migrate_accounts.py &
```
Thirty minutes later, the engineer's laptop went to sleep. The SSH connection timed out with `packet_write_wait: Broken pipe`.
When the SSH daemon terminated, the login shell sent `SIGHUP` to the background python process, killing the migration midway through modifying 40 million records. The database was left in an inconsistent half-migrated state, forcing a 12-hour recovery from tape backups.

### Remediation
1. Never run long-running tasks directly in interactive shells.
2. Use a terminal multiplexer (`tmux` or `screen`), OR:
3. Explicitly detach with redirected streams:
   ```bash
   nohup python migrate_accounts.py > /var/log/migration.log 2>&1 &
   ```---

## 5. Terminal Signals & The Job Control State Machine
When an interactive user presses terminal key combinations, the terminal line discipline generates POSIX signals dispatched to the foreground process group:

```
+----------------------------------------------------------------------------+
| TERMINAL KEYSTROKE TO KERNEL SIGNAL MAPPING:                               |
|   - Ctrl+C -> SIGINT  (Signal 2, Interrupt - Graceful termination)         |
|   - Ctrl+\ -> SIGQUIT (Signal 3, Quit - Generates core dump)               |
|   - Ctrl+Z -> SIGTSTP (Signal 20, Terminal Stop - Suspends process)        |
+----------------------------------------------------------------------------+
```

### The Background Process I/O Traps: `SIGTTIN` and `SIGTTOU`
What happens when a background job tries to interact with the terminal?
1. **Background Read (`SIGTTIN`)**: If a background process calls `read(STDIN_FILENO)`, the kernel stops the process immediately by delivering `SIGTTIN` (Signal 21). This prevents background jobs from stealing keystrokes intended for the foreground shell!
2. **Background Write (`SIGTTOU`)**: If `tostop` terminal mode is enabled (`stty tostop`), any background write to stdout delivers `SIGTTOU` (Signal 22), preventing background jobs from garbling the terminal screen.

### Resuming Suspended Jobs
- `bg %1`: Sends `SIGCONT` (Signal 18) to Job 1, instructing it to resume execution in the background.
- `fg %1`: Assigns terminal control to Job 1 via `tcsetpgrp()` and sends `SIGCONT`, bringing it to the foreground.

---

## 6. Non-Blocking SIGCHLD Harvesting & Zombie Prevention
When background child processes terminate, they enter the `Z` (Zombie) state until their parent reads their exit status via `wait()` or `waitpid()`.
If a long-running daemon spawns background tasks without harvesting zombies, the Linux process table (`pid_max`, typically 32,768) fills up, preventing new processes from starting!

### The Non-Blocking SIGCHLD Handler in C
```c
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

// Asynchronous signal handler for SIGCHLD
void sigchld_handler(int sig) {
    (void)sig;
    int saved_errno = errno;
    // Harvest all terminated children without blocking using WNOHANG!
    while (waitpid(-1, NULL, WNOHANG) > 0);
    errno = saved_errno;
}

// In main(): Register SA_RESTART to prevent interrupting active syscalls:
struct sigaction sa;
sa.sa_handler = sigchld_handler;
sigemptyset(&sa.sa_mask);
sa.sa_flags = SA_RESTART | SA_NOCLDSTOP;
sigaction(SIGCHLD, &sa, NULL);
```
With `WNOHANG`, the loop reaps every child that terminated, completely eliminating zombie accumulation in production services.
---

## 7. Deep Architectural Mechanics: Kernel TTY Line Discipline & Session Topology

### TTY Architecture & Foreground Process Group
Every terminal session in Linux is controlled by a kernel **Session Leader** (the interactive login shell).
The terminal hardware or emulator (PTY) connects to a kernel **Line Discipline**. The line discipline tracks:
1. `foreground_pgrp`: The process group ID currently receiving terminal inputs (stdin) and keyboard signals (`Ctrl+C` $	o$ `SIGINT`, `Ctrl+Z` $	o$ `SIGTSTP`).
2. `background_pgrp`: Any process groups running in the background.

```
+-------------------------------------------------------------------------+
| KERNEL TTY LINE DISCIPLINE                                              |
|                                                                         |
| Keyboard: [Ctrl+C] ---> Generates SIGINT                                |
| Line discipline reads foreground_pgrp (e.g. PGID 1050)                  |
| Line discipline invokes: killpg(1050, SIGINT);                          |
|                                                                         |
| Background jobs (PGID 1080) DO NOT RECEIVE THE SIGNAL!                  |
+-------------------------------------------------------------------------+
```

### The Background TTY Read Signal: `SIGTTIN`
What happens when a background job tries to read from standard input (`read line` or `cat`)?
If multiple processes concurrently read from the terminal, characters would be randomly interleaved and stolen!
To prevent this chaos, the kernel line discipline detects when a process whose `pgrp != tty->pgrp` invokes `read()` on the TTY file descriptor.
The kernel immediately pauses the background process by delivering **`SIGTTIN` (Signal 21 - TTY Input)**. The process enters state `T` (Stopped) until the user brings it to the foreground with `fg`.

### Complete Compilable C Program: Process Group and Session Inspector
```c
/*
 * session_topology_demo.c - Dumps PID, PPID, PGID, and Session ID
 * Compile: gcc -O2 -Wall session_topology_demo.c -o session_topology_demo
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>

int main(void) {
    pid_t pid  = getpid();
    pid_t ppid = getppid();
    pid_t pgid = getpgrp();
    pid_t sid  = getsid(0);

    printf("=========================================\n");
    printf("LINUX PROCESS HIERARCHY TOPOLOGY AUDIT\n");
    printf("=========================================\n");
    printf("Process ID  (PID)  : %d\n", pid);
    printf("Parent PID  (PPID) : %d\n", ppid);
    printf("Process Grp (PGID) : %d\n", pgid);
    printf("Session ID  (SID)  : %d\n", sid);

    if (pid == pgid) {
        printf("-> Role: Process is the PROCESS GROUP LEADER\n");
    }
    if (pid == sid) {
        printf("-> Role: Process is the SESSION LEADER\n");
    }
    printf("=========================================\n");
    return 0;
}
```

---

## 8. Production War Story: The Rogue Background Daemon and the Orphan Storm
In 2017, a data engineering team automated a multi-hour machine learning ETL job via SSH. The engineer ran:
```bash
python run_etl.py &
exit
```
The next morning, the engineer discovered the job had abruptly terminated 2 seconds after logout!
Why? When an interactive SSH session terminates, the SSH daemon closes the TTY and sends **`SIGHUP` (Hangup)** to the Session Leader (the shell). The shell automatically broadcasts `SIGHUP` to all jobs in its active job table, killing them!
To detach a long-running process from TTY session death, you must either:
1. Use `nohup python run_etl.py > etl.log 2>&1 &` (ignores `SIGHUP` and redirects streams).
2. Run `disown -h %1` (removes the job from the shell's SIGHUP dispatch list).
3. Best practice: Execute inside a persistent terminal multiplexer like `tmux` or `screen`.
