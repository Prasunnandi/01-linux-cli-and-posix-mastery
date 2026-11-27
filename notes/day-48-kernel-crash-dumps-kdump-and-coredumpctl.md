# Day 48: Kernel Crash Dumps & Userspace Coredumps - kdump, kexec, and coredumpctl

## 1. Crash Telemetry: Kernel Panics vs Userspace Faults

When software crashes in a production environment, diagnosing the root cause requires capturing the exact register state, call stack, and memory contents at the precise millisecond of failure:
1. **Userspace Coredump**: Triggered when a process receives a fatal terminating signal (`SIGSEGV`, `SIGBUS`, `SIGABRT`, `SIGFPE`, `SIGILL`). The Linux kernel freezes the thread group and dumps the process memory space into an ELF-formatted core file (`coredumpctl`, `/proc/sys/kernel/core_pattern`).
2. **Kernel Crash Dump (`kdump`)**: Triggered when the Linux kernel itself crashes (Kernel Panic, NULL pointer dereference in kernel space, hardware Machine Check Exception). Because the running kernel is corrupted and untrusted, it cannot reliably write to disk. Instead, the hardware uses **`kexec`** to boot a completely isolated, clean secondary kernel residing in pre-reserved RAM to safely dump physical memory to disk (`/var/crash/vmcore`).

```
+--------------------------------------------------------------------------+
|                     KERNEL CRASH TELEMETRY (kdump)                       |
+--------------------------------------------------------------------------+
|  Primary Production Kernel (Active Memory: 64 GB)                         |
|  - Pre-allocates isolated Crashkernel RAM via bootloader: crashkernel=512M|
|  - System Panic occurs (e.g., NULL pointer in network driver)            |
+--------------------------------------------------------------------------+
                                    |
                                    v panic() -> machine_kexec()
+--------------------------------------------------------------------------+
|  Secondary Capture Kernel (Boots inside isolated 512 MB Crashkernel RAM) |
|  - Production kernel memory is preserved in raw physical address space   |
|  - Capture kernel exports raw physical RAM via /proc/vmcore              |
|  - makedumpfile filters user/zero pages and compresses vmcore to disk    |
+--------------------------------------------------------------------------+
                                    |
                                    v Writes compressed ELF core
+--------------------------------------------------------------------------+
|                       /var/crash/<date>/vmcore                           |
+--------------------------------------------------------------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: ELF Core Headers and CPU Registers

Both kernel crash dumps (`vmcore`) and userspace core dumps are packaged as standard ELF (Executable and Linkable Format) binary files with `e_type = ET_CORE`. 

Instead of sections (`.text`, `.data`), an ELF core dump contains programmatic segments (`PT_LOAD`) mapping memory pages and special note segments (`PT_NOTE`) storing CPU register states.

Below are the Linux kernel C structs from `include/uapi/linux/elfcore.h` and `include/uapi/linux/elf.h`:

```c
/* Real Linux Kernel Definition from include/uapi/linux/elfcore.h */
struct elf_siginfo {
    int32_t     si_signo;       /* Signal number (e.g. 11 for SIGSEGV) */
    int32_t     si_code;        /* Signal code (e.g. SEGV_MAPERR) */
    int32_t     si_errno;       /* Errno value */
};

/* PRSTATUS Note: Process status and CPU architectural registers */
struct elf_prstatus {
    struct elf_siginfo  pr_info;        /* Information about the faulting signal */
    int16_t             pr_cursig;      /* Current signal */
    unsigned long       pr_sigpend;     /* Set of pending signals */
    unsigned long       pr_sighold;     /* Set of held signals */
    pid_t               pr_pid;         /* Faulting Process ID */
    pid_t               pr_ppid;        /* Parent Process ID */
    pid_t               pr_pgrp;        /* Process Group ID */
    pid_t               pr_sid;         /* Session ID */
    struct timeval      pr_utime;       /* User CPU time used */
    struct timeval      pr_stime;       /* System CPU time used */
    
    /* Architectural CPU General Purpose Registers (x86_64) */
    struct user_regs_struct pr_reg;     /* RAX, RBX, RCX, RDX, RSI, RDI, RSP, RIP, RFLAGS */
    int                 pr_fpvalid;     /* Floating point registers valid flag */
};

/* x86_64 register state excerpted from sys/user.h */
struct user_regs_struct {
    unsigned long long r15, r14, r13, r12, rbp, rbx, r11, r10;
    unsigned long long r9, r8, rax, rcx, rdx, rsi, rdi, orig_rax;
    unsigned long long rip;             /* Instruction Pointer at crash time */
    unsigned long long cs, eflags;      /* CPU Flags (ZF, CF, SF) */
    unsigned long long rsp;             /* Stack Pointer at crash time */
    unsigned long long ss, fs_base, gs_base, ds, es, fs, gs;
};
```

---

## 3. Mathematical Foundations: Dump Compression Ratios & Bitmask Filtering

Dumping 512 GB of raw server RAM across NVMe disks during a kernel panic would exhaust storage and take 20 minutes, causing cluster failover timeouts.

The `makedumpfile` utility resolves this using **Selective Memory Page Filtering**. Physical RAM is modeled as an array of page frames of size $P_{	ext{size}} = 4096	ext{ bytes}$. 

### The Dump Level Bitmask:
Let each page belong to one of 5 classes:
- Class 1 ($d_1$): Zero pages (unallocated memory filled with zeros).
- Class 2 ($d_2$): Non-private cache pages (clean page cache backed by disk).
- Class 3 ($d_3$): Private cache pages.
- Class 4 ($d_4$): User process memory.
- Class 5 ($d_5$): Free pages.

The dump level $D$ is configured as a bitwise integer:
$$D = \sum_{i=1}^{5} b_i \cdot 2^{i-1}$$
The standard production dump level is `DumpLevel = 31` (all 5 bits set: $1 + 2 + 4 + 8 + 16 = 31$). This discards all zero, cache, user, and free pages, retaining **only kernel data structures and module memory**.

The compression ratio achieved by zstandard (`zstd`) on filtered kernel dumps is:
$$	ext{Size}(	ext{vmcore}) = \sum_{p \in 	ext{KernelPages}} 	ext{Compress}(p) pprox 0.02 	imes 	ext{RAM}_{	ext{total}}$$
A 512 GB server yields a tiny, highly actionable 2 GB `vmcore` file written in less than 3 seconds!

---

## 4. Compilable C Implementation: Automated Signal Interceptor & Crash Diagnostics

Save the following program as `crash_telemetry.c`:

```c
/*
 * crash_telemetry.c - Advanced POSIX Signal Crash Diagnostic Interceptor
 * Demonstrates:
 * 1. Catching SIGSEGV via sigaction with SA_SIGINFO
 * 2. Extracting exact memory address that caused the fault (si_addr)
 * 3. Inspecting CPU instruction pointer (RIP) from ucontext_t
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread crash_telemetry.c -o crash_telemetry
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <ucontext.h>
#include <string.h>

void sigsegv_diagnostic_handler(int sig, siginfo_t *info, void *ucontext_ptr)
{
    (void)sig;
    ucontext_t *uc = (ucontext_t *)ucontext_ptr;

    /* Extract architectural instruction pointer (x86_64: REG_RIP) */
#if defined(__x86_64__)
    unsigned long long rip = uc->uc_mcontext.gregs[REG_RIP];
    unsigned long long rsp = uc->uc_mcontext.gregs[REG_RSP];
#else
    unsigned long long rip = 0;
    unsigned long long rsp = 0;
#endif

    fprintf(stderr, "\n====================================================\n");
    fprintf(stderr, "CRITICAL FAULT: POSIX SIGNAL %d (SIGSEGV) CAUGHT\n", info->si_signo);
    fprintf(stderr, "====================================================\n");
    fprintf(stderr, "Faulting Memory Address (si_addr) : %p\n", info->si_addr);
    fprintf(stderr, "Signal Cause Code (si_code)       : %d (%s)\n",
            info->si_code, (info->si_code == SEGV_MAPERR) ? "SEGV_MAPERR (Address not mapped)" : "SEGV_ACCERR");
    fprintf(stderr, "CPU Instruction Pointer (RIP)     : 0x%llX\n", rip);
    fprintf(stderr, "Stack Pointer (RSP)               : 0x%llX\n", rsp);
    fprintf(stderr, "====================================================\n");
    fprintf(stderr, "[DIAGNOSTIC] Writing telemetry to disk before core generation...\n");

    /* Reset to default handler and re-raise so kernel produces coredump */
    signal(SIGSEGV, SIG_DFL);
    raise(SIGSEGV);
}

int main(void)
{
    printf("====================================================\n");
    printf("SIGNAL CRASH TELEMETRY ENGINE (PID: %d)\n", getpid());
    printf("====================================================\n");

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = sigsegv_diagnostic_handler;
    sa.sa_flags = SA_SIGINFO | SA_RESETHAND;
    sigaction(SIGSEGV, &sa, NULL);

    printf("[TEST] Arming deliberate NULL pointer dereference...\n");
    sleep(1);

    /* Intentionally trigger a SEGV_MAPERR */
    volatile int *bad_ptr = (int *)0x00000000DEADBEEF;
    *bad_ptr = 42;

    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The Core Pattern Pipe Deadlock

In 2019, a Fortune 500 bank running a distributed microservices platform suffered a total cluster freeze. Whenever a single worker service segfaulted, all other unrelated services on the node became unresponsive within 60 seconds.

**The Architecture**:
The `/proc/sys/kernel/core_pattern` had been configured to pipe coredumps into an automated telemetry agent:
```
|/usr/local/bin/crash_reporter --pid=%p --uid=%u
```
**The Flaw**:
1. When a process crashes, the Linux kernel pauses the process, enters kernel mode, and forks the piped helper program (`crash_reporter`), connecting stdout of the kernel core dump to stdin of the helper via a kernel pipe.
2. The `crash_reporter` binary had a bug: it attempted to allocate 2 GB of memory upon startup.
3. During heavy load, the system was low on memory. `crash_reporter` blocked waiting for memory allocation from the kernel.
4. Because `crash_reporter` did not read from the pipe, the pipe buffer filled up (64 KB). The Linux kernel thread paused, holding the internal `mm->mmap_lock` semaphore of the crashed process.
5. Other diagnostic utilities like `ps`, `top`, and `systemctl` attempted to read `/proc/<crashed_pid>/stat` and blocked waiting for `mmap_lock`. Within 2 minutes, all monitoring and management tools hung in State `D` (Uninterruptible Sleep).

**The Fix**:
Never pipe coredumps directly into unbuffered userland scripts. Always use `systemd-coredump` (`/lib/systemd/systemd-coredump %P %u %g %s %t %c %h`), which utilizes asynchronous kernel socket buffers, enforces strict storage quotas in `/var/lib/systemd/coredump/`, and compresses dumps in real-time with LZ4.

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Deep Technical Purpose |
| :--- | :--- | :--- |
| `coredumpctl list` | View Core Dumps | Lists all captured userspace coredumps with PID, UID, signal, and executable path. |
| `coredumpctl debug <pid>` | Instant GDB Session | Automatically invokes `gdb` against the executable and its matching ELF core. |
| `coredumpctl info <pid>` | Stack Trace Telemetry | Prints saved registers, signal code, and backtrace without opening GDB. |
| `kexec -p /boot/vmlinuz ...` | Arm Capture Kernel | Pre-loads the isolated secondary capture kernel into reserved memory. |
| `crash /usr/lib/debug/.../vmlinux /var/crash/.../vmcore` | Kernel Dump Debug | Starts Red Hat Crash utility to analyze call stacks from kernel panics. |
