# Day 13: Filesystem Superblocks & ext4 Journaling

## 1. Architectural Foundations: Ext4 Disk Layout & Block Groups

The Fourth Extended Filesystem (**ext4**) is the default, battle-tested workhorse filesystem of enterprise Linux. To prevent disk fragmentation and minimize seek times on rotational and solid-state media, ext4 subdivides physical partition storage into autonomous administrative zones called **Block Groups** (typically $128\text{ MB}$ each, containing $32,768$ blocks of $4096\text{ bytes}$).

```
+-----------------------------------------------------------------------------------+
|                            Ext4 Partition Disk Geometry                           |
+-----------------------------------------------------------------------------------+
| 1024-byte | Block Group 0 | Block Group 1 | Block Group 2 | ... | Block Group N-1 |
| Boot Code | (128 MB)      | (128 MB)      | (128 MB)      |     | (128 MB)        |
+-----------------------------------------------------------------------------------+

                              Inside a Single Block Group:
+-----------------------------------------------------------------------------------+
| Superblock | Group Descriptors | Block Bitmap | Inode Bitmap | Inode Table | Data |
| (1 block)  | (GDT, N blocks)   | (1 block)    | (1 block)    | (M blocks)  |Blocks|
+-----------------------------------------------------------------------------------+
```

### 1.1 The Primary Superblock & Sparse Superblocks
The **Superblock** is the master control record of the entire filesystem. Located at fixed offset **1024 bytes** from the start of the partition, it records:
- Total block count and total Inode count.
- Block size (typically $4096\text{ bytes}$) and Inode size ($256\text{ bytes}$).
- Free block count and free Inode count.
- Filesystem state (Clean vs Error flags).
- Mount count, maximum mount count, and last `fsck` check time.
- UUID and volume label.

Because corruption of the primary superblock makes the entire filesystem unmountable, ext4 employs the **Sparse Superblock** feature. Redundant backup copies of the superblock and Group Descriptor Table (GDT) are stored exclusively in Block Groups $0$, $1$, and groups that are powers of $3, 5,$ and $7$ (Groups $3, 5, 7, 9, 25, 49, \dots$).

If the primary superblock is corrupted by hardware failures:
```bash
# Locate backup superblocks:
$ dumpe2fs /dev/sda1 | grep -i superblock
  Primary superblock at 0, Group descriptors at 1-1
  Backup superblock at 32768, Group descriptors at 32769-32769
  Backup superblock at 98304, Group descriptors at 98305-98305

# Recover using a healthy backup superblock:
$ fsck.ext4 -b 32768 /dev/sda1
```

---

## 2. Crash Consistency & The JBD2 Journaling Engine

In a non-journaling filesystem (such as ext2 or FAT32), appending data to a file requires updating three distinct disk locations:
1. Allocating a free block in the **Block Bitmap**.
2. Updating the file's **Inode** (increasing file size and adding block pointer).
3. Writing the actual **Data Payload** into the allocated data block.

If power fails or the kernel panics mid-write (between Step 1 and 2), the filesystem state becomes corrupt: a block is marked used, but no Inode references it. On reboot, a full partition scan (`fsck`) taking hours or days would be required to reconstruct consistency.

To guarantee instantaneous crash recovery, ext4 utilizes the **Journaling Block Device 2 (JBD2)** subsystem. JBD2 maintains a dedicated circular write-ahead log (WAL) on disk (typically a hidden $128\text{ MB}$ file at Inode `8`).

```
                              JBD2 Transaction Life Cycle
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 1. Descriptor Block | 2. Target Metadata Blocks In-Memory | 3. Commit Block (Magic) |
| (Lists target LBAs) | (Inode updates, Block Bitmap diffs) | (Written via FLUSH/FUA) |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
                              Transaction Marked Committed
                              (Guaranteed Recoverable in WAL)
                                          |
                                          v
                              4. Checkpointing Phase
                         (Write back blocks to real Inode Table)
```

### 2.1 The Three Ext4 Journaling Modes

Ext4 supports three distinct journaling modes, configurable at mount time via `/etc/fstab`:

| Journaling Mode | What Gets Journaled | Durability Guarantee | Performance Impact |
| :--- | :--- | :--- | :--- |
| **`data=journal`** | **Both Metadata AND Data Payloads** | **Maximum**. Zero data corruption or loss on crash. | **Severe Write Penalty**. Every byte written twice. |
| **`data=ordered`** *(Default)* | **Metadata Only** (Data written to disk *before* metadata commits) | **High**. Prevents files from pointing to stale garbage blocks. | **Optimal**. Minimal latency overhead for enterprise workloads. |
| **`data=writeback`** | **Metadata Only** (No ordering constraints between data and metadata) | **Weak**. After crash, files may contain old deallocated data. | **Fastest**. High throughput at risk of stale data leaks. |

---

## 3. Dissecting ext4 Utilities: `dumpe2fs` & `tune2fs`

Systems engineers use low-level tools to inspect and modify filesystem parameters without reformatting:

```bash
# Inspect superblock parameters:
$ tune2fs -l /dev/sda1
Filesystem volume name:   cloud_root
Last mounted on:          /
Filesystem UUID:          a7c3b210-912f-48d1-b512-094182941fa0
Filesystem state:         clean
Errors behavior:          Continue
Filesystem OS type:       Linux
Inode count:              3276800
Block count:              13107200
Reserved block count:     655360 (5.0%)
Free blocks:              8412490
Free inodes:              2984120
Block size:               4096
Journal UUID:             f0e1d2c3-b4a5-9687-7869-5a4b3c2d1e0f
```

### Crucial Superblock Tuning:
- **Reserved Blocks (5% Rule)**: By default, ext4 reserves $5\%$ of disk blocks exclusively for user `root` (UID 0). This prevents user processes from completely filling the disk and halting critical system daemons (syslog, sshd). On a modern $20\text{ TB}$ drive, $5\% = 1\text{ TB}$ of wasted space! Reclaim it using:
  ```bash
  $ tune2fs -m 1 /dev/sda1  # Reduce reserved space to 1%
  ```
- **Error Behavior**: Configure how the kernel reacts upon encountering disk corruption:
  ```bash
  $ tune2fs -e remount-ro /dev/sda1  # Instantly remount read-only to protect data
  ```

---

## 4. Production War Story: The Power Outage Null-Byte Leak

An enterprise SaaS company suffered an unannounced data center power cut. Upon server reboot, several customer JSON configuration files were found filled entirely with thousands of null bytes (`\x00\x00\x00...`), despite the filesystem being formatted with ext4!

### Root Cause Analysis
The filesystem had been mounted with `data=writeback` to maximize microbenchmark scores. When applications updated files using the standard pattern:
```c
int fd = open("config.json", O_WRONLY | O_CREAT | O_TRUNC);
write(fd, payload, len);
close(fd);
```
Under `data=writeback`, the ext4 metadata update (file size increased to $4096\text{ bytes}$) was committed to the journal and written to disk before the Page Cache dirty data blocks were flushed to storage media. When the power died mid-flight, the Inode pointed to an allocated disk block whose physical NAND flash had not yet received the new data payload, leaving the previous unwritten or zeroed block visible to users.

### The Remediation
1. Switched all enterprise mounts back to `data=ordered`.
2. Mandated that all critical state writes execute `fsync(fd)` or `fdatasync(fd)` before closing file descriptors, forcing an explicit hardware cache barrier.
