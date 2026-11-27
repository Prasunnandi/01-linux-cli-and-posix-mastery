# Day 44: systemd Timers - Monotonic Clocks, Calendar Events, and Cron Modernization

## 1. Architectural Superiority of systemd Timers over Cron

For over three decades, the POSIX `cron` daemon (`crond`) was the ubiquitous mechanism for scheduling periodic tasks. However, cron exhibits severe architectural shortcomings in modern cloud and container infrastructure:
- **No Dependency Awareness**: Cron executes jobs blindly regardless of network connectivity or filesystem state.
- **Silent Failures**: If a cron job fails, output is dumped to local UNIX mail (`/var/spool/mail/`), which is rarely read.
- **Resource Starvation**: Jobs scheduled at the exact same minute fire simultaneously, creating the **Thundering Herd Problem**.
- **No Catch-up Scheduling**: If a server is suspended or powered off during the scheduled window, cron skips the job entirely.

systemd timers (`.timer` units) solve these limitations by pairing a timer unit with an execution unit (`.service`), leveraging Linux kernel high-resolution timer file descriptors (`timerfd`), cgroups for resource throttling, and systemd journal integration.

```
+--------------------------------------------------------------------------+
|                       systemd TIMER ARCHITECTURE                         |
+--------------------------------------------------------------------------+
|  1. Timer Unit (/etc/systemd/system/backup.timer)                        |
|     - OnCalendar=*-*-* 02:00:00 (Real-time wallclock)                    |
|     - RandomizedDelaySec=15m    (De-synchronization jitter)              |
|     - Persistent=true           (Missed execution catch-up)              |
+--------------------------------------------------------------------------+
                                    |
                                    v timerfd_settime() (Linux Kernel)
+--------------------------------------------------------------------------+
|  2. Linux Kernel High-Resolution Timer Subsystem                         |
|     - CLOCK_MONOTONIC / CLOCK_REALTIME triggers epoll event in PID 1    |
+--------------------------------------------------------------------------+
                                    |
                                    v Activates Matching Service
+--------------------------------------------------------------------------+
|  3. Service Unit (/etc/systemd/system/backup.service)                    |
|     - Requires=network-online.target                                     |
|     - MemoryMax=1G (cgroup resource enforcement)                         |
|     - Logs automatically routed to systemd journal                       |
+--------------------------------------------------------------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: Linux timerfd API

systemd does not poll the clock in a sleep loop. Instead, PID 1 uses the Linux kernel `timerfd` subsystem (`sys/timerfd.h`), which creates a file descriptor that delivers timer expiration events directly through `epoll_wait()`.

```c
/* Real Linux Kernel Definition from include/linux/time64.h and sys/timerfd.h */
struct timespec64 {
    time64_t    tv_sec;         /* Seconds */
    long        tv_nsec;        /* Nanoseconds (0 to 999,999,999) */
};

struct itimerspec64 {
    struct timespec64 it_interval; /* Timer interval for periodic expiration */
    struct timespec64 it_value;    /* Initial expiration deadline */
};

/* systemd internal timer definition from src/core/timer.h */
typedef enum TimerBase {
    TIMER_ACTIVE,       /* Relative to unit activation time */
    TIMER_BOOT,         /* Relative to machine boot (CLOCK_MONOTONIC) */
    TIMER_STARTUP,      /* Relative to systemd manager startup */
    TIMER_UNIT_ACTIVE,  /* Relative to last time matching service activated */
    TIMER_UNIT_INACTIVE,/* Relative to last time matching service stopped */
    TIMER_CALENDAR,     /* Real-time wallclock calendar specification */
    _TIMER_BASE_MAX
} TimerBase;

struct Timer {
    Unit            meta;
    TimerValue      *values;
    usec_t          accuracy_usec;
    usec_t          random_usec;
    bool            persistent;
    bool            wake_system;

    /* Linux timerfd descriptor integrated into event loop */
    int             timer_fd;
};
```

---

## 3. Mathematical Foundations: Timer Jitter & Thundering Herd Suppression

When 5,000 microservice nodes all schedule log compaction at midnight (`00:00:00 UTC`), shared network storage and database backends suffer catastrophic latency spikes.

systemd resolves this mathematically via **Uniform Randomized Delay**:
$$T_{	ext{trigger}} = T_{	ext{scheduled}} + \Delta_{	ext{jitter}}$$
where $\Delta_{	ext{jitter}}$ is a uniformly distributed random variable:
$$\Delta_{	ext{jitter}} \sim \mathcal{U}\left(0, 	ext{RandomizedDelaySec}ight)$$

### Accuracy Coalescing
To conserve CPU power and prevent battery drain on laptops and edge devices, the Linux kernel coalesces wakeups within a defined accuracy window $\epsilon$:
$$[T_{	ext{trigger}} - \epsilon, T_{	ext{trigger}} + \epsilon]$$
In systemd, `AccuracySec=` sets $\epsilon$ (default: 1 minute), allowing the kernel to merge multiple timer interrupts into a single CPU wakeup.

---

## 4. Compilable C Implementation: Linux timerfd Epoll Event Loop

Save the following program as `timerfd_demo.c`:

```c
/*
 * timerfd_demo.c - High-resolution Timer Event Loop using Linux timerfd and epoll
 * Demonstrates:
 * 1. Creating a timer file descriptor via timerfd_create()
 * 2. Arming monotonic periodic intervals with timerfd_settime()
 * 3. Monitoring timer expirations non-blockingly via epoll_wait()
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread timerfd_demo.c -o timerfd_demo
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
#include <sys/timerfd.h>
#include <sys/epoll.h>
#include <time.h>
#include <errno.h>

int main(void)
{
    printf("====================================================\n");
    printf("LINUX timerfd HIGH-RESOLUTION SCHEDULING ENGINE\n");
    printf("====================================================\n");

    /* 1. Create a timerfd tracking CLOCK_MONOTONIC */
    int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    if (tfd < 0) {
        perror("timerfd_create failed");
        return EXIT_FAILURE;
    }

    /* 2. Arm timer: initial expiration at 1.0s, recurring interval every 1.5s */
    struct itimerspec new_value;
    new_value.it_value.tv_sec = 1;
    new_value.it_value.tv_nsec = 0;
    new_value.it_interval.tv_sec = 1;
    new_value.it_interval.tv_nsec = 500000000; /* 500 ms */

    if (timerfd_settime(tfd, 0, &new_value, NULL) < 0) {
        perror("timerfd_settime failed");
        close(tfd);
        return EXIT_FAILURE;
    }
    printf("[TIMER] Armed: First fire in 1.0s, interval every 1.5s\n");

    /* 3. Integrate into epoll event loop */
    int epfd = epoll_create1(EPOLL_CLOEXEC);
    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.fd = tfd;
    epoll_ctl(epfd, EPOLL_CTL_ADD, tfd, &ev);

    struct epoll_event events[4];
    int expirations = 0;

    while (expirations < 4) {
        int nfds = epoll_wait(epfd, events, 4, 3000);
        if (nfds < 0) {
            if (errno == EINTR) continue;
            perror("epoll_wait failed");
            break;
        }

        for (int i = 0; i < nfds; i++) {
            if (events[i].data.fd == tfd) {
                uint64_t misses = 0;
                /* Reading the timerfd returns the number of expirations that occurred */
                ssize_t s = read(tfd, &misses, sizeof(misses));
                if (s == sizeof(misses)) {
                    expirations++;
                    printf("[TICK %d] timerfd expired! (Overrun count: %lu)\n",
                           expirations, (unsigned long)misses);
                }
            }
        }
    }

    close(tfd);
    close(epfd);
    printf("[TIMER] Event loop cleanly finished.\n");
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The Persistent=true Disk Thrashing Incident

In 2021, an enterprise cloud database fleet experienced a critical storage lockup across 80 nodes following a 4-day scheduled datacenter power maintenance.

A junior engineer had created a database verification timer with:
```ini
[Timer]
OnCalendar=hourly
Persistent=true
```
When `Persistent=true` is set, systemd writes a timestamp file in `/var/lib/systemd/timers/stamp-<unit>.timer` each time the matching service runs. If the server is powered off for 96 hours, upon boot systemd determines that the service missed 96 scheduled execution windows!

Because no rate-limiting or concurrency bounds were configured, systemd immediately triggered the matching service upon boot. The service attempted to run 96 deep database integrity checks simultaneously, spawning thousands of parallel disk I/O threads that saturated the enterprise SAN, triggered kernel task lockups (`INFO: task blocked for more than 120 seconds`), and prevented SSH from accepting logins.

**The Fix**:
1. Added `ConditionPathExists=` and concurrency lockouts (`ExecStartPre=/usr/bin/flock -n /run/db_check.lock ...`).
2. Configured `RandomizedDelaySec=30m` to ensure that even after prolonged outages, timer executions are spread evenly across the timeline.

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Deep Technical Purpose |
| :--- | :--- | :--- |
| `systemctl list-timers` | Active Timer View | Displays next execution deadline, remaining time, and last trigger timestamp. |
| `systemd-analyze calendar "*-*-* 04:00:00"` | Expression Check | Parses and validates calendar syntax, printing the next 5 execution timestamps. |
| `systemctl list-timers --all` | Exhaustive Inspection | Includes inactive and dead timers awaiting event activation. |
| `journalctl -u <unit>.timer` | Timer Audit | Displays exact trigger history and execution delays logged by PID 1. |
