# Day 16: Logical Volume Management: PV, VG, LV (lvm2)

## 1. Architectural Foundations: The Limitations of Raw Partitions

Standard disk partitions (e.g. `/dev/sda1`, `/dev/sdb2`) suffer from severe operational limitations:
- **Rigid Physical Boundaries**: A partition cannot span across multiple physical disks.
- **Downtime-Heavy Resizing**: Resizing raw partitions requires unmounting, modifying partition tables, and hoping contiguous adjacent free space exists.
- **Storage Fragmentation**: Free space on `/dev/sda` cannot be used by a full partition on `/dev/sdb`.

**Logical Volume Management (LVM)** introduces an enterprise virtualization layer between physical block storage and operating system filesystems. It implements a 3-tier abstraction hierarchy:

```
+-------------------------------------------------------------------------+
|                     LVM 3-Tier Abstraction Layer                        |
+-------------------------------------------------------------------------+
| Filesystems:           [ / (root) ]            [ /var/lib/docker ]      |
|                             |                           |               |
|                             v                           v               |
| Logical Volumes (LV):   [ lv_root ]                 [ lv_docker ]       |
|                       (Allocates LEs)             (Allocates LEs)       |
|                             \                         /                |
|                              v                       v                  |
| Volume Group (VG):      +---------------------------------+             |
|                         |      vg_production (Pool)       |             |
|                         |    Physical Extents (PE): 4MB   |             |
|                         +---------------------------------+             |
|                                    /           \                        |
|                                   /             \                       |
|                                  v               v                      |
| Physical Volumes (PV):    [ /dev/nvme0n1 ]     [ /dev/sda2 ]            |
|                           (500 GB NVMe)        (2 TB SSD)               |
+-------------------------------------------------------------------------+
```

---

## 2. The 3 Tiers: Physical Volumes, Volume Groups & Logical Volumes

### 2.1 Physical Volumes (PV)
A **Physical Volume** is a raw block device (partition, whole disk, or RAID array) initialized by LVM using `pvcreate`.
- LVM writes a **PV Header** and **Metadata Area (MDA)** to the start of the device.
- The storage space is sliced into uniform chunks called **Physical Extents (PE)** (default size: **4 MB**).

### 2.2 Volume Groups (VG)
A **Volume Group** is created by pooling one or more Physical Volumes together using `vgcreate`.
- The VG aggregates all PEs from its member PVs into a single massive, unified pool of storage.
- Storage capacity can be scaled dynamically at runtime simply by adding new PVs (`vgextend`).

### 2.3 Logical Volumes (LV)
A **Logical Volume** is the virtual block device carved out of a Volume Group using `lvcreate`.
- Presents itself to the Linux kernel as a standard block device under `/dev/mapper/<vg>-<lv>` or `/dev/<vg>/<lv>`.
- Formatted with any standard filesystem (`ext4`, `xfs`).
- Composed of **Logical Extents (LE)**. In linear volumes, each LE maps 1:1 to a specific PE in the Volume Group.

---

## 3. The Linux Device Mapper Subsystem (`dm-mod`)

LVM does not perform disk I/O itself. Instead, it relies on the kernel's **Device Mapper** driver (`/dev/mapper/*`). Device Mapper provides modular targets:
1. **`dm-linear`**: Maps a continuous range of LEs to PEs across one or more physical drives.
2. **`dm-stripe`**: Stripes data across multiple PVs (similar to RAID 0) for high throughput.
3. **`dm-snapshot`**: Implements **Copy-on-Write (CoW)** point-in-time snapshots.
4. **`dm-crypt`**: Transparent disk encryption (LUKS).
5. **`dm-thin`**: Thin provisioning, enabling storage overcommit.

---

## 4. Online Volume Expansion & Zero-Downtime Operations

One of LVM's greatest superpowers is the ability to grow filesystems dynamically under active production load without unmounting.

```bash
# 1. Initialize a newly inserted 1TB drive:
$ pvcreate /dev/sdc

# 2. Add the new PV to the existing Volume Group:
$ vgextend vg_production /dev/sdc

# 3. Extend the Logical Volume by 500 GB:
$ lvextend -L +500G /dev/vg_production/lv_root

# 4. Expand the ext4 filesystem online to claim the new space:
$ resize2fs /dev/vg_production/lv_root

# Alternatively, do both in a single atomic command:
$ lvextend -r -L +500G /dev/vg_production/lv_root
```

---

## 5. LVM Snapshots & The Copy-on-Write (CoW) Write Penalty

An LVM snapshot is a frozen, point-in-time image of a logical volume created almost instantaneously.
- When `lvcreate --snapshot` is executed, no data is copied. The snapshot simply shares the exact same PEs as the origin volume.
- **Copy-On-Write (CoW)**: When a write arrives for an uncopied block on the origin volume, the kernel intercepts the write, copies the *original* block data into the snapshot's reserved space, updates the snapshot mapping table, and then executes the write on the origin volume.

```
Initial State: Origin and Snapshot point to original block
[Write Request] ---> Intercepted by Device Mapper
                      |
                      v
              1. Read Original Block A
              2. Write Block A into Snapshot Storage
              3. Overwrite Block A in Origin Volume
```

> [!CAUTION]
> Traditional LVM snapshots impose a severe **double-write penalty** on every modified block. Furthermore, if the snapshot's allocated storage fills to $100\%$, the snapshot becomes invalid and is permanently dropped by the kernel. For high-write databases, use modern **Thin-Provisioned Snapshots** (`dm-thin`).
