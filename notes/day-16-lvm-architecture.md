# Day 16: Logical Volume Management: PV, VG, LV (lvm2)

## 1. Architectural Foundations: The Storage Virtualization Stack
Traditional disk partitioning binds filesystems directly to physical sector ranges. If a filesystem fills its partition, expanding it requires contiguous unallocated sectors immediately following it—an impossibility if another partition follows.

Linux Logical Volume Manager (LVM2) abstracts physical storage into a dynamic, pooled allocation architecture using the Linux kernel **Device Mapper (`dm`)** framework.

```
+----------------------------------------------------------------------------+
|                             Filesystem (ext4 / xfs)                        |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| Logical Volume (LV): /dev/mapper/vg_data-lv_app  (e.g., 500 GB)            |
| Composed of contiguous Logical Extents: LE 0, LE 1, LE 2 ... LE 127999     |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| Volume Group (VG): vg_data  (Pool of Physical Extents, e.g., PE size = 4MB) |
+----------------------------------------------------------------------------+
                   |                                       |
                   v                                       v
+-------------------------------------+ +-------------------------------------+
| Physical Volume (PV 1): /dev/nvme0n1 | | Physical Volume (PV 2): /dev/nvme1n1 |
| PE 0 ... PE 63999 (256 GB)          | | PE 0 ... PE 63999 (256 GB)          |
+-------------------------------------+ +-------------------------------------+
```

### The Three Architectural Tiers
1. **Physical Volume (PV)**: A raw block device (e.g. `/dev/sda2`, `/dev/nvme0n1`) initialized with an LVM label at sector 1 (LBA 1). It is divided into uniform allocation units called **Physical Extents (PE)**, typically 4 MiB in size.
2. **Volume Group (VG)**: A storage pool aggregating one or more PVs into a unified heap of free PEs. A VG defines the extent size (e.g., 4 MiB, 8 MiB, 64 MiB).
3. **Logical Volume (LV)**: A virtual block device carved out of a VG. An LV is composed of **Logical Extents (LE)**. The kernel Device Mapper maps each LE to an arbitrary PE anywhere within the VG:
$$\text{LE}_i \xrightarrow{\text{Device Mapper}} \text{PE}_j \text{ on PV}_k$$

---

## 2. Kernel Device Mapper Internals
Device Mapper (`drivers/md/dm.c`) is the kernel subsystem that translates block I/O requests between virtual target devices and underlying block devices.
When userspace runs `lvs` or `lvcreate`, `liblvm2cmd` communicates with the kernel via `ioctl(fd, DM_TABLE_LOAD, ...)` against the character device `/dev/mapper/control`.

### Device Mapper Target Types
- **`dm-linear`**: Concatenates extent ranges across physical volumes. Table format:
  ```
  # logical_start_sector num_sectors linear target_dev target_start_sector
  0 20971520 linear /dev/nvme0n1 2048
  20971520 20971520 linear /dev/nvme1n1 2048
  ```
- **`dm-striped`**: Interleaves reads and writes across multiple PVs for high throughput (RAID 0 equivalent).
- **`dm-snapshot`**: Implements Copy-on-Write (COW) point-in-time snapshots.
- **`dm-thin`**: Thin-provisioning pool supporting over-provisioned virtual volumes.
- **`dm-crypt`**: Transparent block-level encryption (LUKS).

---

## 3. Thin Provisioning and Copy-on-Write (COW) Snapshots

```
[ Active Logical Volume ]                      [ Read-Only Snapshot LV ]
          |                                                |
          +-----------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    | Shared Base Data Blocks   |  (Blocks unchanged since snapshot)
                    +---------------------------+
                      /                       \\
                     v                         v
       [ New Overwrites to Active ]    [ Saved Original Pre-Write Blocks ]
       (Stored in Active Thin Pool)    (Preserved in COW metadata area)
```

### The Mechanics of COW
1. When a snapshot is created, no data is copied. The snapshot simply references the existing extent pointers. Creation is instantaneous ($O(1)$).
2. When a write arrives for block $B$ on the origin volume:
   - The kernel DM intercept halts the write.
   - The original contents of block $B$ are read and copied into the snapshot's reserved COW volume.
   - The pending write is allowed to overwrite block $B$ on the origin volume.
   - Subsequent writes to block $B$ incur zero overhead because the pre-snapshot state is already preserved.

### The Snapshot Invalidation Hazard
If the snapshot's allocated COW storage pool fills to 100%:
- The kernel cannot preserve any more original blocks.
- The snapshot becomes **invalidated** (`[INACTIVE]` state) and is permanently dropped by the kernel to protect the active origin volume from write failures.

---

## 4. Production Masterclass: Compilable C Userspace Extent Mapper

Save as `dm_extent_mapper.c` and compile with `gcc -Wall -Wextra -O2 dm_extent_mapper.c -o dm_extent_mapper`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define EXTENT_SIZE_BYTES (4 * 1024 * 1024) // 4 MiB Extents
#define SECTOR_SIZE       512
#define EXTENT_SECTORS    (EXTENT_SIZE_BYTES / SECTOR_SIZE) // 8192 sectors

typedef struct {
    uint32_t pe_index;
    char     pv_name[32];
    uint64_t pv_offset_bytes;
} physical_extent_t;

typedef struct {
    uint32_t          le_index;
    physical_extent_t mapped_pe;
} logical_extent_t;

typedef struct {
    char             lv_name[32];
    uint32_t         total_extents;
    logical_extent_t *extents;
} logical_volume_t;

// Translate a virtual byte offset in the Logical Volume to its exact physical location
int translate_lv_offset(const logical_volume_t *lv, uint64_t lv_byte_offset,
                        char *out_pv, uint64_t *out_pv_byte_offset) {
    uint32_t le_idx = lv_byte_offset / EXTENT_SIZE_BYTES;
    uint64_t offset_within_extent = lv_byte_offset % EXTENT_SIZE_BYTES;

    if (le_idx >= lv->total_extents) {
        return -1; // Out of bounds
    }

    const logical_extent_t *le = &lv->extents[le_idx];
    strncpy(out_pv, le->mapped_pe.pv_name, 32);
    *out_pv_byte_offset = le->mapped_pe.pv_offset_bytes + offset_within_extent;
    return 0;
}

int main(void) {
    printf("====================================================\\n");
    printf("LVM2 EXTENT TRANSLATION ENGINE SIMULATOR\\n");
    printf("Extent Size: %d MiB (%d sectors)\\n", EXTENT_SIZE_BYTES / (1024*1024), EXTENT_SECTORS);
    printf("====================================================\\n");

    // Construct a simulated 12 MiB Logical Volume spanning two different Physical Volumes
    logical_volume_t lv;
    strncpy(lv.lv_name, "lv_production_db", sizeof(lv.lv_name));
    lv.total_extents = 3;
    lv.extents = malloc(sizeof(logical_extent_t) * lv.total_extents);

    // LE 0 -> PV1 (/dev/nvme0n1) PE 100
    lv.extents[0].le_index = 0;
    strncpy(lv.extents[0].mapped_pe.pv_name, "/dev/nvme0n1", 32);
    lv.extents[0].mapped_pe.pe_index = 100;
    lv.extents[0].mapped_pe.pv_offset_bytes = (uint64_t)100 * EXTENT_SIZE_BYTES;

    // LE 1 -> PV1 (/dev/nvme0n1) PE 101
    lv.extents[1].le_index = 1;
    strncpy(lv.extents[1].mapped_pe.pv_name, "/dev/nvme0n1", 32);
    lv.extents[1].mapped_pe.pe_index = 101;
    lv.extents[1].mapped_pe.pv_offset_bytes = (uint64_t)101 * EXTENT_SIZE_BYTES;

    // LE 2 -> PV2 (/dev/nvme1n1) PE 5 (Discontiguous span across second physical drive!)
    lv.extents[2].le_index = 2;
    strncpy(lv.extents[2].mapped_pe.pv_name, "/dev/nvme1n1", 32);
    lv.extents[2].mapped_pe.pe_index = 5;
    lv.extents[2].mapped_pe.pv_offset_bytes = (uint64_t)5 * EXTENT_SIZE_BYTES;

    // Query virtual byte offsets:
    uint64_t test_offsets[] = {
        0,                      // Start of LE 0
        4194304 + 1024,         // 1024 bytes into LE 1
        8388608 + 2048          // 2048 bytes into LE 2 (on second NVMe drive)
    };

    for (int i = 0; i < 3; i++) {
        uint64_t off = test_offsets[i];
        char pv[32];
        uint64_t physical_off;

        if (translate_lv_offset(&lv, off, pv, &physical_off) == 0) {
            printf("[VFS Read] Virtual Offset: %10llu bytes -> Target: %-15s Physical Offset: %10llu bytes\\n",
                   (unsigned long long)off, pv, (unsigned long long)physical_off);
        }
    }

    free(lv.extents);
    return 0;
}
```

---

## 5. Production Post-Mortem: The Thin Snapshot Cascade Freeze
### The Outage
A high-throughput PostgreSQL payment processing cluster experienced an abrupt complete I/O hang across all read and write transactions. The database server reported `D-state` (uninterruptible sleep) threads spiking to 350. Load average surged to 400.00.

### Root Cause Analysis
An automated backup script executed nightly created an LVM snapshot:
```bash
lvcreate -s -L 20G -n db_snap /dev/vg_prod/lv_database
```
The snapshot volume was allocated only 20 GB. During peak midnight batch settlement, the primary database performed 45 GB of random updates.
As the snapshot COW table filled past 100%, LVM's default configuration in `/etc/lvm/lvm.conf` had:
`snapshot_autoextend_threshold = 100` (auto-extend disabled).
The kernel driver detected COW allocation failure. Under the configured safety mode, the device mapper locked the table, freezing all incoming I/O to prevent silent silent filesystem corruption.

### Remediation & Architectural Protection
1. **Dynamic Extension Configuration**:
   In `/etc/lvm/lvm.conf`, configure dynamic threshold alerting:
   ```ini
   activation {
       snapshot_autoextend_threshold = 70
       snapshot_autoextend_percent = 20
   }
   ```
   When snapshot usage exceeds 70%, `dmeventd` automatically invokes `lvextend` to grow the COW pool before exhaustion.
2. **Monitoring**:
   Add Prometheus node-exporter alert for `lvm_thinpool_data_percent > 80`.
