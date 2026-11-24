# Day 13: Filesystem Superblocks & ext4 Journaling

## 1. Architectural Foundations: Ext4 Physical Storage Geometry

The Fourth Extended Filesystem (**ext4**) is the default, mission-critical storage workhorse of enterprise Linux. Rather than treating storage devices as a single monolithic array of blocks, ext4 subdivides physical partition capacity into autonomous, self-contained administrative zones known as **Block Groups** (typically $128\text{ MB}$ each, containing $32,768$ blocks of $4096\text{ bytes}$).

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
The **Superblock** is the master control record governing the entire filesystem. Located at fixed byte offset **1024** from the start of the partition (leaving the first 1024 bytes untouched for x86 bootloaders), it defines all global filesystem parameters.

Because physical sector damage to the primary superblock would render the entire partition unmountable, ext4 implements the **Sparse Superblock** feature (`RO_COMPAT_SPARSE_SUPER`). Duplicate backup copies of the superblock and the Group Descriptor Table (GDT) are saved exclusively in:
- Block Group $0$ (Primary Superblock).
- Block Group $1$.
- Block Groups that are powers of $3, 5,$ and $7$ (Groups $3, 5, 7, 9, 25, 49, 81, 125, \dots$).

```bash
# Locate all backup superblocks on an ext4 partition:
$ dumpe2fs /dev/sda1 | grep -i superblock
  Primary superblock at 0, Group descriptors at 1-1
  Backup superblock at 32768, Group descriptors at 32769-32769
  Backup superblock at 98304, Group descriptors at 98305-98305
  Backup superblock at 163840, Group descriptors at 163841-163841

# Force partition recovery using a backup superblock:
$ fsck.ext4 -b 32768 -y /dev/sda1
```

---

## 2. Anatomy of the Kernel `struct ext4_super_block`

In the Linux kernel source code (`fs/ext4/ext4.h`), the superblock is defined as an exact 1024-byte binary structure:

```c
struct ext4_super_block {
    __le32  s_inodes_count;          /* Total Inodes count */
    __le32  s_blocks_count_lo;       /* Total Blocks count (Low 32 bits) */
    __le32  s_r_blocks_count_lo;     /* Reserved blocks count */
    __le32  s_free_blocks_count_lo;  /* Free blocks count */
    __le32  s_free_inodes_count;     /* Free inodes count */
    __le32  s_first_data_block;      /* First Data Block (0 for 4KB blocks) */
    __le32  s_log_block_size;        /* Block size = 1024 << s_log_block_size */
    __le32  s_log_cluster_size;      /* Cluster size */
    __le32  s_blocks_per_group;      /* Blocks per group (32,768) */
    __le32  s_clusters_per_group;    /* Clusters per group */
    __le32  s_inodes_per_group;      /* Inodes per group (8,192) */
    __le32  s_mtime;                 /* Last mount time */
    __le32  s_wtime;                 /* Last write time */
    __le16  s_mnt_count;             /* Mount count */
    __le16  s_max_mnt_count;         /* Maximal mount count */
    __le16  s_magic;                 /* Magic signature: 0xEF53 */
    __le16  s_state;                 /* File system state (1 = Clean) */
    __le16  s_errors;                /* Behavior when detecting errors */
    __le16  s_minor_rev_level;       /* Minor revision level */
    __le32  s_lastcheck;             /* Time of last check */
    __le32  s_checkinterval;         /* Max. time between checks */
    __le32  s_creator_os;            /* OS (0 = Linux) */
    __le32  s_rev_level;             /* Revision level */
    __le16  s_def_resuid;            /* Default uid for reserved blocks */
    __le16  s_def_resgid;            /* Default gid for reserved blocks */
    __u8    s_uuid[16];              /* 128-bit Filesystem UUID */
    char    s_volume_name[16];       /* Volume name label */
    char    s_last_mounted[64];      /* Directory path where last mounted */
    /* ... 64-bit feature extensions, JBD2 journal UUID, and CRC32C checksum ... */
    __le32  s_checksum;              /* Superblock CRC32C Checksum */
};
```

The fundamental sanity check of ext4 is verifying that bytes at offset `0x38` contain the magic hex bytes **`0xEF53`** (Little-Endian `53 EF`).

---

## 3. Ext4 Extents: Eliminating Indirect Block Pointers

Legacy filesystems (ext2, ext3) mapped file data using direct, indirect, doubly indirect, and triply indirect block pointers. For a $100\text{ GB}$ file, this required allocating millions of indirect pointer blocks, fragmenting storage and requiring multiple seek operations just to resolve a block address.

Ext4 completely eliminated indirect pointers, replacing them with **Extent Trees** (`struct ext4_extent`). An **extent** represents a contiguous range of physical blocks mapped to a contiguous range of logical file blocks:

```
+-------------------------------------------------------------------------+
|                  Ext4 12-Byte Extent Record Structure                   |
+-------------------------------------------------------------------------+
| Field            | Size    | Description                                |
+------------------+---------+--------------------------------------------+
| ee_block         | 4 bytes | Logical File Block Offset (starting block) |
| ee_len           | 2 bytes | Length of extent in blocks (up to 32,768)   |
| ee_start_hi      | 2 bytes | High 16 bits of physical disk block address|
| ee_start_lo      | 4 bytes | Low 32 bits of physical disk block address |
+------------------+---------+--------------------------------------------+
```

A single 12-byte extent can map up to **$32,768$ contiguous 4KB blocks ($128\text{ MB}$ of data)** in a single record! Up to 4 extents fit directly inside the Inode itself (`i_block[15]`). If a file is heavily fragmented, the Inode transitions into an extent B-tree using `struct ext4_extent_idx` branch nodes.

---

## 4. Crash Consistency & The JBD2 Journaling Engine

In a non-journaling filesystem (like ext2), appending data to an existing file requires three separate, independent disk writes:
1. Allocating a free block in the **Block Bitmap**.
2. Updating the file's **Inode** (increasing file size and adding the extent pointer).
3. Writing the user's **Data Payload** into the physical data block.

If a server suffers sudden power loss between Step 1 and Step 2, the filesystem becomes corrupt: physical blocks are marked allocated in the bitmap, but no Inode references them. Upon rebooting, the operating system would be forced to execute a full disk scan (`fsck`), scanning every Inode on a 10 TB drive for 6 hours.

To achieve instantaneous recovery (under 2 seconds), ext4 delegates all state modifications to the **Journaling Block Device 2 (JBD2)** subsystem. JBD2 maintains an append-only circular log on disk (typically an internal $128\text{ MB}$ space located at Inode 8).

```
                              JBD2 Transaction State Machine
                                            |
                                            v
+---------------------------------------------------------------------------------------+
| 1. Running Transaction | Collects dirty Inode buffers, bitmaps, and metadata in RAM   |
+---------------------------------------------------------------------------------------+
                                            | (After commit interval: default 5 seconds)
                                            v
+---------------------------------------------------------------------------------------+
| 2. Descriptor Block    | Written to disk journal. Lists physical target block LBAs.  |
| 3. Metadata Blocks     | Exact Inode and Bitmap block updates flushed to disk journal.|
| 4. Commit Block        | Written to journal with hardware barrier (FLUSH / FUA).     |
+---------------------------------------------------------------------------------------+
                                            |
                                            v
                               Transaction Committed!
                        (Crash consistency 100% guaranteed)
                                            |
                                            v
+---------------------------------------------------------------------------------------+
| 5. Checkpointing Phase | Inodes & bitmaps written back to real filesystem tables.    |
|                        | Space in circular journal freed for new transactions.        |
+---------------------------------------------------------------------------------------+
```

### 4.1 The Three Ext4 Journaling Modes

Ext4 provides three configurable journaling modes, selectable in `/etc/fstab`:

| Journaling Mode | What Gets Journaled | Durability Guarantee | Write Amplification Penalty |
| :--- | :--- | :--- | :--- |
| **`data=journal`** | **Both Metadata AND User Data Payloads** | **Absolute Maximum**. Zero data loss or corruption. | **Extreme ($2\times$ Write Penalty)**. Every payload byte written twice (journal + disk). |
| **`data=ordered`** *(Default)* | **Metadata Only** (Kernel forces Data Payloads to disk *before* committing Metadata) | **Enterprise High**. Files never point to stale, unwritten blocks after crashes. | **Minimal**. Optimal throughput and latency for databases and web servers. |
| **`data=writeback`** | **Metadata Only** (Zero ordering constraints between data and metadata) | **Weak**. After crash, files can point to old, deallocated data from previous files! | **Zero Overhead**. Fastest possible throughput at risk of security data leaks. |

---

## 5. Compilable C Implementation: Inspecting Ext4 Superblock Directly from Disk

The following compilable C program opens a raw storage block device (or partition image), reads the 1024-byte superblock at offset 1024, verifies the magic number `0xEF53`, and extracts vital filesystem telemetry.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <string.h>

#define EXT4_SUPERBLOCK_OFFSET 1024
#define EXT4_MAGIC_SIGNATURE   0xEF53

// Exact packed representation of minimal ext4 superblock fields
struct __attribute__((packed)) Ext4SuperBlockHeader {
    uint32_t s_inodes_count;
    uint32_t s_blocks_count_lo;
    uint32_t s_r_blocks_count_lo;
    uint32_t s_free_blocks_count_lo;
    uint32_t s_free_inodes_count;
    uint32_t s_first_data_block;
    uint32_t s_log_block_size;
    uint32_t s_log_cluster_size;
    uint32_t s_blocks_per_group;
    uint32_t s_clusters_per_group;
    uint32_t s_inodes_per_group;
    uint32_t s_mtime;
    uint32_t s_wtime;
    uint16_t s_mnt_count;
    uint16_t s_max_mnt_count;
    uint16_t s_magic;
    uint16_t s_state;
    uint16_t s_errors;
};

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <block_device_or_image>\n", argv[0]);
        fprintf(stderr, "Example: sudo %s /dev/sda1\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *device_path = argv[1];
    int fd = open(device_path, O_RDONLY);
    if (fd < 0) {
        perror("open(device_path)");
        return EXIT_FAILURE;
    }

    // Seek to fixed superblock offset (1024 bytes)
    if (lseek(fd, EXT4_SUPERBLOCK_OFFSET, SEEK_SET) == (off_t)-1) {
        perror("lseek");
        close(fd);
        return EXIT_FAILURE;
    }

    struct Ext4SuperBlockHeader sb;
    ssize_t bytes_read = read(fd, &sb, sizeof(sb));
    if (bytes_read != sizeof(sb)) {
        perror("read(superblock)");
        close(fd);
        return EXIT_FAILURE;
    }

    close(fd);

    printf("=== Ext4 Superblock Telemetry: %s ===\n", device_path);
    printf("  Magic Signature       : 0x%04X (Expected: 0x%04X)\n", 
           sb.s_magic, EXT4_MAGIC_SIGNATURE);

    if (sb.s_magic != EXT4_MAGIC_SIGNATURE) {
        fprintf(stderr, "[ERROR] Not a valid ext4 filesystem (magic mismatch)!\n");
        return EXIT_FAILURE;
    }

    uint32_t block_size = 1024 << sb.s_log_block_size;
    uint64_t total_capacity_bytes = (uint64_t)sb.s_blocks_count_lo * block_size;

    printf("  Filesystem State      : %s\n", (sb.s_state == 1) ? "CLEAN" : "DIRTY / ERRORS");
    printf("  Block Size            : %u bytes\n", block_size);
    printf("  Total Inodes          : %u\n", sb.s_inodes_count);
    printf("  Free Inodes           : %u\n", sb.s_free_inodes_count);
    printf("  Total Blocks          : %u\n", sb.s_blocks_count_lo);
    printf("  Free Blocks           : %u\n", sb.s_free_blocks_count_lo);
    printf("  Blocks Per Group      : %u\n", sb.s_blocks_per_group);
    printf("  Inodes Per Group      : %u\n", sb.s_inodes_per_group);
    printf("  Total Storage Size    : %.2f GB\n", (double)total_capacity_bytes / (1024 * 1024 * 1024));

    return EXIT_SUCCESS;
}
```
