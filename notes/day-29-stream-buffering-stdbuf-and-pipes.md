# Day 29: Stream Buffering Tools: stdbuf, unbuffer, pv

## 1. Architectural Foundations: The C Standard I/O (stdio) Buffering Dilemma
When an application writes to standard output using `printf()` or `write()`, data does not immediately hit the operating system kernel. The standard C library (`glibc`) buffers data in userspace memory to minimize expensive `write()` system calls.

`glibc` implements three distinct buffering modes defined in `<stdio.h>`:
1. **Unbuffered (`_IONBF`)**: Data is flushed immediately on every byte (used exclusively by `stderr`).
2. **Line Buffered (`_IOLBF`)**: Data is flushed whenever a newline character (`\n`) is encountered. **Default when stdout is connected to a terminal (TTY)**.
3. **Fully Buffered / Block Buffered (`_IOFBF`)**: Data is accumulated into a fixed-size block (typically **4096 bytes or 8192 bytes**) and flushed **ONLY when the buffer is 100% full**. **Default when stdout is redirected to a PIPE or FILE**!

```
+----------------------------------------------------------------------------+
| THE SILENT PIPELINE STALL BUG:                                             |
|                                                                            |
|   tail -f access.log | grep "ERROR" | awk '{print $1}'                     |
|                                                                            |
| 1. tail writes line-by-line.                                               |
| 2. grep sees stdout is a PIPE -> glibc switches grep to 4KB BLOCK BUFFERING!|
| 3. grep finds an error, but DOES NOT FLUSH until 4096 bytes accumulate!    |
| 4. awk receives ZERO data for 20 minutes! Real-time alerts fail!           |
+----------------------------------------------------------------------------+
```

---

## 2. Dynamic Stream Tuning: `stdbuf`, `unbuffer`, and `pv`

### 1. `stdbuf` (Zero-Overhead LD_PRELOAD Injection)
`stdbuf` modifies the buffering mode of dynamically linked C binaries **without recompiling them**:
```bash
# Force grep and awk to use Line Buffering on stdout:
tail -f access.log | stdbuf -oL grep "ERROR" | stdbuf -oL awk '{print $1}'
```
- `-iL`, `-oL`, `-eL`: Line buffering on stdin, stdout, or stderr.
- `-i0`, `-o0`, `-e0`: Unbuffered mode.
- `-o1M`: Custom 1 MiB buffer size.

#### How `stdbuf` Works Under the Hood
`stdbuf` sets the environment variable `LD_PRELOAD=/usr/lib/.../libstdbuf.so`.
When the target program launches, `libstdbuf.so` executes in the constructor phase **before `main()` runs**, invoking:
```c
setvbuf(stdout, NULL, _IOLBF, 0);
```

### 2. `unbuffer` (Expect Pseudo-Terminal Allocation)
For statically linked binaries or applications that ignore `setvbuf()`, `unbuffer` allocates a genuine pseudo-terminal (PTY) pair. The target program believes it is writing to an interactive terminal, naturally enabling line buffering.

### 3. `pv` (Pipe Viewer: Throughput & Rate Limiting)
`pv` sits between pipeline commands to measure data throughput, transfer progress, and throttle data rates:
```bash
# Monitor compression throughput:
cat large_db.sql | pv | gzip > backup.sql.gz
# Limit throughput to 10 MB/s to prevent disk saturation:
tar -czf - /data | pv -L 10M > /mnt/backup/archive.tar.gz
```

---

## 3. Production Masterclass: Compilable C stdio Buffering Demonstrator

Save as `stdio_buffer_demo.c` and compile with `gcc -Wall -Wextra -O2 stdio_buffer_demo.c -o stdio_buffer_demo`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void test_buffering_mode(int mode, const char *label) {
    printf("====================================================\n");
    printf("TESTING BUFFERING MODE: %s\n", label);
    printf("====================================================\n");

    // Reconfigure stdout buffering
    if (mode == _IONBF) {
        setvbuf(stdout, NULL, _IONBF, 0); // No buffering
    } else if (mode == _IOLBF) {
        setvbuf(stdout, NULL, _IOLBF, 0); // Line buffering
    } else if (mode == _IOFBF) {
        char *custom_buf = malloc(4096);
        setvbuf(stdout, custom_buf, _IOFBF, 4096); // 4KB Block buffering
    }

    printf("[+] Writing 10 characters without newline: ");
    for (int i = 0; i < 10; i++) {
        putchar('.');
        usleep(50000); // 50ms delay per dot
    }

    if (mode == _IOFBF) {
        printf(" <-- Block buffered (Visible only when flushed!)\n");
        fflush(stdout);
    } else {
        printf(" <-- Flushed in real time!\n");
    }
}

int main(void) {
    test_buffering_mode(_IONBF, "_IONBF (Unbuffered)");
    test_buffering_mode(_IOLBF, "_IOLBF (Line Buffered)");
    test_buffering_mode(_IOFBF, "_IOFBF (4KB Block Buffered)");
    return 0;
}
```

---

## 4. Production Post-Mortem: The 15-Minute Cyberattack Detection Delay
### The Outage
A security operations center (SOC) deployed a real-time intrusion detection pipeline:
```bash
tail -F /var/log/auth.log | grep --line-buffered "Failed password" | ./ban_ip.py
```
A junior engineer refactored the pipeline to add rate monitoring:
```bash
tail -F /var/log/auth.log | grep "Failed password" | awk '{print $11}' | ./ban_ip.py
```
During a brute-force SSH credential stuffing attack, attackers attempted 20,000 passwords. The `ban_ip.py` script banned zero IPs for 15 minutes!
Because `awk` stdout was a pipe, `awk` buffered 4096 bytes before flushing. The attacker compromised the server before the first batch of IPs was delivered to the firewall.

### Remediation
Enforce line buffering across every command in streaming log pipelines:
```bash
tail -F /var/log/auth.log | stdbuf -oL grep "Failed password" | stdbuf -oL awk '{print $11}' | ./ban_ip.py
```---

## 5. Pure C PTY Wrapper: Disabling Block Buffering Without LD_PRELOAD
When dealing with statically compiled binaries (e.g., Go, Rust, or static C binaries) where `stdbuf` cannot inject `libstdbuf.so`, the only way to force unbuffered line output is allocating a real **Pseudo-Terminal (PTY)**:

```c
#define _XOPEN_SOURCE 600
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>

int spawn_in_pty(const char *cmd, char *const argv[]) {
    int master_fd = posix_openpt(O_RDWR | O_NOCTTY);
    if (master_fd < 0) return -1;

    grantpt(master_fd);
    unlockpt(master_fd);
    char *slave_name = ptsname(master_fd);

    pid_t pid = fork();
    if (pid == 0) {
        close(master_fd);
        int slave_fd = open(slave_name, O_RDWR);
        dup2(slave_fd, STDIN_FILENO);
        dup2(slave_fd, STDOUT_FILENO);
        dup2(slave_fd, STDERR_FILENO);
        close(slave_fd);
        setsid();
        execvp(cmd, argv);
        exit(1);
    }
    return master_fd; // Parent reads unbuffered stdout from master_fd!
}
```
Because the child process has its stdout bound to a genuine `/dev/pts/N` slave device, `isatty(1)` evaluates to true. Standard C libraries automatically select **Line Buffering (`_IOLBF`)**, guaranteeing instantaneous real-time output stream forwarding.

---

## 6. Kernel Pipe Buffer Sizing with fcntl(F_SETPIPE_SZ)
In the Linux kernel, anonymous pipes created with `pipe()` or `|` have a default buffer capacity of **65,536 bytes (64 KB / 16 pages)**.
When a fast producer writes faster than a slow consumer can read:
- Once 64 KB accumulates in the kernel pipe buffer, the `write()` system call **blocks** until the consumer reads data.
- If high-bandwidth throughput is required, the pipe buffer size can be dynamically grown up to `/proc/sys/fs/pipe-max-size` (typically 1 MiB or 8 MiB):

```c
#define _GNU_SOURCE
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>

void enlarge_pipe_capacity(int pipe_fd) {
    // Query current pipe capacity
    int current_size = fcntl(pipe_fd, F_GETPIPE_SZ);
    printf("[+] Default Pipe Capacity: %d bytes (%.1f KB)\n",
           current_size, (double)current_size / 1024.0);

    // Enlarge pipe buffer to 1 MiB (1,048,576 bytes)
    int new_size = fcntl(pipe_fd, F_SETPIPE_SZ, 1024 * 1024);
    if (new_size < 0) {
        perror("fcntl(F_SETPIPE_SZ)");
    } else {
        printf("[+] Upgraded Pipe Capacity: %d bytes (%.1f MB)\n",
               new_size, (double)new_size / (1024.0 * 1024.0));
    }
}
```
Enlarging the pipe buffer reduces context switching overhead between producer and consumer threads by up to **400%** on high-speed data pipelines.
---

## 7. Deep Architectural Mechanics: Glibc `stdio` Buffering & `LD_PRELOAD` Interposition

### The Three Buffering Modes in Glibc `_IO_FILE`
Under the hood, C standard I/O library (`stdio.h`) manages user-space memory buffers to minimize expensive `read()` and `write()` system calls.
The buffering mode is stored in the internal `flags` field of `FILE *`:
1. **`_IONBF` (Unbuffered)**:
   - Every single call to `fputc()` or `printf()` immediately invokes the `write(2)` system call.
   - Standard error (`stderr`) is unbuffered by default so error messages appear immediately even during a crash.
2. **`_IOLBF` (Line Buffered)**:
   - Characters are stored in a memory buffer and flushed to the OS kernel only when a newline character `\n` is written, or when the buffer fills up.
   - Standard output (`stdout`) is line-buffered by default when connected to an interactive TTY!
3. **`_IOFBF` (Fully Buffered / Block Buffered)**:
   - Data is held in a large buffer (typically 4096 or 8192 bytes). It is ONLY flushed when the buffer is 100% full or `fflush()` is called explicitly.
   - Standard output (`stdout`) automatically switches to fully buffered when redirected to a file or pipe!

```
TTY Connected:       printf("msg\n")  ---> Line Buffered  ---> Flushed Immediately!
Pipe/File Connected: printf("msg\n")  ---> Fully Buffered ---> Stuck in 4KB RAM buffer!
```

### How `stdbuf` Works via `LD_PRELOAD`
The `stdbuf` utility does not modify the binary file on disk. Instead, it forces the dynamic linker (`ld.so`) to preload a helper shared library (`libstdbuf.so`) before standard libraries:
```bash
LD_PRELOAD=/usr/lib64/coreutils/libstdbuf.so _STDBUF_O=L my_command | grep pattern
```
When `libstdbuf.so` loads, its constructor function runs before `main()`. It reads environment variables like `_STDBUF_O=L` and calls:
```c
setvbuf(stdout, NULL, _IOLBF, 0);
```
This forces `stdout` to remain line-buffered even when writing into a pipe!

---

## 8. Production War Story: The Hanging Microservice Log Monitor
In 2019, a DevOps team configured a real-time log alerting pipeline for a Python-based microservice:
```bash
python worker.py | grep "CRITICAL_ERROR" | alert_pager.sh
```
During a major production outage, the database crashed and the microservice emitted dozens of `CRITICAL_ERROR` messages. Yet, the paging system sent zero alerts!
The engineering team only received alerts 45 minutes later, after the outage had worsened.
Why? Because standard Python output is block-buffered when piped. The microservice's error messages were trapped inside Python's 8 KB memory buffer. Only when the service finally crashed or filled 8 KB of logs was the buffer flushed into `grep`.
Fix: Run Python with unbuffered standard streams using `python -u worker.py` or use `stdbuf -oL` on the pipeline commands!
