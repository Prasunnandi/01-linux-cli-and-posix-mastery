# Day 14: Disk I/O Stats (iostat, iotop) & Quotas

## 1. Architectural Foundations: The Linux I/O Subsystem

Disk storage is thousands of times slower than main memory. The Linux storage architecture is structured as a multi-tier pipeline designed to merge adjacent requests, minimize head movements on mechanical disks, and optimize concurrency on NVMe storage:

```
+-------------------------------------------------------------------------+
|                  Linux Storage Stack Architecture                       |
+-------------------------------------------------------------------------+
| User Applications (write, read, aio_read, io_uring)                    |
|       |                                                                 |
|       v                                                                 |
| Virtual Filesystem (VFS) & Page Cache (Dirty Page Buffering)            |
|       |                                                                 |
|       v                                                                 |
| Block Layer (BIO Requests, bio_vec Scatter/Gather Lists)                |
|       |                                                                 |
|       v                                                                 |
| I/O Schedulers / Multi-Queue (blk-mq) Layer                             |
| [ mq-deadline | bfq | kyber | none (hardware FIFO) ]                    |
|       |                                                                 |
|       v                                                                 |
| Device Drivers (nvme.ko, scsi_mod.ko, virtio_blk.ko)                   |
|       |                                                                 |
|       v                                                                 |
| Physical Hardware Controller (PCIe NVMe / SAS Host Bus Adapter)         |
+-------------------------------------------------------------------------+
```

### 1.1 Multi-Queue Block Layer (`blk-mq`)
On legacy single-spindle HDDs, an I/O scheduler maintained a single global request queue with a single lock. On modern PCIe Gen 4/5 NVMe SSDs capable of millions of IOPS and 64,000 hardware queues, global locks caused severe CPU contention. The modern Linux **`blk-mq`** architecture provides:
- **Software Staging Queues**: Per-CPU submission queues (`ctx`), eliminating lock contention across cores.
- **Hardware Dispatch Queues**: Maps directly to hardware submission queues (`hctx`) exposed by the NVMe controller.

---

## 2. Dissecting `/proc/diskstats` and `iostat`

All Linux disk monitoring tools (`iostat`, `sar -d`, Prometheus `node_exporter`) derive their data directly from the kernel interface: `/proc/diskstats`.

```bash
$ cat /proc/diskstats | grep sda
 8       0 sda 14210 2410 1489201 45120 89201 1204 4892010 120400 0 45120 165520 0 0 0 0
```

The 11 core metrics maintained per block device are:
1. `reads completed successfully`
2. `reads merged` (adjacent sequential sectors combined into single BIO)
3. `sectors read` (1 sector = 512 bytes)
4. `time spent reading` (in milliseconds)
5. `writes completed successfully`
6. `writes merged`
7. `sectors written`
8. `time spent writing` (in milliseconds)
9. `I/Os currently in progress` (instantaneous queue depth)
10. `time spent doing I/Os` (in milliseconds)
11. `weighted time spent doing I/Os`

### 2.1 The Mathematics of `iostat -xz 1`

Running `iostat -xz 1` transforms these cumulative counters into delta rates:

```bash
$ iostat -xz 1 1
Device   r/s    w/s   rkB/s   wkB/s  rrqm/s wrqm/s  %rrqm  %wrqm  r_await w_await  aqu-sz  %util
sda    145.0  820.0  4520.0 32800.0     0.0   45.0    0.0    5.2     1.20    4.50    3.80  94.2
```

### Critical Formula Derivations:
- **`r/s` and `w/s` (IOPS)**:

  $$\text{IOPS} = \frac{\Delta \text{reads}}{\Delta t} + \frac{\Delta \text{writes}}{\Delta t}$$

- **`r_await` and `w_await` (Average Latency)**: Average time (in milliseconds) an I/O spent waiting in the queue PLUS being serviced by hardware:

  $$\text{r\_await} = \frac{\Delta \text{time\_reading}}{\Delta \text{reads}}$$

- **`aqu-sz` (Average Queue Size)**: Average number of requests pending in the driver and hardware queues:

  $$\text{aqu-sz} = \frac{\Delta \text{weighted\_io\_time}}{\Delta t \times 1000}$$

- **`%util` (Device Utilization)**: Percentage of elapsed time during which the device was busy servicing at least one request:

  $$\%\text{util} = \frac{\Delta \text{time\_doing\_io}}{\Delta t \times 1000} \times 100\%$$

> [!WARNING]
> On multi-spindle RAID arrays or NVMe SSDs that handle 32+ commands concurrently, **`%util` can reach 100% while substantial device throughput remains available**. Always cross-reference `%util` with `r_await`, `w_await`, and `aqu-sz`. If latency (`await`) spikes above acceptable thresholds, the storage device is truly saturated.

---

## 3. Filesystem Disk Quotas: Architecture & Enforcement

In multi-tenant servers, shared HPC clusters, or containerized hosts, a single rogue user or container can consume all available blocks or Inodes, crashing other tenants. Linux implements **Disk Quotas** at the filesystem level.

### 3.1 Quota Types: Soft vs Hard Limits
- **Hard Limit**: Absolute physical ceiling. Any system call (`write()`, `creat()`) that would breach the hard limit is immediately aborted with error `EDQUOT` (**Disk quota exceeded**).
- **Soft Limit**: Threshold warning boundary. A user can temporarily exceed the soft limit up to the hard limit for a configurable **Grace Period** (default $7\text{ days}$). If the user does not delete data before the grace period expires, the soft limit hardens into an absolute hard limit.

```
0 MB                     Soft Limit (800 MB)          Hard Limit (1000 MB)
|---------------------------------|-----------------------------|
          Normal Operation                Grace Period Timer
                                          (7 Days to reduce disk)
```

### 3.2 Setting Up User Quotas in Ext4:
```bash
# 1. Enable quota accounting in /etc/fstab:
# /dev/sdb1  /data  ext4  defaults,usrquota,grpquota  0 2

# 2. Remount filesystem and generate quota databases (aquota.user):
$ mount -o remount /data
$ quotacheck -cum /data
$ quotaon -v /data

# 3. Configure quota for user alice (soft=800MB, hard=1000MB):
$ setquota -u alice 800M 1000M 10000 12000 /data

# 4. Inspect quota status:
$ repquota -avug
```
