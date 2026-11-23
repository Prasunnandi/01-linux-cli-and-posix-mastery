# Day 08: Linux Filesystem Hierarchy Standard (FHS) & The Virtual Filesystem (`/proc` & `/sys`)

---

## 1. The Core Mental Model: Real-World Analogy
Imagine walking into an ultra-modern hospital:
* The **Medical Records Warehouse** (disk drives: `/home`, `/var`, `/etc`) contains permanent paper charts filed in drawers. If the power shuts off, the paper files remain on physical shelves.
* The **ICU Vital Signs Monitor** (`/proc` and `/sys`) does **not** store paper. It is an illuminated glass screen showing live heart rate, blood oxygen, and intracranial pressure in real time. If you tap the screen, you aren't pulling a sheet of paper from a shelf; you are reading current electrical sensors straight from the patient's body!

In Linux, **everything is exposed through the filesystem interface**. But not every file lives on a magnetic platter or SSD flash chip! The Linux kernel exposes its internal runtime state, memory tables, process registers, and hardware topology as pseudo-filesystems: `/proc` (process and kernel metrics) and `/sys` (device drivers and bus topology). When you read `/proc/cpuinfo`, no disk head moves—the CPU directly executes kernel code that formats its internal registers into an ASCII text stream on the fly!

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

---

## 2. Low-Level Kernel Architecture: How `procfs` Synthesizes Files

In a physical filesystem like `ext4`, an inode points to data blocks stored on physical disk sectors.
In the Virtual File System (VFS), an inode contains a table of function pointers: `struct file_operations`.

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

When you inspect a file in `/proc`:
```bash
ls -l /proc/cpuinfo
# -r--r--r-- 1 root root 0 Nov 23 10:00 /proc/cpuinfo
```
Notice that the size is reported as **`0 bytes`**!
* In `procfs`, the file has no pre-allocated disk size.
* When your process issues `read(fd, buffer, 4096)`, the kernel intercepts the syscall and executes the kernel function registered in `file_operations->read` (specifically, `seq_read` in Linux kernel sequence files).
* The kernel dynamically queries the CPU registers or memory descriptors, formats ASCII strings into a kernel memory buffer, copies them across the user/kernel space boundary to your userspace buffer via `copy_to_user()`, and returns the byte count.

---

## 3. The Linux Filesystem Hierarchy Standard (FHS)

The FHS defines the directory structure and directory contents in Linux distributions:

| Directory | Full Name / Classification | Purpose & Contents | Persistent Across Reboots? |
| :--- | :--- | :--- | :--- |
| **`/`** | Root | Top-level directory of the absolute file hierarchy. Everything branches from here. | Yes |
| **`/bin`** | Essential User Binaries | Core executable binaries required for single-user recovery mode (e.g. `sh`, `bash`, `cp`, `ls`, `cat`). On modern distros, symlinked to `/usr/bin`. | Yes |
| **`/sbin`** | Essential System Binaries | Administrative binaries required for system boot and recovery (e.g. `ip`, `iptables`, `fdisk`, `reboot`). Symlinked to `/usr/sbin`. | Yes |
| **`/etc`** | Editable Text Configurations | Host-specific system-wide configuration files (e.g. `/etc/passwd`, `/etc/fstab`, `/etc/nginx/nginx.conf`). | Yes |
| **`/dev`** | Device Nodes | Special character and block device files representing physical and pseudo hardware (`/dev/sda`, `/dev/null`, `/dev/urandom`, `/dev/pts`). Managed dynamically by `devtmpfs` and `udev`. | No (Recreated on boot) |
| **`/proc`** | Process Information Pseudo-FS | Live kernel metrics, hardware information, and per-process memory/runtime descriptors (`procfs`). | No (Pure RAM state) |
| **`/sys`** | System & Hardware Topology | Unified device model exposing kernel subsystem parameters, power management, and PCI/USB bus states (`sysfs`). | No (Pure RAM state) |
| **`/var`** | Variable Data | Dynamic spool files, system logs (`/var/log`), caches (`/var/cache`), databases (`/var/lib/mysql`). Must survive reboot. | Yes |
| **`/tmp`** | Temporary Files | Ephemeral scratch storage. Often mounted as `tmpfs` (RAM-backed) and cleared on boot. | No |
| **`/usr`** | Universal System Resources | User binaries, libraries, and documentation (`/usr/bin`, `/usr/lib`, `/usr/share`). Historically mounted read-only over NFS. | Yes |
| **`/home`** | User Home Directories | Personal storage, shell configs (`~/.bashrc`), user data. | Yes |

---

## 4. Deep-Dive: Exploring `/proc` Internals

### 4.1 System-Wide Metrics

#### A. `/proc/meminfo` & The True Available Memory Equation
Run `cat /proc/meminfo`:
```
MemTotal:       32645120 kB
MemFree:         4123540 kB
MemAvailable:   24891230 kB
Buffers:          345120 kB
Cached:         20422570 kB
SwapTotal:       8388604 kB
SwapFree:        8388604 kB
```

**Crucial Systems Engineering Truth**: In Linux, **`MemFree` does NOT represent how much memory your applications can use!**
The Linux kernel aggressively utilizes unused memory as page cache (`Cached`) to avoid slow disk I/O. If an application suddenly requests 10 GB of RAM, the kernel instantaneously evicts clean cached disk pages and hands the memory to the application without dropping a frame.

$$\text{Usable Application Memory} \approx \text{MemAvailable} = \text{MemFree} + \text{Cached}_{\text{evictable}} + \text{Buffers} - \text{Watermarks}$$

* **`MemTotal`**: Total usable physical RAM (excluding kernel binary reserved space).
* **`MemFree`**: Memory completely untouched and empty. High `MemFree` is actually a sign of wasted caching capacity!
* **`MemAvailable`**: An estimate provided by the kernel of how much memory is available for starting new applications without swapping.

---

#### B. `/proc/loadavg` & The Exponential Smoothing Math
Run `cat /proc/loadavg`:
```
0.72 1.45 2.10 2/450 19842
```
* Field 1: 1-minute load average
* Field 2: 5-minute load average
* Field 3: 15-minute load average
* Field 4: Currently executing threads / total scheduled threads (e.g. `2` currently on CPU out of `450` runnable)
* Field 5: Most recently created PID (`19842`)

**Mathematical Derivation**:
Linux calculates load average using an exponentially decaying moving average (EWMA). Every 5 seconds ($t = 5\text{s}$), the kernel updates the load average:

$$L_t = L_{t-1} \cdot e^{-\Delta t / \tau} + n \cdot (1 - e^{-\Delta t / \tau})$$

Where:
* $L_t$ is the new load average.
* $\Delta t = 5$ seconds.
* $\tau$ is the time constant: 60 seconds (for 1-min avg), 300 seconds (for 5-min avg), or 900 seconds (for 15-min avg).
* $n$ is the instantaneous count of threads in **`TASK_RUNNING` (state R)** OR **`TASK_UNINTERRUPTIBLE` (state D - waiting for disk I/O)**.

*Notice*: On Linux (unlike traditional Unix), high disk I/O wait drives up the load average because threads in uninterruptible sleep (`D` state) are counted as active demand for system resources!

---

### 4.2 Per-Process Metrics: `/proc/<PID>/`

Every running process with identifier `<PID>` has a dedicated virtual directory:

| Path | Contents & Meaning |
| :--- | :--- |
| **`/proc/<PID>/cmdline`** | Null-byte (`\0`) separated list of the full command-line arguments used to launch the process. |
| **`/proc/<PID>/environ`** | Null-byte (`\0`) separated list of environment variables active inside the process. |
| **`/proc/<PID>/cwd`** | Symlink to the current working directory of the process. |
| **`/proc/<PID>/exe`** | Symlink pointing directly to the executable binary on disk (even if deleted!). |
| **`/proc/<PID>/fd/`** | Directory containing numeric symlinks for every open file descriptor (0=stdin, 1=stdout, 2=stderr, 3+=sockets, open files). |
| **`/proc/<PID>/status`** | Human-readable process summary: UID, GID, state (`R`, `S`, `D`, `Z`), memory high-water mark (`VmHWM`), peak virtual memory (`VmPeak`), thread count (`Threads`). |
| **`/proc/<PID>/maps`** | Memory address space mapping: text segment, heap, dynamically linked libraries (`.so`), stack, memory-mapped files (`mmap`). |
| **`/proc/<PID>/limits`** | Soft and hard limits enforced by the kernel (`ulimit`): Max open files, max stack size, max CPU time. |

---

## 5. Real-World Production War Story: The Silent File Descriptor Leak

### The Incident:
A high-throughput payment processing API built in Go/Python began failing in production during Black Friday traffic. The service would run flawlessly for 4 hours, and then suddenly return `HTTP 500 Internal Server Error` on every incoming payment request.

The application logs revealed:
`OSError: [Errno 24] Too many open files`

### Live Production Triage using `/proc`:
The on-call engineer identified the process PID:
```bash
pgrep -f "payment-engine"
# Returned PID: 14208
```

Inspecting the system resource limits:
```bash
cat /proc/14208/limits | grep "Max open files"
# Max open files            1024                 4096                 files
```
The soft limit was capped at 1,024 open file descriptors.

Next, the engineer inspected `/proc/14208/fd/`:
```bash
ls -l /proc/14208/fd | wc -l
# Output: 1025
```
The process had completely exhausted its descriptor allocation!

By listing the actual targets of the symlinks in `/proc/14208/fd`:
```bash
ls -l /proc/14208/fd | tail -n 20
# lrwx------ 1 root root 64 Nov 23 10:14 1020 -> socket:[4819201]
# lrwx------ 1 root root 64 Nov 23 10:14 1021 -> socket:[4819205]
# lrwx------ 1 root root 64 Nov 23 10:14 1022 -> socket:[4819210]
# lrwx------ 1 root root 64 Nov 23 10:14 1023 -> socket:[4819218]
```
Over 1,000 file descriptors were open sockets in `ESTABLISHED` or `CLOSE_WAIT` states connected to an external fraud detection microservice!

### Root Cause:
The payment client created a new HTTP connection to verify card fraud for every transaction, but omitted `response.Body.Close()`. In Go and Python, failing to explicitly close the response body keeps the underlying TCP socket file descriptor open in the kernel table indefinitely.

### Resolution:
1. Immediate production unblock: Raised the process limit live using `prlimit --pid 14208 --nofile=65536:65536`.
2. Permanent fix: Enforced connection pooling (`requests.Session()` / `http.Client` with reuse) and added `defer resp.Body.Close()`.

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
* `ls -l` issues the `stat()` or `fstatat()` system call.
* When `stat()` queries `/proc/cpuinfo`, the `procfs` inode implementation fills `struct stat.st_size = 0` because calculating the exact character length of dynamic kernel text without generating the text would waste CPU cycles.
* When `wc -c` runs, it issues `open()` and loops `read()` until `read()` returns `0` (EOF).
* Each `read()` invokes the kernel's `seq_printf` function inside `procfs`, which dynamically generates the CPU specifications into a temporary kernel page buffer and copies it to userspace. `wc` counts the actual bytes delivered across the syscall boundary.

---

## 7. Complete Verification Checklist (Zero Gaps)
- [ ] Do you understand why `/proc` and `/sys` consume 0 bytes of physical hard drive space?
- [ ] Can you explain why `MemFree` is a misleading metric and why `MemAvailable` is the true indicator of system memory health?
- [ ] What two thread states ($R$ and $D$) contribute to the Linux system load average in `/proc/loadavg`?
- [ ] How does inspecting `/proc/<PID>/fd/` allow you to diagnose socket and file descriptor leaks?
