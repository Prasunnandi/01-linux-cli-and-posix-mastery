# Day 15: Partitioning: MBR vs GPT (fdisk, parted)

## 1. Architectural Foundations: Storage Partitioning

A physical storage device (HDD, SSD, NVMe) presents itself to the operating system as a linear sequence of addressable **Logical Blocks** (typically 512 bytes or 4096 bytes each), addressed sequentially via **Logical Block Addressing (LBA)**: $\text{LBA } 0, \text{LBA } 1, \text{LBA } 2, \dots, \text{LBA } N-1$.

To isolate operating systems, swap spaces, and filesystems, the drive must be segmented into partitions using a standard partition table format. Two primary architectures exist:
1. **Master Boot Record (MBR)**: Designed in 1983 for IBM PC DOS.
2. **GUID Partition Table (GPT)**: Modern standard defined as part of the Unified Extensible Firmware Interface (UEFI) specification.

---

## 2. Master Boot Record (MBR) Architecture & The 2.2 TB Limit

The MBR resides in the very first 512-byte physical sector of the drive (**LBA 0**).

```
+-------------------------------------------------------------------------+
|                  Master Boot Record (MBR) LBA 0 (512 Bytes)             |
+-------------------------------------------------------------------------+
| Offset (Bytes) | Size (Bytes) | Description                             |
+----------------+--------------+-----------------------------------------+
| 0x000 - 0x1BD  | 446 bytes    | Bootstrap Machine Code (Stage 1 Loader) |
| 0x1BE - 0x1CD  | 16 bytes     | Partition Table Entry 1                 |
| 0x1CE - 0x1DD  | 16 bytes     | Partition Table Entry 2                 |
| 0x1DE - 0x1ED  | 16 bytes     | Partition Table Entry 3                 |
| 0x1EE - 0x1FD  | 16 bytes     | Partition Table Entry 4                 |
| 0x1FE - 0x1FF  | 2 bytes      | Boot Signature (0x55, 0xAA)             |
+----------------+--------------+-----------------------------------------+
```

### 2.1 Anatomy of a 16-Byte MBR Partition Record
Each partition entry contains:
- `0x00`: Bootable Flag (`0x80` = active/bootable, `0x00` = inactive).
- `0x01 - 0x03`: Starting CHS (Cylinder-Head-Sector) address (legacy).
- `0x04`: Partition Type ID (`0x83` = Linux Native, `0x82` = Linux Swap, `0x07` = NTFS).
- `0x05 - 0x07`: Ending CHS address.
- `0x08 - 0x0B`: **Starting LBA Sector** (32-bit unsigned integer, Little-Endian).
- `0x0C - 0x0F`: **Total Sector Count** (32-bit unsigned integer, Little-Endian).

### 2.2 The Mathematical Proof of the 2.2 TB MBR Limit
The MBR partition table allocates exactly **32 bits** to store the total sector count of a partition. Assuming the standard legacy sector size of **512 bytes**:

$$\text{Maximum Addressable Sectors} = 2^{32} = 4,294,967,296\text{ sectors}$$

$$\text{Maximum Capacity} = 4,294,967,296 \times 512\text{ bytes} = 2,199,023,255,552\text{ bytes}$$

$$2,199,023,255,552\text{ bytes} = \frac{2^{32} \times 2^9}{2^{40}}\text{ TiB} = 2.0\text{ TiB} \approx 2.199\text{ TB}$$

Any disk capacity exceeding $2.199\text{ TB}$ cannot be addressed by an MBR partition table; excess storage is permanently invisible and wasted.

---

## 3. GUID Partition Table (GPT) Architecture

GPT replaces the archaic 512-byte MBR with an extensible, 64-bit, highly redundant layout.

```
+-------------------------------------------------------------------------+
|                  GUID Partition Table (GPT) Disk Layout                 |
+-------------------------------------------------------------------------+
| LBA 0          | Protective MBR (Type 0xEE, prevents legacy corruption) |
+----------------+--------------------------------------------------------+
| LBA 1          | Primary GPT Header (Disk GUID, CRC32 checksums, bounds)|
+----------------+--------------------------------------------------------+
| LBA 2 - 33     | Primary Partition Entries (128 entries x 128 bytes)    |
+----------------+--------------------------------------------------------+
| LBA 34 ...     | User Data Partitions                                   |
| ... N - 34     |                                                        |
+----------------+--------------------------------------------------------+
| LBA N - 33..N-2| Secondary (Backup) Partition Entries                   |
+----------------+--------------------------------------------------------+
| LBA N - 1      | Secondary (Backup) GPT Header                          |
+----------------+--------------------------------------------------------+
```

### 3.1 Architectural Advantages of GPT:
1. **Massive Capacity**: Uses 64-bit sector numbers. With 512-byte sectors:
   $$\text{Capacity} = 2^{64} \times 512\text{ bytes} = 9.44 \times 10^{21}\text{ bytes} = 8\text{ Zettabytes (ZB)}$$
2. **Globally Unique Identifiers (UUIDs)**: Every disk and partition is assigned a random 128-bit UUID, eliminating drive re-ordering bugs (`/dev/sda` swapping with `/dev/sdb`).
3. **Partition Redundancy & CRC32**: Both the header and partition entries are duplicated at the very end of the physical disk. Both headers store a CRC32 checksum of themselves and the partition table; if disk corruption occurs, the kernel detects it and restores state from the backup table.
4. **Protective MBR**: LBA 0 contains an MBR with a single partition covering the entire drive marked with type **`0xEE` (GPT Protective)**. Legacy utilities see the disk as fully occupied, preventing accidental overwrites.

---

## 4. Partitioning Tools: `fdisk` vs `parted`

| Feature | `fdisk` (util-linux) | `parted` (GNU parted) |
| :--- | :--- | :--- |
| **Interface** | Interactive menu-driven CLI | Both interactive and non-interactive scripted |
| **Partition Tables** | Supports MBR and GPT | Supports MBR, GPT, Mac, BSD, Sun |
| **Partition Resizing** | Delete and recreate with same start sector | Native `resizepart` command |
| **Sector Alignment** | Auto-aligns to 1MB (2048 sectors) | Requires explicit `--align optimal` |

### Scripted Non-Interactive Partitioning with `parted`:
```bash
# Create a GPT partition table:
$ parted -s /dev/sdb mklabel gpt

# Create an EFI System Partition (512MB):
$ parted -s /dev/sdb mkpart "EFI" fat32 1MiB 513MiB
$ parted -s /dev/sdb set 1 esp on

# Create a Linux Root Partition using optimal 1MB alignment:
$ parted -s -a optimal /dev/sdb mkpart "root" ext4 513MiB 100%
```
