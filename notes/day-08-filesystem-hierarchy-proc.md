# Day 08: Linux Filesystem Hierarchy Standard (FHS) & The Virtual Filesystem (`/proc` & `/sys`)

> **Zero External Dependency Guarantee**: This document is an encyclopedic, self-contained masterclass. It contains complete historical origins, real-world mental models, VFS `dcache` and `inode` caching physics, the kernel `seq_file` dynamic generation engine, complete FHS 3.0 directory taxonomy, `/proc/meminfo` telemetry mathematics, file descriptor recovery forensics, production monitoring crashes, and FAANG staff-level interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & The Core Mental Model

The Linux Filesystem Hierarchy Standard (FHS 3.0) unifies all system storage under a single rooted tree (`/`). Unlike legacy operating systems that assign arbitrary drive letters (`C:`, `D:`) to physical storage controllers, Linux abstracts all physical storage devices, network shares, kernel state variables, and hardware peripherals into a single, unified namespace through the **Virtual File System (VFS)**.

### The Hospital ICU Real-World Analogy:
Imagine walking into an ultra-modern hospital:
* The **Medical Records Warehouse** (disk drives: `/home`, `/var`, `/etc`) contains permanent paper charts filed in physical drawers. If the power shuts off, the paper files remain on physical shelves.
* The **ICU Vital Signs Monitor** (`/proc` and `/sys`) does **not** store paper. It is an illuminated glass screen showing live heart rate, blood oxygen, and intracranial pressure in real time. If you tap the screen, you aren't pulling a sheet of paper from a shelf; you are reading current electrical sensors straight from the patient's body!

In Linux, **everything is exposed through the filesystem interface**. But not every file lives on a magnetic platter or NVMe flash chip! The Linux kernel exposes its internal runtime state, memory tables, process registers, and hardware topology as pseudo-filesystems: `/proc` (process and kernel metrics) and `/sys` (device drivers and bus topology). When you read `/proc/cpuinfo`, no disk head moves—the CPU directly executes kernel code that formats its internal registers into an ASCII text stream on the fly!

```
THE VFS UNIFIED TREE ABSTRACTION:
                                 / (Root VFS Inode)
                                 |
        +----------------+-------+--------+----------------+
        |                |                |                |
     /bin, /usr        /etc             /dev             /proc
(Physical Disk: ext4) (Local Config) (Virtual Devices) (Virtual Kernel RAM)
```

---

## 2. Low-Level Kernel Architecture: VFS, Dentry Caches & `seq_file`

When userspace applications issue POSIX system calls like `open()`, `read()`, and `stat()`, the calls traverse the **Virtual File System (VFS)** layer.

```
+-----------------------------------------------------------------------------------+
|                           USERSPACE APPLICATIONS                                  |
|                 (cat /proc/meminfo, htop, ps, nginx, postgres)                     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v  POSIX open(), read(), write(), close()
+-----------------------------------------------------------------------------------+
|                        VFS (Virtual File System Layer)                            |
|             Translates universal POSIX syscalls into specific driver hooks         |
+-----------------------------------------------------------------------------------+
       |                                   |                                |
       v                                   v                                v
+------------------+             +-------------------+             +----------------+
|  ext4 / xfs / btrfs|            |      procfs       |             |     sysfs      |
|  Physical Storage|             | (Dynamic Kernel   |             | (Hardware/Bus  |
|  (SATA/NVMe SSD) |             |  Memory State)    |             |  Driver Tree)  |
+------------------+             +-------------------+             +----------------+
```

### 2.1 The VFS Inode and Dentry Caches
When you resolve a path like `/var/log/syslog`, the kernel does not search physical disk sectors sequentially. Instead, the VFS maintains an in-memory acceleration layer:
1. **`struct super_block` (`include/linux/fs.h`)**: Represents an entire mounted filesystem. Stores block size, total inodes, and filesystem root pointer.
2. **`struct inode`**: Represents a specific file or directory on storage. Stores file size, permissions, timestamps, and data block pointers. Crucially: **An inode does NOT contain the file's name!**
3. **`struct dentry` (Directory Entry)**: Binds a human-readable file or directory name string (e.g., `"syslog"`) to its numerical `struct inode` pointer.
   - Dentries are cached in physical RAM in the **dcache**.
   - Path resolution utilizes lockless **RCU (Read-Copy-Update)** lookups, resolving complex nested paths in nanoseconds without taking locks!

### 2.2 How `procfs` Synthesizes Files: The `seq_file` Interface (`fs/seq_file.c`)
In a physical filesystem like `ext4`, an inode points to physical disk sectors. In the Virtual File System (VFS), an inode contains a table of function pointers: `struct file_operations`.

```c
/* Simplified Linux Kernel VFS File Operations Struct */
struct file_operations {
    struct module *owner;
    loff_t (*llseek) (struct file *, loff_t, int);
    ssize_t (*read) (struct file *, char __user *, size_t, loff_t *);
    ssize_t (*write) (struct file *, const char __user *, size_t, loff_t *);
    int (*open) (struct inode *, struct file *);
    int (*release) (struct inode *, struct file *);
};
```

When you inspect a pseudo-file like `/proc/cpuinfo`:
```bash
ls -l /proc/cpuinfo
# Output: -r--r--r-- 1 root root 0 Nov 23 10:00 /proc/cpuinfo
```
The file reports a size of **0 bytes**. Yet, when you run `cat /proc/cpuinfo`, you receive several kilobytes of processor telemetry!
* **The Reason**: The kernel does not know how many bytes `/proc/cpuinfo` will output until it queries the hardware. Calculating the character length ahead of time would waste CPU cycles.
* When userspace calls `read()`, the kernel invokes `seq_read()`, which dynamically allocates a temporary page buffer, calls the driver's show function (`cpuinfo_op.show`), formats the text into ASCII via `seq_printf()`, and streams it to userspace!

---

## 3. The Linux Filesystem Hierarchy Standard (FHS 3.0)

Every directory in the Linux root (`/`) serves a deterministic, architecturally defined purpose:

| Directory | Full Name / Meaning | Primary Purpose | Persistent Across Reboots? |
| :--- | :--- | :--- | :---: |
| **`/`** | Root | Top of the entire hierarchical tree. Every path branches from here. | Yes |
| **`/bin`** | Essential User Binaries | Core commands required for single-user recovery mode (`cat`, `ls`, `cp`, `sh`). In modern Linux, symlinked to `/usr/bin`. | Yes |
| **`/sbin`**| System Binaries | Administrative tools used by root for booting and repairing (`fdisk`, `iptables`, `ip`). Symlinked to `/usr/sbin`. | Yes |
| **`/etc`** | Editable Text Configurations | System-wide static configuration files (`/etc/passwd`, `/etc/fstab`, `/etc/hosts`). Strictly text files—no binaries! | Yes |
| **`/dev`** | Device Nodes | Virtual device interface files created by `udev` (`/dev/sda`, `/dev/null`, `/dev/urandom`). | No (Recreated on boot) |
| **`/proc`**| Process Information | Live kernel and process state metrics. Memory-backed virtual pseudo-filesystem (`procfs`). | No (Pure RAM) |
| **`/sys`** | System & Hardware | Unified kernel device driver and bus topology model (`sysfs`). Modern companion to `/proc`. | No (Pure RAM) |
| **`/var`** | Variable Data | Dynamic, continuously growing operational files: spoolers, databases, caches, and system logs (`/var/log`). | Yes |
| **`/tmp`** | Temporary Files | Ephemeral scratch directory accessible by all users. Often mounted on `tmpfs` (RAM). Emptied on reboot. | No |
| **`/usr`** | Universal System Resources | Secondary hierarchy containing the bulk of installed software, shared libraries (`/usr/lib`), and headers (`/usr/include`). | Yes |
| **`/home`**| User Home Directories | Personal storage for non-root users (`/home/username`). Stores personal dotfiles (`.bashrc`). | Yes |
| **`/root`**| Root User Home | Home directory for the administrative `root` superuser (kept separate from `/home` in case `/home` fails to mount). | Yes |
| **`/boot`**| Bootloader Files | Linux kernel binary (`vmlinuz`), initial RAM disk (`initramfs`), and GRUB configuration. | Yes |
| **`/opt`** | Optional Third-Party Packages| Self-contained proprietary software suites (e.g., `/opt/google/chrome`, `/opt/slack`). | Yes |
| **`/run`** | Runtime Data | Ephemeral runtime state since system boot: active PID files, domain sockets (`/run/systemd/`). Mounted on `tmpfs`. | No |

---

## 4. Deep-Dive: Exploring `/proc` Internals

The `/proc` directory divides cleanly into **System-Wide Metrics** and **Per-Process Metrics (`/proc/<PID>/`)**.

### 4.1 System-Wide Metrics

#### A. `/proc/meminfo` & The True Available Memory Equation
Software engineers frequently misread memory usage because they equate `MemFree` with available capacity.
```
PHYSICAL RAM DECOMPOSITION:
+-------------------------------------------------------------------------+
|                         TOTAL PHYSICAL RAM (MemTotal)                   |
+-------------------+-------------------+---------------------------------+
| Used by Processes | Linux Page Cache  | Actual Free Memory              |
| (AnonPages)       | (Buffers+Cached)  | (MemFree)                       |
| Cannot be evicted | EVICTABLE ON DEMAND| Unused / Empty RAM pages        |
+-------------------+-------------------+---------------------------------+
                    \___________________ _________________________________/
                                        v
                            True Usable Memory: MemAvailable!
```

* **`MemTotal`**: Total usable physical RAM.
* **`MemFree`**: Completely unreferenced RAM pages. In Linux, large `MemFree` is wasteful; idle RAM is used for Page Cache.
* **`MemAvailable`** (The True Health Metric):
  An estimate of how much memory can be allocated without causing the system to swap or trigger the OOM Killer.
  $$\text{MemAvailable} \approx \text{MemFree} + \text{Cached} + \text{SReclaimable} - \text{Watermarks}$$
* **`Buffers`**: Temporary storage for raw disk blocks (filesystem metadata, partition tables).
* **`Cached`**: File-backed page cache in physical RAM. Reclaimable on demand when applications need memory!
* **`Dirty`**: Memory pages modified in RAM waiting to be flushed to physical storage.

#### B. `/proc/loadavg` & The Exponential Smoothing Math
```bash
cat /proc/loadavg
# Example Output: 0.42 0.85 1.15 2/894 14209
```
* The first three numbers represent the **1-minute, 5-minute, and 15-minute load averages**.
* The fourth field (`2/894`) indicates: **Currently executing processes / Total scheduled threads**.
* The fifth field (`14209`) is the **most recently created PID**.

```
LOAD AVERAGE DEFINITION:
Load Average is the exponentially decaying running average of:
  [ Number of Tasks in TASK_RUNNING (R) ] + [ Number of Tasks in TASK_UNINTERRUPTIBLE (D) ]
```

The kernel calculates load average every 5 seconds using an Exponential Moving Average (EMA):
$$\text{Load}(t) = \text{Load}(t - 1) \cdot e^{-5 / \tau} + n \cdot (1 - e^{-5 / \tau})$$
Where $\tau \in \{60, 300, 900\}$ seconds, and $n$ is the instantaneous count of running and uninterruptible tasks.

> **Critical Note**: Linux includes `TASK_UNINTERRUPTIBLE` (D-state disk sleep) in load average, unlike standard BSD Unix! If an NFS server hangs, load average can spike to 100.0 even with 0% CPU utilization!

### 4.2 Per-Process Metrics: `/proc/<PID>/`
Every active process has an ephemeral directory in `/proc/`:

```
CRITICAL /proc/[pid]/ NODES:
/proc/[pid]/
  |-- cmdline      Null-delimited string of original command-line arguments.
  |-- environ      Null-delimited environment variable array.
  |-- fd/          Subdirectory containing symlinks to all currently open file descriptors!
  |-- maps         Virtual memory address space map (code, heap, stack, shared libs).
  |-- status       Human-readable summary (State, UIDs, Memory limits, Context switches).
  |-- oom_score    Current vulnerability score calculated by kernel OOM killer (0 - 1000).
  `-- oom_score_adj Administrator override knob (-1000 to +1000). Setting to -1000 makes PID IMMUNE to OOM killing!
```

---

## 5. Real-World Production War Stories

### 5.1 War Story 1: The Silent File Descriptor Leak (`EMFILE`)
* **The Incident**: A high-volume payment processing microservice (Python + FastAPI) ran smoothly for 6 hours, then abruptly began rejecting 100% of incoming transactions with HTTP 500:
  `OSError: [Errno 24] Too many open files`
* **Live Production Triage using `/proc`**:
  ```bash
  # 1. Identify the PID of the failing microservice:
  pgrep -f "payment_service"
  # Returned PID: 14208

  # 2. Check the maximum allowable file descriptors for this process:
  grep "Max open files" /proc/14208/limits
  # Output: Max open files            1024                 4096                 files

  # 3. Count how many descriptors the process currently holds:
  ls -1 /proc/14208/fd | wc -l
  # Output: 1025 (CEILING HIT!)

  # 4. Inspect what files or sockets are leaking:
  ls -l /proc/14208/fd | tail -n 10
  # Output:
  # lrwx------ 1 root root 64 Nov 23 10:14 1020 -> socket:[4819201]
  # lrwx------ 1 root root 64 Nov 23 10:14 1021 -> socket:[4819205]
  # lrwx------ 1 root root 64 Nov 23 10:14 1022 -> socket:[4819210]
  # lrwx------ 1 root root 64 Nov 23 10:14 1023 -> socket:[4819218]
  ```
* **The Root Cause**: A newly deployed fraud verification client created a raw HTTP socket connection for every transaction, but omitted `response.close()`! Sockets remained permanently open in the kernel table until the limit was exhausted.
* **Resolution**:
  1. Live production relief: Raised limit dynamically using `prlimit --pid 14208 --nofile=65536:65536`.
  2. Code fix: Enforced connection pooling (`requests.Session()`) and proper context managers.

### 5.2 War Story 2: The Monitoring Agent that Killed a 128-Core Database
* **The Incident**: An infrastructure team installed a third-party agent that executed `cat /proc/[pid]/status` once per second for every thread in a Cassandra database running 12,000 threads.
* **The Physics**: Generating `/proc/[pid]/status` acquires task locks and formats 60 lines of ASCII. 12,000 threads $\times 1\text{ Hz} = 700,000\text{ kernel lock acquisitions per second}$!
* **The Fix**: Switched to reading aggregated cgroup metrics (`/sys/fs/cgroup/memory`) instead of individual thread `/proc` files.

---

## 6. Staff-Level Technical Interview Deep-Dives

### Question 1: How can an administrator recover an accidentally deleted log file if a running process still has it open?
**Exhaustive Answer**:
* In Linux, a file is only truly unlinked and destroyed from disk when its directory inode link count reaches `0` **AND** all open file descriptor reference counts drop to `0`!
* If a 50 GB log file `/var/log/app.log` is deleted with `rm /var/log/app.log` while `java` (PID 9102) is actively writing to it:
  1. The directory entry is deleted, so `ls /var/log/app.log` returns `No such file or directory`.
  2. However, the inode and data blocks remain allocated on disk because `struct file` in the kernel still references them!
  3. Locate the file descriptor: `ls -l /proc/9102/fd` will show `fd 4 -> /var/log/app.log (deleted)`.
  4. Recover the entire file contents: `cp /proc/9102/fd/4 /var/log/app_recovered.log`!
  5. The kernel streams the exact data blocks through the VFS descriptor into the new file.

### Question 2: Why does `ls -l /proc/cpuinfo` show size 0, but `wc -c /proc/cpuinfo` outputs thousands of bytes?
**Exhaustive Answer**:
* `ls -l` issues the `stat()` system call.
* When `stat()` queries `/proc/cpuinfo`, the `procfs` inode implementation fills `struct stat.st_size = 0` because calculating the exact character length of dynamic kernel text without generating the text would waste CPU cycles.
* When `wc -c` runs, it issues `open()` and loops `read()` until `read()` returns `0` (EOF).
* Each `read()` invokes the kernel's `seq_printf` function inside `procfs`, which dynamically generates the CPU specifications into a temporary kernel page buffer and copies it to userspace. `wc` counts the actual bytes delivered across the syscall boundary.

### Question 3: What is the exact difference between `Buffers` and `Cached` in `/proc/meminfo`?
**Exhaustive Answer**:
* **`Buffers`**: Represents in-memory caching of **raw disk block sectors** (metadata). When the kernel reads partition superblocks, directory tables, or raw block devices, bytes are cached in the buffer cache.
* **`Cached`**: Represents in-memory caching of **regular file contents** within the VFS Page Cache. When an application reads a file (`open()` and `read()`), data pages are cached here. Both are reclaimable under memory pressure!

---

## 7. Complete Verification Checklist (Zero Gaps)
- [ ] Do you understand why `/proc` and `/sys` consume 0 bytes of physical hard drive space?
- [ ] Can you explain why `MemFree` is a misleading metric and why `MemAvailable` is the true indicator of system memory health?
- [ ] What two thread states ($R$ and $D$) contribute to the Linux system load average in `/proc/loadavg`?
- [ ] How does inspecting `/proc/<PID>/fd/` allow you to diagnose socket and file descriptor leaks?
- [ ] How can you use `/proc/<PID>/fd/<FD>` to recover an unlinked file before the writing process closes it?
- [ ] How does the kernel `seq_file` interface synthesize text streams on the fly?
