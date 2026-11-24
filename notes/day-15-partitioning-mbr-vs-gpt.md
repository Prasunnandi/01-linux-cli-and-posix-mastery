# Day 15: Partitioning: MBR vs GPT (fdisk, parted)

## 1. Architectural Foundations: Disk Geometry and Addressing
Storage devices expose an array of contiguous, fixed-size logical blocks indexed by an address known as the **Logical Block Address (LBA)**. Historically, disks operated with 512-byte sectors (512n). Modern Advanced Format drives utilize 4096-byte physical sectors (4Kn or 512e emulation).

Partitioning is the division of this flat linear block space into isolated logical sub-disks. The partition table resides in reserved sectors at the beginning (and end) of the storage medium.

---

## 2. Master Boot Record (MBR / DOS) Architecture
Introduced with IBM PC DOS 2.0 in 1983, the MBR resides entirely within the very first sector of the disk (**LBA 0**, exactly 512 bytes):

```
+----------------------------------------------------------------------------+
|                          LBA 0: MBR Sector (512 Bytes)                     |
+----------------------------------------------------------------------------+
| Offset 0x000 (0):   Bootstrap Machine Code (446 bytes)                     |
|                     Executes in 16-bit Real Mode during BIOS boot          |
+----------------------------------------------------------------------------+
| Offset 0x1BE (446): Partition Entry 1 (16 bytes)                           |
+----------------------------------------------------------------------------+
| Offset 0x1CE (462): Partition Entry 2 (16 bytes)                           |
+----------------------------------------------------------------------------+
| Offset 0x1DE (478): Partition Entry 3 (16 bytes)                           |
+----------------------------------------------------------------------------+
| Offset 0x1EE (494): Partition Entry 4 (16 bytes)                           |
+----------------------------------------------------------------------------+
| Offset 0x1FE (510): Boot Signature: 0x55 0xAA (2 bytes, Little-Endian)    |
+----------------------------------------------------------------------------+
```

### Anatomy of a 16-Byte MBR Partition Record
```
Byte 0:      Boot Indicator (0x80 = Active/Bootable, 0x00 = Inactive)
Byte 1-3:    Starting CHS Address (Cylinder-Head-Sector, legacy 10-bit cylinder)
Byte 4:      Partition Type ID (e.g., 0x83 = Linux Native, 0x82 = Linux Swap, 0x07 = NTFS)
Byte 5-7:    Ending CHS Address
Byte 8-11:   Starting LBA Address (32-bit unsigned little-endian integer)
Byte 12-15:  Total Sectors in Partition (32-bit unsigned little-endian integer)
```

### The Fundamental 2.19 TB Limit
Because the starting LBA and total sector counts are strictly 32-bit unsigned integers:
$$\text{Max Addressable Sectors} = 2^{32} = 4,294,967,296 \text{ sectors}$$
With standard 512-byte logical sectors:
$$\text{Max Disk Capacity} = 4,294,967,296 \times 512 \text{ bytes} = 2,199,023,255,552 \text{ bytes} \approx 2.199 \text{ TB (2.00 TiB)}$$
Any storage capacity beyond 2.19 TB on an MBR-partitioned drive is mathematically invisible to the operating system.

---

## 3. GUID Partition Table (GPT) Architecture
Defined as part of the Unified Extensible Firmware Interface (UEFI) specification, GPT replaces the legacy MBR table with a robust 64-bit LBA addressing scheme and redundant metadata protected by CRC32 checksums:

```
+----------------------------------------------------------------------------+
| LBA 0:        Protective MBR (Single type 0xEE partition spanning disk)    |
+----------------------------------------------------------------------------+
| LBA 1:        Primary GPT Header (UUID, CRC32, Disk LBAs, Entry Pointer)   |
+----------------------------------------------------------------------------+
| LBA 2 - 33:   Primary Partition Entry Array (128 partition slots, 128B ea) |
+----------------------------------------------------------------------------+
| LBA 34:       First Usable LBA                                             |
|               ... [ USER DATA PARTITIONS ] ...                             |
| LBA N - 34:   Last Usable LBA                                              |
+----------------------------------------------------------------------------+
| LBA N - 33 - N - 2: Backup Partition Entry Array (128 partition slots)     |
+----------------------------------------------------------------------------+
| LBA N:        Secondary (Backup) GPT Header at the final sector of disk    |
+----------------------------------------------------------------------------+
```

### The Protective MBR (LBA 0)
To prevent legacy MBR partitioning utilities (which know nothing of GPT) from thinking the disk is unpartitioned and overwriting GPT structures, LBA 0 contains a valid MBR with a single partition record:
- Bootable flag: `0x00`
- Partition Type: `0xEE` (GPT Protective Partition)
- Starting LBA: `1`
- Size: Set to disk size (or capped at 2TB for 32-bit field)

### Primary GPT Header (LBA 1, 92 Bytes)
- **Signature (8 bytes)**: ASCII string `"EFI PART"` (`0x5452415020494645`).
- **Revision (4 bytes)**: GPT version (typically `0x00010000` for v1.0).
- **Header Size (4 bytes)**: Usually 92 bytes (`0x0000005C`).
- **Header CRC32 (4 bytes)**: Calculated with this field zeroed out.
- **Current LBA (8 bytes)**: Must be `1`.
- **Backup LBA (8 bytes)**: Sector number of the secondary header at disk end ($N$).
- **First Usable LBA (8 bytes)**: Typically LBA 34.
- **Last Usable LBA (8 bytes)**: Typically $N - 34$.
- **Disk GUID (16 bytes)**: Unique 128-bit UUID identifying the disk.
- **Partition Entry Array LBA (8 bytes)**: Usually LBA 2.
- **Number of Partition Entries (4 bytes)**: Minimum 128 entries.
- **Size of Each Partition Entry (4 bytes)**: Typically 128 bytes.
- **Partition Entry Array CRC32 (4 bytes)**: Checksum covering the entire array.

### Partition Entry Format (128 Bytes)
- Bytes 0-15: Partition Type GUID (e.g. `0FC63DAF-8483-4772-8E79-3D69D8477DE4` for Linux filesystem data).
- Bytes 16-31: Unique Partition GUID (unique UUID per partition instance).
- Bytes 32-39: Starting LBA (64-bit unsigned integer).
- Bytes 40-47: Ending LBA inclusive (64-bit unsigned integer).
- Bytes 48-55: Attribute Flags (Bit 0: System partition; Bit 60: Read-only; Bit 62: Hidden; Bit 63: Do not automount).
- Bytes 56-127: Partition Name (36 characters in UTF-16LE).

### GPT Theoretical Capacity Limit
With 64-bit LBA addressing:
$$\text{Max Addressable Sectors} = 2^{64} \approx 1.84 \times 10^{19} \text{ sectors}$$
With 512-byte sectors:
$$\text{Max Capacity} = 2^{64} \times 512 \text{ bytes} = 9.44 \text{ Zettabytes (ZB)} = 9.44 \times 10^{21} \text{ bytes}$$

---

## 4. Production Masterclass: Compilable C GPT & MBR Inspector

Save as `partition_parser.c` and compile with `gcc -Wall -Wextra -O2 partition_parser.c -o partition_parser`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

#pragma pack(push, 1)
// MBR Partition Entry Structure (16 bytes)
typedef struct {
    uint8_t  boot_indicator;
    uint8_t  start_head;
    uint8_t  start_sector;
    uint8_t  start_cylinder;
    uint8_t  partition_type;
    uint8_t  end_head;
    uint8_t  end_sector;
    uint8_t  end_cylinder;
    uint32_t start_lba;
    uint32_t total_sectors;
} mbr_entry_t;

// GPT Header Structure (92 bytes)
typedef struct {
    char     signature[8];       // "EFI PART"
    uint32_t revision;
    uint32_t header_size;
    uint32_t header_crc32;
    uint32_t reserved;
    uint64_t current_lba;
    uint64_t backup_lba;
    uint64_t first_usable_lba;
    uint64_t last_usable_lba;
    uint8_t  disk_guid[16];
    uint64_t partition_entries_lba;
    uint32_t num_partition_entries;
    uint32_t partition_entry_size;
    uint32_t entries_crc32;
} gpt_header_t;

// GPT Partition Entry Structure (128 bytes)
typedef struct {
    uint8_t  type_guid[16];
    uint8_t  unique_guid[16];
    uint64_t start_lba;
    uint64_t end_lba;
    uint64_t attributes;
    uint16_t name_utf16[36];
} gpt_entry_t;
#pragma pack(pop)

void print_guid(const uint8_t *g) {
    printf("%02X%02X%02X%02X-%02X%02X-%02X%02X-%02X%02X-%02X%02X%02X%02X%02X%02X",
           g[3], g[2], g[1], g[0], g[5], g[4], g[7], g[6],
           g[8], g[9], g[10], g[11], g[12], g[13], g[14], g[15]);
}

int main(int argc, char **argv) {
    const char *disk_path = (argc > 1) ? argv[1] : "test_disk.img";
    int fd = open(disk_path, O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "[-] Failed to open '%s': %s\\n", disk_path, strerror(errno));
        return 1;
    }

    uint8_t sector0[512];
    if (read(fd, sector0, 512) != 512) {
        perror("read sector 0");
        close(fd);
        return 1;
    }

    uint16_t magic = sector0[510] | (sector0[511] << 8);
    printf("====================================================\\n");
    printf("LBA 0 INSPECTION: MBR Verification\\n");
    printf("====================================================\\n");
    printf("  MBR Boot Signature: 0x%04X (%s)\\n", magic, magic == 0xAA55 ? "VALID 0x55AA" : "INVALID");

    mbr_entry_t *entries = (mbr_entry_t *)(sector0 + 446);
    int is_protective_gpt = 0;

    for (int i = 0; i < 4; i++) {
        if (entries[i].partition_type == 0x00 && entries[i].total_sectors == 0) continue;
        printf("  Slot %d: Type=0x%02X, Boot=0x%02X, StartLBA=%u, Sectors=%u\\n",
               i + 1, entries[i].partition_type, entries[i].boot_indicator,
               entries[i].start_lba, entries[i].total_sectors);
        if (entries[i].partition_type == 0xEE) {
            is_protective_gpt = 1;
        }
    }

    if (!is_protective_gpt) {
        printf("[+] Disk utilizes standard legacy MBR partitioning.\\n");
        close(fd);
        return 0;
    }

    printf("\\n[+] Protective MBR (0xEE) detected. Reading Primary GPT Header at LBA 1...\\n");
    gpt_header_t gpt;
    if (read(fd, &gpt, sizeof(gpt)) != sizeof(gpt)) {
        perror("read LBA 1");
        close(fd);
        return 1;
    }

    if (strncmp(gpt.signature, "EFI PART", 8) != 0) {
        fprintf(stderr, "[-] Invalid GPT signature: %.8s\\n", gpt.signature);
        close(fd);
        return 1;
    }

    printf("====================================================\\n");
    printf("LBA 1 INSPECTION: Primary GPT Header\\n");
    printf("====================================================\\n");
    printf("  Signature           : %.8s\\n", gpt.signature);
    printf("  Revision            : 0x%08X\\n", gpt.revision);
    printf("  Header Size         : %u bytes\\n", gpt.header_size);
    printf("  Current LBA         : %llu\\n", (unsigned long long)gpt.current_lba);
    printf("  Backup LBA          : %llu\\n", (unsigned long long)gpt.backup_lba);
    printf("  First Usable LBA    : %llu\\n", (unsigned long long)gpt.first_usable_lba);
    printf("  Last Usable LBA     : %llu\\n", (unsigned long long)gpt.last_usable_lba);
    printf("  Disk GUID           : "); print_guid(gpt.disk_guid); printf("\\n");
    printf("  Partition Table LBA : %llu\\n", (unsigned long long)gpt.partition_entries_lba);
    printf("  Partition Slots     : %u (Entry Size: %u bytes)\\n",
           gpt.num_partition_entries, gpt.partition_entry_size);

    close(fd);
    return 0;
}
```

---

## 5. Production Post-Mortem: The Cloud Disk Expansion Trap
### Incident Context
An infrastructure engineer scaled up an AWS EBS volume from 1 TB to 4 TB for a core PostgreSQL database. After resizing in the AWS Console, the engineer executed:
```bash
growpart /dev/nvme1n1 1
resize2fs /dev/nvme1n1p1
```
The command abruptly failed with:
`growpart: [ERROR] disk is larger than 2TB and uses MBR partition scheme. Cannot expand beyond 2TB limit.`

### Root Cause
The base OS image was historically provisioned with legacy DOS (MBR) partitioning scheme. Although AWS EBS successfully allocated 4 TB of physical NVMe blocks, the 32-bit `total_sectors` field in the MBR partition entry strictly prevented addressing any block past 2.19 TB. Any attempt to force a larger partition would cause 32-bit integer wraparound, corrupting the filesystem superblock.

### Live In-Place Migration to GPT (Zero Data Loss)
Instead of re-creating the disk, the modern Linux utility `gdisk` allows lossless in-place conversion from MBR to GPT:
```bash
# 1. Back up partition table
sfdisk -d /dev/nvme1n1 > mbr_partition_table_backup.dump

# 2. In-place conversion using gdisk
# 'gdisk' automatically reads the MBR, converts entries to GPT format,
# and writes the Primary Header to LBA 1 and Backup Header to the very end of the 4TB disk.
sgdisk -g /dev/nvme1n1

# 3. Inform the Linux kernel of partition table change
partx -u /dev/nvme1n1

# 4. Now growpart cleanly expands into the 4TB GPT boundaries
growpart /dev/nvme1n1 1
resize2fs /dev/nvme1n1p1
```
Result: Volume expanded to 4.0 TB with zero downtime and verified data integrity.
