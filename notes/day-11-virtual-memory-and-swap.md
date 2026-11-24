# Day 11: Virtual Memory, Page Tables & Swap (vmstat)

## 1. Architectural Foundations: Virtual Memory & Address Translation

In modern computing architectures, no user-space process ever accesses physical RAM directly. Instead, every single process executes inside its own private, isolated **Virtual Address Space**. On x86-64 Linux, this address space spans an astronomical $2^{48}$ bytes ($256\text{ TB}$) in 4-level paging mode (or $2^{57} = 128\text{ PB}$ in 5-level paging mode).

The fundamental goals of virtual memory are:
1. **Isolation & Memory Protection**: Process $A$ cannot read or overwrite Process $B$'s memory, nor can it touch kernel memory (Ring 0) from user space (Ring 3).
2. **Illusion of Abundant Memory**: Processes can allocate contiguous blocks of memory that are non-contiguous in physical RAM, or even backed by secondary disk storage (Swap).
3. **Transparent Memory Sharing**: Multiple processes executing `/bin/bash` or linking `libc.so` can share the exact same read-only physical memory frames.

```
+-------------------------------------------------------------------------+
|                  x86-64 Virtual Address Space Layout                    |
+-------------------------------------------------------------------------+
| 0xFFFFFFFFFFFFFFFF +--------------------------------------------------+ |
|                    | Kernel Space (128 TB) - Higher Half Mapping      | |
| 0xFFFF800000000000 +--------------------------------------------------+ |
|                    | Non-Canonical Hole (Guard Space, 16.7 Million TB)| |
| 0x00007FFFFFFFFFFF +--------------------------------------------------+ |
|                    | Stack (Grows Downward toward lower addresses)    | |
|                    |   |                                              | |
|                    |   v                                              | |
|                    | Memory Mapping Segment (mmap, shared libraries)  | |
|                    |   ^                                              | |
|                    |   |                                              | |
|                    | Heap (Grows Upward via brk/sbrk)                 | |
|                    | BSS Segment (Uninitialized Static Variables)     | |
|                    | Data Segment (Initialized Static Variables)      | |
|                    | Text Segment (Compiled Executable Machine Code)  | |
| 0x0000000000000000 +--------------------------------------------------+ |
+-------------------------------------------------------------------------+
```

### 1.1 The Hardware MMU & 4-Level Page Tables

The physical CPU contains a specialized hardware component called the **Memory Management Unit (MMU)**. Every memory dereference in assembly (e.g. `movq (%rax), %rbx`) passes through the MMU, which converts the virtual address into a physical address.

Standard memory pages on x86-64 are **4096 bytes** ($4\text{ KB} = 2^{12}\text{ bytes}$). A 48-bit canonical virtual address is decomposed into five distinct bitfields:

```
 47        39 38        30 29        21 20        12 11          0
+------------+------------+------------+------------+-------------+
| PML4 Index | PDPT Index |  PD Index  |  PT Index  | Page Offset |
|   9 Bits   |   9 Bits   |   9 Bits   |   9 Bits   |   12 Bits   |
+------------+------------+------------+------------+-------------+
```

1. **PML4 (Page Map Level 4)**: Bits 47–39 (9 bits = 512 entries). Points to the base of a PDPT.
2. **PDPT (Page Directory Pointer Table)**: Bits 38–30 (9 bits = 512 entries). Points to a Page Directory.
3. **PD (Page Directory)**: Bits 29–21 (9 bits = 512 entries). Points to a Page Table.
4. **PT (Page Table)**: Bits 20–12 (9 bits = 512 entries). Contains Page Table Entries (PTEs) holding the Physical Frame Base Address.
5. **Page Offset**: Bits 11–0 (12 bits = $0\text{ to } 4095$). Exact byte offset inside the 4KB physical frame.

The CPU's **`CR3` control register** stores the root physical address of the current process's PML4 table. During a context switch, the Linux kernel executes a single instruction to reload `CR3`, instantaneously switching the entire virtual memory mapping of the CPU.

---

## 2. Page Fault Physics: Minor vs Major Page Faults

When an instruction attempts to access a virtual address whose PTE has the **Present Bit** cleared (`P = 0`), the CPU hardware halts instruction execution and raises an **Interrupt Vector 14: Page Fault Exception (`#PF`)**. The hardware pushes the offending faulting virtual address into the **`CR2` register** and transfers control to the Linux kernel's page fault handler: `do_page_fault()`.

```
                        Virtual Memory Dereference
                                    |
                                    v
                         Is Present Bit Set (P=1)?
                                   / \
                             Yes  /   \  No
                                 /     \
                       Proceed to RAM    Raise Interrupt 14 (#PF)
                                         Store Address in CR2
                                                   |
                                                   v
                                      Kernel do_page_fault()
                                                   |
                      +----------------------------+----------------------------+
                      |                                                         |
                      v                                                         |
       Is address valid in process VMA?                                         |
            /                    \                                             |
      No   /                      \ Yes                                        |
          v                        v                                            |
   SIGSEGV Signal           Is backing page in RAM?                             |
  (Segmentation Fault)            /         \                                  |
                            Yes  /           \ No                              |
                                v             v                                 |
                         Minor Page Fault   Major Page Fault                    |
                         Link Physical Page Issue Block Disk I/O                |
                         Update PTE (P=1)   Suspend Task (D-State)              |
                         Execution Resumes  Load Frame -> Resume Execution      |
```

### 2.1 Minor Page Faults (Soft Faults)
A **minor page fault** occurs when the required physical page is already present in RAM, but the process's page table has not yet been linked to it. Scenarios include:
- **Demand Paging / Zero-Fill-On-Demand (ZFOD)**: When a process calls `malloc()` or `mmap(MAP_ANONYMOUS)`, the kernel immediately returns virtual memory space without allocating physical RAM. On the first write, a `#PF` occurs; the kernel grabs a zeroed physical frame, links it, and resumes the process. Latency: $\approx 0.5\text{ to } 2\text{ }\mu\text{s}$.
- **Copy-On-Write (COW)**: When `fork()` is called, parent and child share physical frames marked read-only. When either writes, `#PF` triggers a clone of that specific 4KB frame.

### 2.2 Major Page Faults (Hard Faults)
A **major page fault** occurs when the required page is not in physical RAM at all:
- The page was swapped out to disk.
- The page is part of a mapped executable or shared library that must be read from disk.
The kernel must issue synchronous disk I/O, putting the process into **Interruptible Sleep (`D-state`)**. On NVMe SSDs this introduces $10\text{ to } 50\text{ }\mu\text{s}$ of latency; on spinning HDDs, this takes $5\text{ to } 15\text{ milliseconds}$—a catastrophic $10,000\times$ latency penalty.

---

## 3. Page Cache, Anonymous Memory & Swap Reclaim Physics

Linux categorizes all allocated physical memory into two broad classifications:
1. **File-Backed Pages**: Pages backed by files on disk (executables, libraries, data files). These form the **Page Cache**. If physical memory becomes scarce, clean file-backed pages can be instantly discarded because they can be re-read from disk at any time.
2. **Anonymous Pages**: Pages not backed by any file (heap allocations, stack, process data structures). Anonymous memory cannot simply be discarded—if memory runs out, it must either be written to a dedicated **Swap Space** on disk, or the process must be terminated by the Out-Of-Memory (OOM) killer.

### 3.1 The Page Replacement Algorithm: Active vs Inactive LRU Lists
The Linux kernel maintains dual Least-Recently-Used (LRU) linked lists:
- **Active List**: Frequently referenced pages.
- **Inactive List**: Candidate pages for reclamation.

A background kernel daemon called **`kswapd`** continuously monitors memory pressure using three watermarks:
- `pages_high`: Memory is plentiful; `kswapd` sleeps.
- `pages_low`: Memory pressure begins; `kswapd` wakes up and starts scanning inactive lists in the background.
- `pages_min`: Emergency threshold; processes that allocate memory are forced into **Direct Reclaim**, stalling CPU execution to free pages synchronously.

### 3.2 The Swappiness Formula
The kernel parameter `/proc/sys/vm/swappiness` (ranging from $0$ to $200$, default $60$) dictates how aggressively `kswapd` reclaims anonymous pages vs file-backed page cache:

$$\text{Reclaim Ratio} = \frac{\text{scan\_anon}}{\text{scan\_file}} = \frac{\text{swappiness} \times \Delta \text{anon}}{(200 - \text{swappiness}) \times \Delta \text{file}}$$

- `swappiness = 0`: Avoid swapping anonymous pages unless absolutely mandatory to avoid an OOM crash.
- `swappiness = 60`: Balanced reclamation between page cache eviction and swapping.
- `swappiness = 100`: Kernel treats anonymous memory and file cache with equal priority for reclamation.

---

## 4. Deep-Dive: Dissecting `vmstat` Output

The `vmstat` (Virtual Memory Statistics) utility provides instantaneous visibility into process queues, virtual memory, paging, block I/O, interrupts, and CPU utilization.

```bash
$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 2  0  65536 215480  84210 1845120    0    0    12    45  150  420  5  2 92  1  0
```

### Field-by-Field Breakdown:
1. **`procs`**:
   - `r` (**Run Queue**): Number of runnable threads waiting for CPU time. If $r > \text{CPU cores}$, the system is CPU-saturated.
   - `b` (**Blocked Queue**): Number of processes in uninterruptible sleep (`D-state`), almost exclusively waiting on synchronous disk I/O or NFS locks.
2. **`memory`**:
   - `swpd`: Total amount of virtual memory currently swapped to disk (in KB).
   - `free`: Unallocated memory frames.
   - `buff`: Memory used by temporary filesystem buffers for raw disk blocks.
   - `cache`: Memory used by the Page Cache for reading and writing files.
3. **`swap`**:
   - `si` (**Swap-In**): Rate of memory paged in from swap disk per second (in KB/s). **High `si` indicates active thrashing.**
   - `so` (**Swap-Out**): Rate of memory paged out to swap disk per second (in KB/s).
4. **`io`**:
   - `bi` (**Blocks In**): Blocks received from block devices (in blocks/s).
   - `bo` (**Blocks Out**): Blocks sent to block devices (in blocks/s).
5. **`system`**:
   - `in`: Hardware interrupts per second.
   - `cs`: Context switches per second.
6. **`cpu`**:
   - `us`: User space CPU percentage.
   - `sy`: Kernel space (system) CPU percentage.
   - `id`: Idle CPU percentage.
   - `wa`: I/O Wait percentage—time CPU spent idle while blocked on pending I/O.
   - `st`: Steal time—CPU cycles stolen by the hypervisor in virtualized environments.

---

## 5. Compilable C Implementation: Inspecting Page Residency with `mincore()`

The following complete, compilable C program demonstrates virtual memory allocation with `mmap()`, triggers minor page faults, and uses the `mincore()` system call to inspect whether pages are physically resident in RAM.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>
#include <fcntl.h>

int main() {
    long page_size = sysconf(_SC_PAGESIZE);
    size_t num_pages = 4;
    size_t total_size = num_pages * page_size;

    printf("[+] System Page Size: %ld bytes\n", page_size);

    // 1. Allocate virtual address space with MAP_ANONYMOUS (Lazy Allocation)
    char *addr = mmap(NULL, total_size, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (addr == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    printf("[+] Allocated %zu bytes at virtual address %p\n", total_size, (void*)addr);

    // Vector to store residency status of each page
    unsigned char vec[num_pages];

    // 2. Inspect physical residency BEFORE writing (Expect zero pages in RAM)
    if (mincore(addr, total_size, vec) == -1) {
        perror("mincore");
        return 1;
    }
    printf("\n[+] Physical residency BEFORE touch:\n");
    for (size_t i = 0; i < num_pages; i++) {
        printf("    Page %zu: %s\n", i, (vec[i] & 1) ? "RESIDENT IN RAM" : "NOT RESIDENT (ZFOD)");
    }

    // 3. Touch Page 0 and Page 2 (Triggering Minor Page Faults)
    printf("\n[+] Touching (writing to) Page 0 and Page 2...\n");
    addr[0 * page_size] = 'A';
    addr[2 * page_size] = 'C';

    // 4. Inspect physical residency AFTER writing
    if (mincore(addr, total_size, vec) == -1) {
        perror("mincore");
        return 1;
    }
    printf("\n[+] Physical residency AFTER touch:\n");
    for (size_t i = 0; i < num_pages; i++) {
        printf("    Page %zu: %s\n", i, (vec[i] & 1) ? "RESIDENT IN RAM" : "NOT RESIDENT (ZFOD)");
    }

    // Clean up
    munmap(addr, total_size);
    printf("\n[+] Cleaned up memory mappings.\n");
    return 0;
}
```

---

## 6. Production War Story: The Database Thrashing Collapse

In a major production FinTech cluster running a 128 GB PostgreSQL master, system monitoring suddenly alerted on API latency spiking from $2\text{ ms}$ to over $3,500\text{ ms}$. CPU utilization dropped to $4\%$, while load average exploded to $142$.

### Root Cause Analysis
Running `vmstat 1` immediately revealed the smoking gun:
- `r = 1`, `b = 48` (48 database worker threads stuck in `D-state`).
- `si = 85,000 KB/s`, `so = 92,000 KB/s` (Massive, non-stop memory thrashing).
- `wa = 88%` (CPUs were completely starved waiting on disk I/O).

A rogue reporting query had executed a memory-intensive unindexed aggregation, pushing anonymous memory allocations beyond available physical RAM. Because `/proc/sys/vm/swappiness` was set to the default value of `60`, `kswapd` began aggressively evicting active database shared buffers to swap space on NVMe storage. When subsequent transactional queries requested pages from the buffer pool, they encountered **major page faults**, reading pages back from swap at NVMe disk speeds instead of RAM bus speeds.

### The Remediation
1. **Immediate Triage**: `sysctl -w vm.swappiness=1` prevented further swapping of active anonymous memory while keeping emergency swap enabled to prevent OOM panic.
2. **Buffer Pinning**: Configured PostgreSQL's shared buffers with huge pages (`vm.nr_hugepages` and `huge_pages = on`), making database memory completely unswappable.
3. **Permanent Fix**: Implemented Linux Cgroups v2 with `memory.min` memory guarantees to protect the database daemon from reclaim pressure.
