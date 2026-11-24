# Day 11: Virtual Memory, Page Tables & Swap (vmstat)

## 1. Architectural Foundations: Virtual Memory & Address Translation

In modern multi-tasking operating systems, no user-space process ever accesses physical RAM directly. Instead, every single process executes inside its own private, isolated, and uniform **Virtual Address Space**. On x86-64 Linux, this virtual address space spans an astronomical $2^{48}$ bytes ($256\text{ TB}$) in standard 4-level paging mode, or $2^{57}$ bytes ($128\text{ PB}$) in modern 5-level paging mode (PAGING57).

The architectural motivations for virtual memory are threefold:
1. **Hardware-Enforced Memory Protection**: Process $A$ cannot read, corrupt, or hijack the memory of Process $B$. Furthermore, user-space code executing in CPU Ring 3 is physically barred by the hardware Memory Management Unit (MMU) from touching kernel memory mapped in Ring 0.
2. **Contiguous Abstraction of Non-Contiguous Physical Storage**: A process can allocate a contiguous $10\text{ GB}$ buffer. The underlying physical page frames in RAM can be scattered randomly across memory banks or even paged out to disk swap space.
3. **Transparent Memory Sharing**: Multiple running instances of `/usr/bin/python3` or applications dynamically linking `libc.so.6` share the exact same physical memory frames for their executable text segments, saving gigabytes of physical RAM.

```
+-------------------------------------------------------------------------+
|                  x86-64 Virtual Address Space Layout (48-Bit)           |
+-------------------------------------------------------------------------+
| 0xFFFFFFFFFFFFFFFF +--------------------------------------------------+ |
|                    | Kernel Space (128 TB) - Higher Half Mapping      | |
| 0xFFFF800000000000 +--------------------------------------------------+ |
|                    | Non-Canonical Hole (Guard Space, 16.7 Million TB)| |
|                    | Dereferencing addresses here triggers #GP (Fault)| |
| 0x00007FFFFFFFFFFF +--------------------------------------------------+ |
|                    | Stack (Grows downward toward lower addresses)    | |
|                    |   |                                              | |
|                    |   v                                              | |
|                    | Memory Mapping Segment (mmap, shared libraries)  | |
|                    |   ^                                              | |
|                    |   |                                              | |
|                    | Heap (Grows upward via brk/sbrk)                 | |
|                    | BSS Segment (Uninitialized Static Variables)     | |
|                    | Data Segment (Initialized Static Variables)      | |
|                    | Text Segment (Compiled Executable Machine Code)  | |
| 0x0000000000000000 +--------------------------------------------------+ |
+-------------------------------------------------------------------------+
```

### 1.1 The Hardware MMU & 4-Level Page Table Traversal
The central processing unit (CPU) contains a specialized hardware circuit called the **Memory Management Unit (MMU)**. Every single memory access instruction in assembly (such as `movq (%rdi), %rax` or `pushq %rbp`) operates on a **virtual address**. The MMU must translate this virtual address into a **physical memory address** before asserting the address lines on the DDR4/DDR5 memory bus.

On x86-64, physical memory is partitioned into uniform blocks called **Page Frames**, standardly **4096 bytes** ($4\text{ KB} = 2^{12}\text{ bytes}$). A 48-bit canonical virtual address is mathematically decomposed into five distinct bitfields:

```
 47        39 38        30 29        21 20        12 11          0
+------------+------------+------------+------------+-------------+
| PML4 Index | PDPT Index |  PD Index  |  PT Index  | Page Offset |
|   9 Bits   |   9 Bits   |   9 Bits   |   9 Bits   |   12 Bits   |
+------------+------------+------------+------------+-------------+
  (512 Ent.)   (512 Ent.)   (512 Ent.)   (512 Ent.)   (4096 Bytes)
```

1. **PML4 (Page Map Level 4)**: Bits 47–39 (9 bits = $2^9 = 512$ entries). Each entry is an 8-byte pointer holding the physical base address of a Page Directory Pointer Table (PDPT).
2. **PDPT (Page Directory Pointer Table)**: Bits 38–30 (9 bits = 512 entries). Points to the physical base address of a Page Directory (PD).
3. **PD (Page Directory)**: Bits 29–21 (9 bits = 512 entries). Points to the physical base address of a Page Table (PT).
4. **PT (Page Table)**: Bits 20–12 (9 bits = 512 entries). Contains the final **Page Table Entries (PTE)**, which store the physical address of the actual 4KB RAM frame.
5. **Page Offset**: Bits 11–0 (12 bits = $2^{12} = 4096$ values). Specifies the exact byte offset ($0\text{ to } 4095$) within the target physical page frame.

### 1.2 The `CR3` Register and Context Switch Overhead
The CPU's control register **`CR3`** holds the root physical memory address of the active process's PML4 table. 
When the Linux kernel scheduler (`schedule()`) switches execution from Process $A$ to Process $B$, it executes a single privileged assembly instruction:
```assembly
movq %rax, %cr3   ; Reload CR3 with Process B's PML4 base physical address
```
Reloading `CR3` instantaneously switches the entire active virtual memory universe of the CPU. However, this comes with a severe microarchitectural penalty: **it flushes the Translation Lookaside Buffer (TLB)**, invalidating cached translations and forcing the MMU to perform full 4-level memory walks on subsequent memory accesses.

---

## 2. Anatomy of a 64-Bit Page Table Entry (PTE)

Every Page Table Entry (PTE) is an 8-byte (64-bit) bitfield structured directly by x86-64 hardware specifications:

```
 63  62           52 51                               12 11  9 8 7 6 5 4 3 2 1 0
+---+---------------+-----------------------------------+-----+-+-+-+-+-+-+-+-+-+
| X |   Available   |    Physical Page Frame Address    | Ign |G|P|D|A|P|P|U|R|P|
| D |  (for OS use) |          (Bits 51 - 12)           |     | |A| | |C|W|/|/| |
|   |               |                                   |     | |T| | |D|T|S|W| |
+---+---------------+-----------------------------------+-----+-+-+-+-+-+-+-+-+-+
```

### Bitfield Descriptions:
- **Bit 0 (`P` - Present)**: Must be `1` if the page is currently resident in physical RAM. If `0`, accessing this page raises a hardware **Page Fault Exception (`#PF`, Interrupt 14)**.
- **Bit 1 (`R/W` - Read/Write)**: If `1`, write operations are permitted. If `0`, writes trigger a `#PF` (used for Read-Only code segments and Copy-On-Write memory).
- **Bit 2 (`U/S` - User/Supervisor)**: If `1`, user-space code (Ring 3) can access this page. If `0`, access is restricted to kernel mode (Ring 0).
- **Bit 3 (`PWT` - Page-Level Write-Through)**: Dictates CPU L1/L2/L3 cache write-through vs write-back caching.
- **Bit 4 (`PCD` - Page-Level Cache Disable)**: Disables CPU caching entirely (used for Memory-Mapped I/O hardware registers).
- **Bit 5 (`A` - Accessed)**: Set to `1` by CPU hardware whenever the page is read or written. Used by the Linux `kswapd` daemon to track active memory pages.
- **Bit 6 (`D` - Dirty)**: Set to `1` by CPU hardware whenever a write operation modifies data within the page frame.
- **Bit 7 (`PAT` / `PS` - Page Size)**: In PDPT or PD entries, setting this bit enables **Huge Pages** ($2\text{ MB}$ or $1\text{ GB}$ pages), bypassing lower page table levels.
- **Bit 8 (`G` - Global)**: Prevents the TLB translation from being invalidated when `CR3` is reloaded during context switches (used for kernel mappings).
- **Bits 51–12 (`Physical Page Base Address`)**: The 40-bit physical frame number (aligned to 4KB).
- **Bit 63 (`XD` / `NX` - Execute-Disable / No-Execute)**: Hardware security bit. If `1`, any attempt by the CPU instruction pointer (`%rip`) to execute code from this memory page triggers a hardware exception. This is the hardware foundation of **W^X (Write XOR Execute)**, preventing stack buffer overflow shellcode execution.

---

## 3. Page Fault Physics: Step-by-Step Kernel Flow

When an assembly instruction dereferences a virtual address whose PTE has `P = 0`, or violates access permissions (e.g. writing to a page with `R/W = 0`), the CPU hardware immediately suspends instruction execution and executes an interrupt:

```
                            Assembly Instruction: movq (%rdi), %rax
                                             |
                                             v
                           MMU Page Table Hardware Traversal
                                             |
                               Is Present Bit (P) == 1?
                                       /       \
                                 Yes  /         \  No (P = 0)
                                     /           \
                     Check Permissions (R/W, U/S)  CPU Halts Instruction
                            /          \          Pushes Virtual Address to CR2
                      Valid/            \Invalid  Pushes Error Code to Stack
                          v              v         Asserts Interrupt Vector 14 (#PF)
                     Read RAM       Raise #PF                      |
                                                                   v
                                                    Kernel do_page_fault() Entry
                                                                   |
                                  +--------------------------------+--------------------------------+
                                  |                                                                 |
                                  v                                                                 v
                    Is virtual address inside a                     Is virtual address outside any
                    valid struct vm_area_struct (VMA)?              registered VMA segment?
                                  |                                                 |
                                  | Yes                                             v
                                  v                                       Kernel Sends SIGSEGV
                    Is physical frame in Page Cache?                    (Segmentation Fault, Core Dump)
                               /            \
                         Yes  /              \ No
                             v                v
                     MINOR PAGE FAULT        MAJOR PAGE FAULT
                     (Zero-Fill-On-Demand    (Issue synchronous Block I/O read)
                      or Copy-On-Write)      (Task moves to D-State uninterruptible sleep)
                             |               (Block driver loads 4KB frame into RAM)
                             v                                      |
                     Link physical frame                            v
                     Set PTE bit P = 1                       Update PTE (P=1)
                     Flush local TLB                         Wake up Task -> Move to R-State
                     Resume instruction                      Re-execute faulting instruction
```

### 3.1 Minor (Soft) Page Faults
A **minor page fault** requires zero disk I/O. The kernel resolves the fault entirely within CPU and memory bus registers:
1. **Zero-Fill-On-Demand (ZFOD)**: When a process calls `malloc(1024*1024*100)` ($100\text{ MB}$), `glibc` calls `mmap(MAP_ANONYMOUS)`. The kernel does **not** allocate physical RAM. It simply creates an internal metadata structure (`struct vm_area_struct`) registering the address range. When the process actually writes to byte `addr[0]`, the CPU encounters `P=0`, raises `#PF`, and the kernel links a physical zeroed 4KB frame to the PTE.
2. **Copy-On-Write (COW)**: After `fork()`, parent and child processes share the exact same physical memory frames with their PTEs marked Read-Only (`R/W = 0`). The moment either process writes to a variable, `#PF` triggers. The kernel allocates a new physical frame, copies the 4096 bytes from the original frame, updates the writing process's PTE to point to the new frame with `R/W = 1`, and resumes execution.

### 3.2 Major (Hard) Page Faults
A **major page fault** occurs when the required memory page is not present anywhere in physical RAM:
- The page belongs to an executable binary or shared library (`.so`) that has not yet been paged into the Page Cache from disk.
- The page was an anonymous memory page that was evicted and compressed into Swap space on NVMe/SSD/HDD storage.
The kernel must suspend the faulting thread, moving its state to **`TASK_UNINTERRUPTIBLE` (`D-state`)**, and issue asynchronous block I/O commands to the disk driver. On high-speed NVMe storage, this introduces $10\text{ to } 50\text{ microseconds}$ of latency; on rotational spinning disks, it takes $5\text{ to } 15\text{ milliseconds}$ ($10,000\times$ slower than RAM).

---

## 4. Linux Memory Management Architecture: Zones, LRU Lists & Swappiness

Physical RAM is partitioned by the kernel into hardware-constrained **Memory Zones**:
- **`ZONE_DMA`**: Lower 16 MB of physical RAM (legacy ISA device DMA addressing).
- **`ZONE_DMA32`**: 16 MB to 4 GB (32-bit PCI device DMA addressing).
- **`ZONE_NORMAL`**: Directly addressable physical memory on 64-bit architectures.
- **`ZONE_MOVABLE`**: Hot-pluggable memory that can be compacted or removed.

### 4.1 Page Cache vs Anonymous Memory
All allocated memory in Linux belongs to one of two categories:
1. **File-Backed Memory (Page Cache)**: Pages created by reading and writing files (`read()`, `write()`, `mmap()`). Because these pages have a permanent home on disk, the kernel can discard "clean" (unmodified) pages instantly under memory pressure without writing them anywhere.
2. **Anonymous Memory**: Memory created by application heaps, stacks, and `mmap(MAP_ANON)`. These pages have no backing file. If the system runs low on RAM, anonymous pages cannot be discarded—they must either be written to a dedicated **Swap Space** on disk, or the process must be terminated.

### 4.2 The Active vs Inactive Dual-LRU Eviction Engine
The Linux kernel maintains two doubly linked lists of memory pages for both file-backed and anonymous memory:
- **`Active List`**: Pages that have been accessed recently (PTE Accessed bit `A = 1`).
- **`Inactive List`**: Pages that have not been accessed recently, making them prime candidates for reclamation.

A background kernel daemon named **`kswapd`** monitors three physical memory watermarks defined per zone:
- **`watermark[WMARK_HIGH]`**: Memory is abundant; `kswapd` sleeps.
- **`watermark[WMARK_LOW]`**: Memory pressure begins; `kswapd` wakes up and begins scanning the inactive lists in the background to free pages before allocations fail.
- **`watermark[WMARK_MIN]`**: Emergency threshold; background reclamation is too slow. User-space allocating processes are forced into **Direct Reclaim**, stalling CPU execution to reclaim memory synchronously before completing memory requests.

### 4.3 The Swappiness Mathematical Ratio
The kernel parameter `/proc/sys/vm/swappiness` (integer between $0$ and $200$, default $60$) dictates how aggressively `kswapd` scans anonymous memory vs file-backed page cache:

$$\text{Scan Ratio} = \frac{\text{scan\_anon}}{\text{scan\_file}} = \frac{\text{swappiness} \times \Delta \text{anon}}{(200 - \text{swappiness}) \times \Delta \text{file}}$$

- `swappiness = 0`: The kernel will never swap anonymous pages unless memory drops below `WMARK_MIN` (avoiding OOM panic).
- `swappiness = 60`: Standard desktop/server default; balanced eviction between page cache and swap.
- `swappiness = 100`: Kernel considers anonymous pages and file-backed pages completely equal for eviction.

---

## 5. Dissecting `vmstat` Field by Field

The `vmstat` (Virtual Memory Statistics) utility provides an instantaneous overview of processes, virtual memory, paging, block I/O, system interrupts, and CPU utilization.

```bash
$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 3  1  65536 215480  84210 1845120    0    0    12    45  150  420  8  4 85  3  0
```

### Complete Column Definitions:
1. **`procs`**:
   - `r` (**Runnable Queue**): Number of threads either currently executing on a CPU core or waiting in the scheduler's runqueue. If $r$ consistently exceeds the total number of physical CPU cores, the host is suffering from severe CPU saturation.
   - `b` (**Blocked Queue**): Number of threads stuck in `TASK_UNINTERRUPTIBLE` sleep (`D-state`), almost exclusively waiting on synchronous disk I/O, page faults, or NFS locks.
2. **`memory`**:
   - `swpd`: Amount of virtual memory currently written to swap partition/file (in KB).
   - `free`: Completely idle, unallocated physical memory frames (in KB).
   - `buff`: Memory used by temporary buffer cache holding raw disk block metadata.
   - `cache`: Memory used by the Page Cache holding file contents read from disk.
3. **`swap`**:
   - `si` (**Swap-In**): Rate of memory paged in from swap disk per second (in KB/s). **A non-zero `si` value combined with high `wa` indicates active memory thrashing!**
   - `so` (**Swap-Out**): Rate of memory paged out to swap disk per second (in KB/s).
4. **`io`**:
   - `bi` (**Blocks In**): Blocks received from physical storage devices per second (1 block $\approx 1024\text{ bytes}$).
   - `bo` (**Blocks Out**): Blocks written to physical storage devices per second.
5. **`system`**:
   - `in`: Hardware interrupts per second, including timer ticks, disk IRQs, and network NIC interrupts.
   - `cs`: Context switches per second between different processes and kernel threads.
6. **`cpu`**:
   - `us`: Percentage of CPU time spent executing user-space code (Ring 3).
   - `sy`: Percentage of CPU time spent executing kernel-space code (Ring 0).
   - `id`: Percentage of CPU time spent completely idle.
   - `wa` (**I/O Wait**): Percentage of CPU time where CPU was idle *while* at least one local thread was blocked waiting on disk I/O.
   - `st` (**Steal Time**): Percentage of CPU time stolen by the hypervisor in virtualized environments (KVM, AWS EC2, VMware) to service other virtual machines.

---

## 6. Complete Compilable C Program: Low-Level Virtual Memory Allocation & `mincore()` Inspection

The following complete, standalone C program demonstrates virtual memory allocation using `mmap()`, proves lazy allocation (Zero-Fill-On-Demand), triggers minor page faults, and uses the Linux `mincore()` system call to inspect whether pages are physically resident in RAM.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <errno.h>
#include <string.h>

int main(void) {
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size == -1) {
        perror("sysconf(_SC_PAGESIZE)");
        return EXIT_FAILURE;
    }
    printf("[+] System Architecture Page Size: %ld bytes (4 KB)\n", page_size);

    size_t num_pages = 4;
    size_t total_bytes = num_pages * page_size;

    // 1. Allocate virtual address space with mmap (Lazy Allocation)
    // MAP_PRIVATE | MAP_ANONYMOUS allocates unbacked memory initialized to zero
    char *virtual_buffer = mmap(
        NULL,
        total_bytes,
        PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS,
        -1,
        0
    );

    if (virtual_buffer == MAP_FAILED) {
        perror("mmap");
        return EXIT_FAILURE;
    }

    printf("[+] Virtual Memory Allocated: %zu bytes at base address: %p\n", 
           total_bytes, (void *)virtual_buffer);

    // Vector to store page residency status (1 byte per page)
    unsigned char residency_vector[num_pages];
    memset(residency_vector, 0, sizeof(residency_vector));

    // 2. Query page residency BEFORE touching the memory
    if (mincore(virtual_buffer, total_bytes, residency_vector) == -1) {
        perror("mincore");
        munmap(virtual_buffer, total_bytes);
        return EXIT_FAILURE;
    }

    printf("\n[+] Physical RAM Residency Status BEFORE touch (Zero-Fill-On-Demand):\n");
    for (size_t i = 0; i < num_pages; i++) {
        int is_resident = residency_vector[i] & 1;
        printf("    Page %zu (Addr: %p): %s\n", 
               i, 
               (void *)(virtual_buffer + (i * page_size)),
               is_resident ? "RESIDENT IN PHYSICAL RAM" : "UNALLOCATED (Virtual Only)");
    }

    // 3. Touch (write to) Page 0 and Page 2 only (Triggers Minor Page Faults)
    printf("\n[+] Writing to Page 0 and Page 2 (Triggering Minor Page Faults in MMU)...\n");
    virtual_buffer[0 * page_size] = 'P'; // Accessing Page 0
    virtual_buffer[2 * page_size] = 'X'; // Accessing Page 2

    // 4. Query page residency AFTER touching the memory
    if (mincore(virtual_buffer, total_bytes, residency_vector) == -1) {
        perror("mincore");
        munmap(virtual_buffer, total_bytes);
        return EXIT_FAILURE;
    }

    printf("\n[+] Physical RAM Residency Status AFTER touch:\n");
    for (size_t i = 0; i < num_pages; i++) {
        int is_resident = residency_vector[i] & 1;
        printf("    Page %zu (Addr: %p): %s\n", 
               i, 
               (void *)(virtual_buffer + (i * page_size)),
               is_resident ? "RESIDENT IN PHYSICAL RAM" : "UNALLOCATED (Virtual Only)");
    }

    // 5. Clean up memory mappings
    if (munmap(virtual_buffer, total_bytes) == -1) {
        perror("munmap");
        return EXIT_FAILURE;
    }
    printf("\n[+] Successfully unmapped virtual memory.\n");

    return EXIT_SUCCESS;
}
```

---

## 7. Production War Story: The Database Memory Thrashing Collapse

In an enterprise e-commerce platform processing 10,000 transactions per second, the primary PostgreSQL database cluster suddenly collapsed during Black Friday. Application response times spiked from $4\text{ ms}$ to over $3,800\text{ ms}$.

### The Diagnostic Triage
Running `uptime` revealed that the 64-core database server had a load average of **184.2**! However, executing `top` showed that CPU user space utilization was only **2%**. 
Running `vmstat 1` exposed the exact failure mode:
```
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 2 58 4194304 112000  12400 4812000 84000 92000 84200 92400 1200 4800  2  5  0 93  0
```
- **`b = 58`**: 58 database worker processes were frozen in `D-state` (uninterruptible sleep).
- **`wa = 93%`**: The CPUs were completely stalled waiting for NVMe storage to complete I/O.
- **`si = 84,000 KB/s` / `so = 92,000 KB/s`**: The kernel was violently thrashing, swapping 84 MB in and 92 MB out of disk swap every single second!

### Root Cause Analysis
A marketing analyst had initiated an unindexed analytic query spanning 500 million records. PostgreSQL allocated memory via `work_mem` across multiple parallel worker threads, pushing anonymous memory allocations past physical RAM limits. Because `/proc/sys/vm/swappiness` was left at the default value of `60`, the kernel's `kswapd` daemon began aggressively evicting active PostgreSQL shared buffer pages to disk swap. When transactional queries attempted to read tables, every memory lookup encountered a **major page fault**, converting sub-nanosecond RAM dereferences into 20-millisecond NVMe block reads.

### The Immediate & Long-Term Fixes:
1. **Emergency Triage**: Executed `sysctl -w vm.swappiness=1` to force `kswapd` to aggressively evict file-backed Page Cache rather than touching anonymous database buffer memory.
2. **Huge Pages Architecture**: Configured PostgreSQL to use **Transparent Huge Pages (THP) disabled** and preallocated static **Explicit Huge Pages (2 MB pages)**:
   ```bash
   sysctl -w vm.nr_hugepages=32768  # 32768 x 2MB = 64 GB pinned memory
   ```
   Huge pages are permanently pinned in physical RAM and can **never be swapped to disk**, providing immunity against memory thrashing.
3. **Cgroup V2 Memory Min Protection**: Placed PostgreSQL into a systemd slice with `MemoryMin=64G`, legally obligating the Linux kernel to never reclaim memory from the database process under any circumstances.
