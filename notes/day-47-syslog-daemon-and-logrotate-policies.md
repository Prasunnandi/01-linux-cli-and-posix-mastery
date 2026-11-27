# Day 47: Syslog Architecture & Logrotate - RFC 5424 Protocols, Sockets, and Rotation Mechanics

## 1. Classical Logging Ecosystem: RFC 3164 vs RFC 5424

Before structured binary journals, standard Linux logging was governed by RFC 3164 (The BSD Syslog Protocol) and modernized by RFC 5424. The architecture centers around a daemon (`rsyslogd` or `syslog-ng`) listening on `/dev/log` and multiplexing logs across local files (`/var/log/syslog`, `/var/log/auth.log`) and remote log collectors via UDP/TCP port 514.

### The RFC 5424 Wire Format Grammar:
$$	ext{SYSLOG-MSG} = \langle 	ext{PRI} angle 	ext{VERSION} \quad 	ext{TIMESTAMP} \quad 	ext{HOSTNAME} \quad 	ext{APP-NAME} \quad 	ext{PROCID} \quad 	ext{MSGID} \quad 	ext{STRUCTURED-DATA} \quad 	ext{MSG}$$

### Priority Calculation:
Every syslog event carries a combined `PRI` integer between 0 and 191 encoded within angle brackets `"<PRI>"`. It is calculated from two orthogonal dimensions:
$$	ext{PRI} = (	ext{Facility} 	imes 8) + 	ext{Severity}$$

- **Facilities (0 to 23)**: `kern` (0), `user` (1), `mail` (2), `daemon` (3), `auth` (4), `syslog` (5), `lpr` (6), `local0-local7` (16-23).
- **Severities (0 to 7)**: `Emergency` (0), `Alert` (1), `Critical` (2), `Error` (3), `Warning` (4), `Notice` (5), `Informational` (6), `Debug` (7).

```
Example:
Facility: auth (4), Severity: Critical (2)
PRI = (4 * 8) + 2 = 34
Wire prefix: <34>1 2026-11-27T02:00:00.123Z host app 1234 ID47 [auth@123 user="root"] Access Denied
```

---

## 2. Kernel C Structs & Binary Bitfields: File Descriptors & Inode Lifecycles

Understanding why simple shell commands like `mv app.log app.log.1` fail to rotate logs without breaking the application requires examining how the Linux VFS tracks open files.

When a process calls `open("/var/log/app.log", O_WRONLY | O_APPEND)`, the kernel allocates a file descriptor that references an in-memory `struct file` pointing to an underlying `struct inode`:

```c
/* Real Linux Kernel VFS Definition excerpted from include/linux/fs.h */
struct inode {
    umode_t             i_mode;         /* File mode and permissions */
    kuid_t              i_uid;          /* Owner UID */
    kgid_t              i_gid;          /* Owner GID */
    unsigned int        i_flags;
    const struct file_operations *i_fop;
    struct super_block  *i_sb;          /* Backing superblock */
    unsigned long       i_ino;          /* Inode number on disk */
    atomic_t            i_count;        /* Reference counter */
    loff_t              i_size;         /* Current byte length of file */
    struct timespec64   i_mtime;        /* Modification timestamp */
};

struct file {
    struct path         f_path;         /* Dentry and mount reference */
    struct inode        *f_inode;       /* Cached pointer to inode */
    const struct file_operations *f_op;
    atomic_long_t       f_count;
    unsigned int        f_flags;        /* O_APPEND, O_NONBLOCK, O_CLOEXEC */
    fmode_t             f_mode;
    loff_t              f_pos;          /* Current file read/write offset */
};
```

### The Inode Retention Invariant:
When an administrator executes `mv /var/log/app.log /var/log/app.log.1`:
1. The filesystem merely updates directory entries (dentries). The underlying **inode number does not change**.
2. The running daemon still holds an open `struct file` pointing directly to that exact inode.
3. Therefore, the daemon **continues writing to the renamed file `app.log.1`**! Disk space is never freed, and the newly created `app.log` remains empty.

---

## 3. Mathematical Foundations: The Logrotate Rotation Strategies

To solve the inode retention problem, `logrotate` provides two distinct architectural strategies:

### Strategy 1: Signal-Based Reopen (`postrotate / SIGHUP`)
1. `logrotate` renames `app.log` $	o$ `app.log.1`.
2. It executes a `postrotate` script that sends a signal (typically `SIGHUP` or `USR1`) to the daemon:
   $$	ext{kill} -s 	ext{HUP} \quad 	ext{PID}$$
3. The daemon's signal handler executes:
   $$	ext{close}(	ext{old\_fd}); \quad 	ext{open}("/	ext{var}/	ext{log}/	ext{app.log}", O\_CREAT | O\_APPEND);$$
4. **Pros**: Zero data loss, zero CPU overhead.
5. **Cons**: Requires the daemon software to support atomic signal-based log re-opening.

### Strategy 2: Copy-Truncate (`copytruncate`)
When a daemon cannot be signaled or restarted:
1. `logrotate` copies the active contents:
   $$	ext{app.log} \xrightarrow{	ext{copy}} 	ext{app.log.1}$$
2. It atomically truncates the active file in-place using the `truncate()` system call:
   $$	ext{truncate}(	ext{app.log}, 0);$$
3. The daemon continues writing to the existing inode at offset 0.
4. **Mathematical Race Condition**:
   Let $\Delta t$ be the duration between reading the last byte and calling `truncate()`. If the daemon writes $B_{	ext{race}}$ bytes during $\Delta t$:
   $$B_{	ext{lost}} = B_{	ext{race}} = \int_{t_{	ext{copy}}}^{t_{	ext{trunc}}} R_{	ext{write}}(t) \, dt$$
   Those bytes are destroyed and permanently lost. Therefore, `copytruncate` is prohibited for audit and financial transaction logs.

---

## 4. Compilable C Implementation: SIGHUP Atomic Log Re-Opener

Save the following program as `sighup_logger.c`:

```c
/*
 * sighup_logger.c - Production Daemon implementing Atomic Log Re-Opening via SIGHUP
 * Demonstrates:
 * 1. Holding an open log file descriptor
 * 2. Asynchronous SIGHUP signal capture
 * 3. Atomic re-opening without terminating the worker thread
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread sighup_logger.c -o sighup_logger
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <string.h>
#include <time.h>
#include <errno.h>

static volatile sig_atomic_t g_reopen_logs = 0;
static volatile sig_atomic_t g_running = 1;

static void sighup_handler(int sig)
{
    (void)sig;
    g_reopen_logs = 1;
}

static void sigterm_handler(int sig)
{
    (void)sig;
    g_running = 0;
}

int main(int argc, char *argv[])
{
    const char *log_path = (argc > 1) ? argv[1] : "/tmp/production_daemon.log";

    /* Setup Signal Handlers */
    struct sigaction sa_hup, sa_term;
    memset(&sa_hup, 0, sizeof(sa_hup));
    sa_hup.sa_handler = sighup_handler;
    sigaction(SIGHUP, &sa_hup, NULL);

    memset(&sa_term, 0, sizeof(sa_term));
    sa_term.sa_handler = sigterm_handler;
    sigaction(SIGTERM, &sa_term, NULL);

    printf("====================================================\n");
    printf("ATOMIC SIGHUP LOG RE-OPENER (PID: %d)\n", getpid());
    printf("Log Path: %s\n", log_path);
    printf("====================================================\n");

    int log_fd = open(log_path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (log_fd < 0) {
        perror("Failed to open log file");
        return EXIT_FAILURE;
    }

    int counter = 0;
    while (g_running && counter < 5) {
        if (g_reopen_logs) {
            g_reopen_logs = 0;
            printf("[DAEMON] SIGHUP caught! Closing old inode and re-opening %s...\n", log_path);
            close(log_fd);
            log_fd = open(log_path, O_WRONLY | O_CREAT | O_APPEND, 0644);
            if (log_fd < 0) {
                perror("Log re-open failed");
                break;
            }
            printf("[DAEMON] Log file re-opened successfully on new inode!\n");
        }

        char buffer[128];
        int len = snprintf(buffer, sizeof(buffer),
                           "[%ld] Worker heartbeat tick %d\n", time(NULL), ++counter);
        write(log_fd, buffer, len);
        sleep(1);
    }

    close(log_fd);
    printf("[DAEMON] Clean shutdown complete.\n");
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The Deleted Inode Disk Space Leak

In 2017, a critical monitoring host alerted: `/var partition is at 100% capacity (0 bytes free)`. 

The on-call engineer logged into the host and ran:
```bash
du -sh /var/log/*
```
The output showed that `/var/log` was only consuming 2.1 GB of disk space on a 200 GB volume! The engineer assumed filesystem corruption and ran `fsck`.

**The Root Cause**:
An unmanaged Java application was writing 1 GB of logs per hour to `/var/log/java_app.log`. Another administrator had manually executed `rm /var/log/java_app.log` to quickly free up disk space.

Because the Java process still had the file open:
1. `rm` simply unlinked the directory entry (`dentry`), decrementing the hard link count from 1 to 0.
2. However, the kernel's `inode->i_count` remained greater than zero because of the open file descriptor.
3. In ext4 and XFS, disk blocks are **only freed when both hard link count AND open file descriptor count reach zero**.
4. The Java application continued writing 190 GB of logs to the unlinked, invisible inode. `du` traverses directory trees and could not see the unlinked file, while `df` reads superblock block allocation counters and correctly reported disk exhaustion!

**The Diagnosis & Remediation**:
```bash
# Locate unlinked open files consuming disk blocks:
lsof +L1 | grep deleted

# Instantly truncate the invisible file via procfs:
> /proc/<PID>/fd/<FD>
```

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Subsystem Impact |
| :--- | :--- | :--- |
| `logrotate -d /etc/logrotate.conf` | Debug Dry-Run | Simulates rotation logic line-by-line without altering files on disk. |
| `logrotate -f /etc/logrotate.d/nginx` | Force Rotation | Forces immediate rotation regardless of size or time expiration rules. |
| `logger -p local0.err "Database error"` | Emit Syslog | Transmits an RFC 5424/3164 datagram directly to `/dev/log`. |
| `lsof -u <user> | grep '(deleted)'` | Detect Ghost Inodes | Identifies deleted files held open in memory that are preventing space reclamation. |
| `cat /var/lib/logrotate/status` | Rotation Ledger | Inspects the recorded timestamps of when each log file was last rotated. |
