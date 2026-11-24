# Day 14: Disk I/O Stats (iostat, iotop) & Quotas

## 1. Architectural Foundations: The Linux I/O Subsystem Pipeline

Storage devices (rotational mechanical hard disks, SATA solid-state drives, and high-performance PCIe NVMe devices) operate at latencies orders of magnitude higher than CPU caches and DDR5 system memory. To prevent applications from stalling during storage operations, the Linux operating system routes all disk access through a multi-tier kernel subsystem:

```
+-------------------------------------------------------------------------+
|                  Linux Storage Stack Architecture                       |
+-------------------------------------------------------------------------+
| User Applications (read, write, pread, pwrite, aio_read, io_uring)      |
|       |                                                                 |
|       v                                                                 |
| Virtual Filesystem (VFS) & Page Cache (Dirty Page Buffering)            |
|       |                                                                 |
|       v                                                                 |
| Block Layer (BIO Requests, bio_vec Scatter/Gather Lists)                |
|       |                                                                 |
|       v                                                                 |
| Multi-Queue (blk-mq) Layer & I/O Schedulers                             |
| [ mq-deadline | bfq | kyber | none (Hardware Direct FIFO) ]             |
|       |                                                                 |
|       v                                                                 |
| Device Drivers (nvme.ko, scsi_mod.ko, virtio_blk.ko)                   |
|       |                                                                 |
|       v                                                                 |
| Physical Hardware Controller (PCIe Gen 4/5 NVMe / SAS Host Adapter)     |
+-------------------------------------------------------------------------+
```

### 1.1 The Multi-Queue Architecture (`blk-mq`)
In legacy Linux kernels, all block I/O requests were funneled through a single global request queue protected by a single kernel spinlock. On modern NVMe SSDs capable of millions of IOPS and 64,000 parallel hardware submission queues, this global spinlock caused catastrophic CPU cache contention across multi-core systems.

The modern Linux **`blk-mq`** architecture introduces a two-tier queueing hierarchy:
1. **Software Staging Queues (`ctx`)**: Allocated per CPU core. When a thread issues a read or write system call, the BIO request is queued in the local core's software queue without acquiring cross-CPU locks.
2. **Hardware Dispatch Queues (`hctx`)**: Mapped directly to hardware execution queues exposed by the physical PCIe NVMe controller.

---

## 2. Dissecting `/proc/diskstats`: The Source of Truth

Every storage monitoring utility in Linux (`iostat`, `sar -d`, `iotop`, and Prometheus `node_exporter`) derives its data directly from the kernel interface: `/proc/diskstats`.

```bash
$ cat /proc/diskstats | grep sda
 8       0 sda 14210 2410 1489201 45120 89201 1204 4892010 120400 0 45120 165520 0 0 0 0
```

### The 11 Core Counter Fields Explained:
1. `reads completed`: Total number of physical read operations successfully finished.
2. `reads merged`: Adjacent sequential read BIO requests combined into single hardware commands.
3. `sectors read`: Total sectors read from the drive (1 sector = 512 bytes).
4. `time reading (ms)`: Total milliseconds spent reading by all read requests combined.
5. `writes completed`: Total number of physical write operations successfully finished.
6. `writes merged`: Adjacent sequential write requests merged into larger block transfers.
7. `sectors written`: Total sectors written to the drive.
8. `time writing (ms)`: Total milliseconds spent writing by all write requests combined.
9. `I/Os in progress`: Instantaneous number of requests currently pending in driver and hardware queues.
10. `time doing I/Os (ms)`: Total milliseconds during which the storage device had at least one active request.
11. `weighted I/O time (ms)`: Sum of duration of each request (used for calculating average queue depth).

---

## 3. Mathematical Derivations of `iostat -xz 1`

When `iostat` computes performance statistics over elapsed sampling window $\Delta t$ (in seconds):

### 1. IOPS (Input/Output Operations Per Second):
$$\text{r/s} = \frac{\Delta \text{reads}}{\Delta t}, \quad \text{w/s} = \frac{\Delta \text{writes}}{\Delta t}$$

### 2. Throughput (Kilobytes Per Second):
$$\text{rkB/s} = \frac{\Delta \text{sectors\_read} \times 512}{1024 \times \Delta t}, \quad \text{wkB/s} = \frac{\Delta \text{sectors\_written} \times 512}{1024 \times \Delta t}$$

### 3. Average Request Latency (`r_await` and `w_await`):
Average time (in milliseconds) an I/O request spent waiting in software queue PLUS being serviced by hardware silicon:
$$\text{r\_await} = \frac{\Delta \text{time\_reading}}{\Delta \text{reads}}, \quad \text{w\_await} = \frac{\Delta \text{time\_writing}}{\Delta \text{writes}}$$

### 4. Average Queue Size (`aqu-sz`):
Using **Little's Law** from queueing theory ($L = \lambda W$, where average queue length equals arrival rate multiplied by wait time):
$$\text{aqu-sz} = \frac{\Delta \text{weighted\_io\_time}}{\Delta t \times 1000}$$

### 5. Device Utilization (`%util`):
$$\%\text{util} = \frac{\Delta \text{time\_doing\_io}}{\Delta t \times 1000\text{ ms}} \times 100\%$$

> [!CRITICAL]
> **The `%util` False Alarm in Modern Storage:**
> On parallel storage arrays (NVMe drives, hardware RAID, SANs), **`%util` can reach 100% when only a single queue is occupied**! Never use `%util` alone to diagnose disk saturation. Always evaluate **`await`** (latency) and **`aqu-sz`** (queue length). If `await` spikes into dozens of milliseconds while `%util = 100%`, the storage device is truly bottlenecked.

---

## 4. Compilable C Implementation: Real-Time `/proc/diskstats` Monitor

The following complete, standalone C program opens `/proc/diskstats`, parses raw counters for a specified block device, sleeps for 1 second, and computes real-time IOPS, throughput, and average wait latency:

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

struct DiskStatsSnapshot {
    uint64_t reads_completed;
    uint64_t reads_merged;
    uint64_t sectors_read;
    uint64_t read_time_ms;
    uint64_t writes_completed;
    uint64_t writes_merged;
    uint64_t sectors_written;
    uint64_t write_time_ms;
    uint64_t ios_in_progress;
    uint64_t io_time_ms;
    uint64_t weighted_io_time_ms;
};

int read_device_stats(const char *target_dev, struct DiskStatsSnapshot *stats) {
    FILE *fp = fopen("/proc/diskstats", "r");
    if (!fp) {
        perror("fopen(/proc/diskstats)");
        return -1;
    }

    char line[512];
    char dev_name[64];
    int major, minor;
    int found = 0;

    while (fgets(line, sizeof(line), fp)) {
        int parsed = sscanf(line, "%d %d %s %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu",
                            &major, &minor, dev_name,
                            &stats->reads_completed, &stats->reads_merged,
                            &stats->sectors_read, &stats->read_time_ms,
                            &stats->writes_completed, &stats->writes_merged,
                            &stats->sectors_written, &stats->write_time_ms,
                            &stats->ios_in_progress, &stats->io_time_ms,
                            &stats->weighted_io_time_ms);
        if (parsed >= 14 && strcmp(dev_name, target_dev) == 0) {
            found = 1;
            break;
        }
    }

    fclose(fp);
    return found ? 0 : -1;
}

int main(int argc, char *argv[]) {
    const char *dev = (argc > 1) ? argv[1] : "sda";
    printf("[+] Monitoring Linux Disk I/O for device: /dev/%s\n", dev);

    struct DiskStatsSnapshot s1, s2;
    if (read_device_stats(dev, &s1) != 0) {
        fprintf(stderr, "[ERROR] Device %s not found in /proc/diskstats!\n", dev);
        return EXIT_FAILURE;
    }

    sleep(1); // 1.0 second sampling window

    if (read_device_stats(dev, &s2) != 0) {
        fprintf(stderr, "[ERROR] Failed to read second stats sample!\n");
        return EXIT_FAILURE;
    }

    uint64_t delta_reads = s2.reads_completed - s1.reads_completed;
    uint64_t delta_writes = s2.writes_completed - s1.writes_completed;
    uint64_t delta_r_sectors = s2.sectors_read - s1.sectors_read;
    uint64_t delta_w_sectors = s2.sectors_written - s1.sectors_written;
    uint64_t delta_r_time = s2.read_time_ms - s1.read_time_ms;
    uint64_t delta_w_time = s2.write_time_ms - s1.write_time_ms;
    uint64_t delta_io_time = s2.io_time_ms - s1.io_time_ms;

    double r_per_sec = (double)delta_reads;
    double w_per_sec = (double)delta_writes;
    double r_kb_per_sec = (double)delta_r_sectors * 512.0 / 1024.0;
    double w_kb_per_sec = (double)delta_w_sectors * 512.0 / 1024.0;

    double r_await = (delta_reads > 0) ? ((double)delta_r_time / delta_reads) : 0.0;
    double w_await = (delta_writes > 0) ? ((double)delta_w_time / delta_writes) : 0.0;
    double util_pct = (double)delta_io_time / 10.0; // (delta_io_time / 1000) * 100

    printf("\n=== Disk I/O Telemetry (1-Second Delta) ===\n");
    printf("  Read IOPS         : %.2f r/s\n", r_per_sec);
    printf("  Write IOPS        : %.2f w/s\n", w_per_sec);
    printf("  Read Throughput   : %.2f KB/s (%.2f MB/s)\n", r_kb_per_sec, r_kb_per_sec / 1024.0);
    printf("  Write Throughput  : %.2f KB/s (%.2f MB/s)\n", w_kb_per_sec, w_kb_per_sec / 1024.0);
    printf("  Read Latency      : %.2f ms\n", r_await);
    printf("  Write Latency     : %.2f ms\n", w_await);
    printf("  Device %%%%util     : %.2f %%%%\n", util_pct);

    return EXIT_SUCCESS;
}
```

---

## 5. Filesystem Disk Quotas: Architecture & Enforcement

In shared multi-tenant environments (HPC clusters, shared Linux servers, web hosting), unconstrained disk writes create a "noisy neighbor" disaster where one runaway process fills the drive and crashes critical system daemons. Linux implements **Disk Quotas** at the filesystem level.

### 5.1 Quota Types: Soft Limits vs Hard Limits
- **Hard Limit**: Absolute physical ceiling. Any write operation (`write()`, `creat()`) that would cause the user's allocated block or Inode count to exceed the hard limit is immediately aborted with error `EDQUOT` (**Disk quota exceeded**).
- **Soft Limit**: Warning boundary. A user can temporarily exceed the soft limit up to the hard limit for a configurable **Grace Period** (default $7\text{ days}$). If the user does not delete data before the grace period expires, the soft limit hardens into an absolute hard limit, blocking all future allocations.

```
0 MB                     Soft Limit (800 MB)          Hard Limit (1000 MB)
|---------------------------------|-----------------------------|
          Normal Operation                Grace Period Timer
                                          (7 Days to reduce disk)
```

### 5.2 Enabling and Enforcing Quotas in Ext4:
```bash
# 1. Mount filesystem with usrquota and grpquota options in /etc/fstab:
# /dev/sdb1  /data  ext4  defaults,usrquota,grpquota  0 2

# 2. Remount filesystem:
$ mount -o remount /data

# 3. Create quota metadata databases (aquota.user and aquota.group):
$ quotacheck -cum /data
$ quotaon -v /data

# 4. Set quotas for user alice (soft=800MB, hard=1000MB, soft_inodes=10000, hard_inodes=12000):
$ setquota -u alice 800M 1000M 10000 12000 /data

# 5. Generate complete audit report:
$ repquota -avug
```
