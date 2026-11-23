# Day 10: POSIX Signals, `sigaction`, Asynchronous Interrupts & Graceful Shutdowns

> **Zero External Dependency Guarantee**: This document is an encyclopedic, self-contained masterclass. It contains complete historical origins, real-world mental models, kernel assembly stack frame injection mechanics (`setup_rt_frame` & `sys_rt_sigreturn`), comprehensive POSIX signal catalogs, async-signal-safety mathematical proofs, production graceful shutdown daemons in C, Kubernetes termination post-mortems, and FAANG staff-level interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & The Core Mental Model

In 1971, Unix introduced **Signals** as software interrupts to notify processes of asynchronous events:
* A hardware division by zero (`SIGFPE`).
* An illegal memory access past page bounds (`SIGSEGV`).
* An interactive user pressing `Ctrl+C` on a terminal (`SIGINT`).
* A parent requesting graceful application termination (`SIGTERM`).

Signals represent the purest form of asynchronous event handling in POSIX systems. When a signal is delivered, the Linux kernel interrupts normal userspace instruction flow, modifies the thread's execution stack, and jumps to a custom signal handler function before seamlessly resuming normal execution.

### The Postal Telegram Real-World Analogy:
Imagine you are a chef in a busy restaurant kitchen preparing a 7-course meal (the running process):
* You are in the middle of whisking sauce (executing CPU instructions in `main()`).
* Suddenly, a courier runs into the kitchen and thrusts an urgent telegram into your hand: **"Fire in the dining room!"** (`SIGTERM`).
* You do not ignore it. You immediately drop the whisk, turn off the gas stoves, open the emergency exits, and usher customers outside (executing your custom `signal_handler()`).
* Once the emergency is resolved, you return to the kitchen counter, pick up the whisk, and resume whisking right where you left off (the kernel restores the original register state via `sigreturn`)!

```
THE SIGNAL DELIVERY TIMELINE:
[ Normal Program Execution: main() loop ]
   Instruction A -> Instruction B
                        |
                        v [ Hardware Interrupt / Signal Generated (e.g., SIGTERM) ]
+-------------------------------------------------------------------------+
| Linux Kernel Intercepts: Prepares User Stack                            |
| 1. Saves registers into ucontext_t structure                            |
| 2. Pushes trampoline frame (__kernel_sigreturn) onto user stack         |
| 3. Overwrites CPU Instruction Pointer (RIP) with Handler Function Address|
+-------------------------------------------------------------------------+
                        |
                        v (CPU returns to Userspace Ring 3)
[ Custom Signal Handler: graceful_shutdown() ]
   Executes cleanup logic...
   Handler returns!
                        |
                        v (Executes trampoline code)
[ sys_rt_sigreturn System Call ]
   Kernel restores original CPU registers from ucontext_t
                        |
                        v
[ Resumes Instruction C in main() loop as if nothing happened! ]
```

---

## 2. Low-Level Kernel Architecture: How Signals Work Under the Hood

Signals are not handled in userspace alone; they require intricate coordination between the CPU hardware interrupt table and kernel execution frames.

### 2.1 The Two Phases of a Signal: Generation vs. Delivery
1. **Signal Generation**:
   A signal is generated when an event occurs (e.g., `kill()` syscall, hardware exception, or TTY keystroke).
   - The kernel locates the target process's `struct task_struct`.
   - It sets the corresponding bit in `task_struct->pending.signal` bitmask.
   - At this moment, the signal is **Pending**.
2. **Signal Delivery**:
   A pending signal is delivered only when the target process transitions from **Kernel Mode (Ring 0) back to User Mode (Ring 3)** (e.g., returning from a system call or timer interrupt).
   - The kernel checks: Is the signal unblocked in `task_struct->blocked`?
   - If unblocked, the kernel prepares userspace stack frame unwinding.

### 2.2 The Stack Trampoline Injection (`setup_rt_frame`)
How does the kernel force a process to execute a signal handler without its explicit consent?
1. The kernel allocates a `struct rt_sigframe` directly on the process's **userspace stack**.
2. It saves all current CPU registers (`RAX`, `RBX`, `RCX`, `RDX`, `RSI`, `RDI`, `RBP`, `RSP`, `RIP`, `EFLAGS`) into a `ucontext_t` structure inside that frame.
3. It sets the CPU Instruction Pointer (`RIP`) to the memory address of the registered signal handler.
4. It sets the return address on the stack to point to **`__kernel_sigreturn`** (a trampoline provided by the kernel vDSO).
5. The CPU drops back to Ring 3 and begins executing the handler.
6. When the handler completes its final `ret` instruction, the CPU pops `__kernel_sigreturn`, which executes the `rt_sigreturn` system call. The kernel reads back the saved registers from `ucontext_t` and restores the CPU to the exact instruction it was executing before the signal arrived!

---

## 3. Comprehensive POSIX Signal Reference

Every POSIX signal serves a deterministic operational purpose:

| Signal Name | Number (x86) | Default Action | Catchable? | Purpose & Common Trigger |
| :--- | :---: | :---: | :---: | :--- |
| **`SIGHUP`** | 1 | Terminate | Yes | Hangup detected on controlling terminal or reload configuration signal for daemons (`kill -HUP <pid>`). |
| **`SIGINT`** | 2 | Terminate | Yes | Interrupt from keyboard (`Ctrl+C`). Politely asks program to abort current interactive task. |
| **`SIGQUIT`**| 3 | Core Dump | Yes | Quit from keyboard (`Ctrl+\`). Generates a memory core dump for debugging. |
| **`SIGILL`** | 4 | Core Dump | Yes | Illegal instruction executed (binary corrupted or instruction unsupported by CPU). |
| **`SIGTRAP`**| 5 | Core Dump | Yes | Trace trap (used by debuggers like `gdb` for breakpoints). |
| **`SIGABRT`**| 6 | Core Dump | Yes | Abort signal emitted by `abort()` or a failed C `assert()`. |
| **`SIGBUS`** | 7 | Core Dump | Yes | Bus error: unaligned memory access or referencing non-existent physical memory in `mmap`. |
| **`SIGFPE`** | 8 | Core Dump | Yes | Floating-point exception (division by zero, integer overflow). |
| **`SIGKILL`**| **9** | **Terminate** | **NO** | **Uncatchable & Unignorable!** Instantly destroys process descriptor in kernel. |
| **`SIGUSR1`**| 10 | Terminate | Yes | User-defined signal 1 for application-specific IPC. |
| **`SIGSEGV`**| 11 | Core Dump | Yes | Segmentation Fault: invalid memory dereference (null pointer, write to read-only page). |
| **`SIGUSR2`**| 12 | Terminate | Yes | User-defined signal 2 for application-specific IPC. |
| **`SIGPIPE`**| 13 | Terminate | Yes | Broken pipe: write to a pipe/socket whose read end has closed. |
| **`SIGALRM`**| 14 | Terminate | Yes | Real-time timer alarm emitted by `alarm()` or `setitimer()`. |
| **`SIGTERM`**| 15 | Terminate | Yes | Polite termination request. The primary signal sent by `systemd`, `kill <pid>`, and Kubernetes! |
| **`SIGCHLD`**| 17 | Ignore | Yes | Child process stopped or terminated. Used by parents to trigger `waitpid()`. |
| **`SIGCONT`**| 18 | Continue | Yes | Resume execution if paused by `SIGSTOP` or `SIGTSTP`. |
| **`SIGSTOP`**| **19** | **Stop** | **NO** | **Uncatchable & Unignorable!** Instantly freezes execution (cannot run on CPU). |
| **`SIGTSTP`**| 20 | Stop | Yes | Terminal stop signal from keyboard (`Ctrl+Z`). Pauses program and returns to shell. |

---

## 4. Async-Signal-Safety: The Reentrancy Trap

The single most dangerous pitfall in Unix systems programming is calling non-reentrant functions inside a signal handler.

### 4.1 The `malloc()` Deadlock Proof
* Imagine your main program is executing `malloc(1024)`.
* `malloc()` acquires an internal mutex lock protecting the `glibc` memory heap.
* At that exact microsecond, the CPU receives a `SIGINT` signal.
* The kernel interrupts `malloc()` and invokes your signal handler.
* Your signal handler contains: `printf("Received signal!\n");`
* But `printf()` internally calls `malloc()` to allocate an output buffer!
* `malloc()` attempts to acquire the heap mutex lock. But the lock is **already held** by the interrupted `main()` thread!
* Result: **The process deadlocks itself forever!**

### 4.2 The Golden Rule of Signal Handling:
Inside a signal handler, you must **ONLY**:
1. Set a flag variable of type:
   `volatile sig_atomic_t g_shutdown_requested = 1;`
2. Or use raw POSIX async-signal-safe system calls: `write()`, `_exit()`.
3. Or write a byte to a self-pipe / eventfd to wake up an `epoll` event loop!

---

## 5. Complete C Implementation: Production Graceful Shutdown Daemon

```c
/**
 * graceful_daemon.c - Production-grade signal handling with sigaction.
 * Compile: gcc -Wall -Wextra -O2 graceful_daemon.c -o graceful_daemon
 */

#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>

/* Volatile ensures compiler does not cache flag in a CPU register */
static volatile sig_atomic_t g_terminate = 0;
static volatile sig_atomic_t g_reload_config = 0;

static void signal_handler(int signo) {
    if (signo == SIGTERM || signo == SIGINT) {
        g_terminate = 1;
    } else if (signo == SIGHUP) {
        g_reload_config = 1;
    }
}

int main(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART; /* Automatically restart interrupted slow syscalls */

    /* Register handlers for SIGTERM, SIGINT, and SIGHUP */
    if (sigaction(SIGTERM, &sa, NULL) < 0) perror("sigaction SIGTERM");
    if (sigaction(SIGINT, &sa, NULL) < 0)  perror("sigaction SIGINT");
    if (sigaction(SIGHUP, &sa, NULL) < 0)  perror("sigaction SIGHUP");

    printf("[Daemon PID %d] Running. Send SIGTERM to stop or SIGHUP to reload.\\n", getpid());

    while (!g_terminate) {
        if (g_reload_config) {
            printf("[Daemon] SIGHUP received: Reloading configuration safely in main loop...\\n");
            g_reload_config = 0;
        }

        printf("[Daemon] Processing background tasks...\\n");
        sleep(2);
    }

    printf("[Daemon] SIGTERM received! Starting graceful shutdown sequence...\\n");
    printf("[Daemon] 1. Closing database connections...\\n");
    sleep(1);
    printf("[Daemon] 2. Flushing telemetry buffers to disk...\\n");
    printf("[Daemon] Clean shutdown complete. Exiting with code 0.\\n");

    return EXIT_SUCCESS;
}
```

---

## 6. Real-World Production War Stories

### 6.1 War Story 1: The Kubernetes 30-Second Pod Termination Race
* **The Incident**: During automated Kubernetes rolling deployments, an e-commerce checkout microservice dropped approximately 0.5% of transactions during every deployment. Customers complained that their credit cards were charged, but orders were never recorded in the database!
* **The Root Cause**:
  1. When Kubernetes terminates a pod, it sends **`SIGTERM`** to the container's PID 1, and simultaneously removes the pod's IP from the Kubernetes Service endpoints.
  2. The service was running a naive Python web server that did not register a `SIGTERM` handler.
  3. The server aborted immediately upon `SIGTERM`, killing active in-flight checkout transactions mid-execution!
  4. Even when developers added a basic `SIGTERM` handler, the process took 35 seconds to finish drain operations. But Kubernetes defaults to `terminationGracePeriodSeconds: 30`.
  5. At exactly 30 seconds, Kubernetes issued **`SIGKILL` (Signal 9)**, violently aborting the lingering transactions anyway!
* **Resolution**:
  - Implemented a graceful shutdown hook in the application that stopped accepting new requests, finished existing requests within a 15-second budget, and closed connections cleanly.
  - Increased `terminationGracePeriodSeconds` to 45 seconds to guarantee headroom.

### 6.2 War Story 2: The Docker Shell Form `SIGKILL` Corruption
* **The Incident**: In a Docker setup, a database container consistently suffered corrupted index tables on `docker stop`.
* **The Physics**: The `Dockerfile` used shell form: `ENTRYPOINT /app/run.sh`. Docker runs this as `/bin/sh -c /app/run.sh`. `/bin/sh` does **not** forward signals to child processes! When `docker stop` sent `SIGTERM`, `/bin/sh` dropped it. 10 seconds later, Docker sent `SIGKILL`, destroying the database mid-write!
* **The Fix**: Used exec form: `ENTRYPOINT ["/app/run.sh"]` or `exec /app/run.sh` inside the script.

---

## 7. Staff-Level Technical Interview Deep-Dives

### Question 1: Why can `SIGKILL` (9) and `SIGSTOP` (19) NEVER be caught or ignored?
**Exhaustive Answer**:
* The operating system kernel must retain absolute administrative supremacy over userspace processes.
* If a process could catch or ignore `SIGKILL`, a buggy, rogue, or malicious program could ignore all termination requests, run infinite loops, consume 100% of CPU and RAM, and make the machine impossible to shut down or administer without physically pulling the power plug!
* Similarly, `SIGSTOP` allows debuggers (`gdb`) and the kernel to freeze a process unconditionally to inspect registers or throttle runaway tasks.

### Question 2: What is the difference between `kill()` and `tgkill()` system calls?
**Exhaustive Answer**:
* The classic `kill(pid, sig)` system call delivers a signal to an entire process (or thread group). If the process has 50 threads, the kernel delivers the signal to **any arbitrary thread** that currently has that signal unblocked!
* The modern `tgkill(tgid, tid, sig)` system call allows the caller to target a **specific individual thread (`tid`)** within a specific thread group (`tgid`). This is essential for runtime implementations (e.g., Java JVM or Go runtime) to profile or cancel a specific thread without affecting sibling threads.

---

## 8. Complete Verification Checklist (Zero Gaps)
- [ ] Diagram how the kernel injects `__kernel_sigreturn` onto the user stack during signal delivery.
- [ ] Why can calling `malloc()` or `printf()` inside a signal handler cause a fatal deadlock?
- [ ] What is the exact type definition of `volatile sig_atomic_t` and why is it required?
- [ ] Why does Docker kill containers with `SIGKILL` after 10 seconds if `ENTRYPOINT` is misconfigured?
- [ ] Explain the difference between `kill(pid, sig)` and `tgkill(tgid, tid, sig)`.
- [ ] Why are `SIGKILL` (9) and `SIGSTOP` (19) impossible to catch or block?
