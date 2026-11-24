# Day 18: Archival & High-Speed Compression (tar, zstd)

## 1. Architectural Foundations: Unix Tape Archival (tar)
The `tar` (Tape Archive) format originated in Unix Version 7 (1979) to serialize hierarchical file trees, permissions, and metadata into a continuous byte stream suitable for linear magnetic tapes.

Unlike modern archive formats like `.zip` or `.7z`, standard `tar` contains **no centralized index or central directory at the beginning or end of the file**. An archive is an unindexed linear sequence of records. Finding a file at the end of a 1 TB tar archive requires linearly scanning through all preceding archive data.

```
+----------------------------------------------------------------------------+
|                          POSIX ustar Archive Stream                        |
+----------------------------------------------------------------------------+
| Block 0 (512B)   : Header for "file1.txt"                                  |
+----------------------------------------------------------------------------+
| Block 1-2 (1024B): Data Payload for "file1.txt" (padded to 512B boundary)  |
+----------------------------------------------------------------------------+
| Block 3 (512B)   : Header for "file2.bin"                                  |
+----------------------------------------------------------------------------+
| Block 4 (512B)   : Data Payload for "file2.bin"                            |
+----------------------------------------------------------------------------+
| Block 5-6 (1024B): End of Archive (Two consecutive 512-byte zero blocks)   |
+----------------------------------------------------------------------------+
```

---

## 2. POSIX ustar Header Specification
Every file entry begins with a 512-byte header block formatted in ASCII octal numbers:

```c
struct posix_header {
    char name[100];     /* File name */
    char mode[8];       /* Permissions (octal ASCII) */
    char uid[8];        /* User ID (octal ASCII) */
    char gid[8];        /* Group ID (octal ASCII) */
    char size[12];      /* File size in bytes (octal ASCII) */
    char mtime[12];     /* Last modification time (octal ASCII) */
    char chksum[8];     /* Header checksum (octal ASCII) */
    char typeflag;      /* Type flag (see below) */
    char linkname[100]; /* Target name of link */
    char magic[6];      /* "ustar\\0" */
    char version[2];    /* "00" */
    char uname[32];     /* User name */
    char gname[32];     /* Group name */
    char devmajor[8];   /* Device major number */
    char devminor[8];   /* Device minor number */
    char prefix[155];   /* Prefix for long pathnames */
    char pad[12];       /* Padding to align to 512 bytes */
};
```

### Type Flags (`typeflag`)
- `'0'` or `'\0'`: Regular file
- `'1'`: Hard link
- `'2'`: Symbolic link
- `'3'`: Character special device
- `'4'`: Block special device
- `'5'`: Directory
- `'6'`: FIFO / named pipe

### Header Checksum Calculation
The checksum field (`chksum`) is computed as the simple unsigned sum of all 512 bytes in the header block, with the 8 bytes of the `chksum` field itself treated as spaces (`0x20`).

---

## 3. High-Speed Compression Algorithms: Comparison Matrix

| Algorithm | Compression Speed (MB/s) | Decompression Speed (MB/s) | Ratio | Memory Overhead | Underlying Mathematics |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **gzip / DEFLATE** | ~35 MB/s | ~250 MB/s | 2.7x | ~128 KB | LZ77 sliding window + Huffman coding |
| **bzip2** | ~12 MB/s | ~35 MB/s | 3.3x | ~8 MB | Burrows-Wheeler Transform + Run-Length + Huffman |
| **xz / LZMA2** | ~3 MB/s | ~80 MB/s | 3.8x | ~64 MB - 512 MB | LZ77 with large dictionary + Range Encoder |
| **zstd (Zstandard)** | **~500 MB/s** (lvl 1) | **~1500 MB/s** | 3.2x | ~1 MB - 8 MB | LZ77 + Finite State Entropy (tANS) |

### Why Zstandard (zstd) Dominates Modern Systems
1. **tANS (Asymmetric Numeral Systems)**: Replaces traditional Huffman entropy coding. ANS achieves the theoretical compression limit of arithmetic coding with the extreme execution speed of table-driven finite state machines.
2. **Decompression Independent of Level**: A file compressed at `zstd -19` (maximum compression) decompresses at nearly the exact same ultra-high speed (~1.5 GB/s) as level 1!
3. **Multi-Threading**: Native chunking (`zstd -T0`) scales linearly across all CPU cores.

---

## 4. Production Masterclass: Compilable C POSIX ustar Archive Reader

Save as `tar_reader.c` and compile with `gcc -Wall -Wextra -O2 tar_reader.c -o tar_reader`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

#pragma pack(push, 1)
typedef struct {
    char name[100];
    char mode[8];
    char uid[8];
    char gid[8];
    char size[12];
    char mtime[12];
    char chksum[8];
    char typeflag;
    char linkname[100];
    char magic[6];
    char version[2];
    char uname[32];
    char gname[32];
    char devmajor[8];
    char devminor[8];
    char prefix[155];
    char pad[12];
} ustar_header_t;
#pragma pack(pop)

// Parse octal ASCII string into uint64_t
uint64_t parse_octal(const char *str, size_t max_len) {
    uint64_t val = 0;
    for (size_t i = 0; i < max_len && str[i] != '\\0' && str[i] != ' '; i++) {
        if (str[i] >= '0' && str[i] <= '7') {
            val = (val << 3) | (str[i] - '0');
        }
    }
    return val;
}

int verify_checksum(const ustar_header_t *hdr) {
    const uint8_t *bytes = (const uint8_t *)hdr;
    uint32_t expected = parse_octal(hdr->chksum, sizeof(hdr->chksum));
    uint32_t sum = 0;

    for (size_t i = 0; i < 512; i++) {
        // Treat the 8 bytes of chksum field as ASCII spaces (0x20)
        if (i >= 148 && i < 156) {
            sum += ' ';
        } else {
            sum += bytes[i];
        }
    }
    return sum == expected;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("Usage: %s <archive.tar>\\n", argv[0]);
        return 1;
    }

    int fd = open(argv[1], O_RDONLY);
    if (fd < 0) {
        perror("open");
        return 1;
    }

    printf("====================================================\\n");
    printf("POSIX ustar ARCHIVE SCANNER: %s\\n", argv[1]);
    printf("====================================================\\n");

    ustar_header_t hdr;
    int entry_count = 0;

    while (read(fd, &hdr, 512) == 512) {
        // Check for end of archive (all zeros block)
        if (hdr.name[0] == '\\0') {
            break;
        }

        if (strncmp(hdr.magic, "ustar", 5) != 0) {
            fprintf(stderr, "[-] Non-ustar block encountered. Halting.\\n");
            break;
        }

        if (!verify_checksum(&hdr)) {
            fprintf(stderr, "[-] Checksum verification failed on entry: %s\\n", hdr.name);
            break;
        }

        entry_count++;
        uint64_t size = parse_octal(hdr.size, sizeof(hdr.size));
        uint64_t mode = parse_octal(hdr.mode, sizeof(hdr.mode));

        const char *t_desc = "Regular File";
        if (hdr.typeflag == '5') t_desc = "Directory";
        else if (hdr.typeflag == '2') t_desc = "Symlink";

        printf("[%03d] %-12s | Mode: %04o | Size: %8llu bytes | Name: %s\\n",
               entry_count, t_desc, (unsigned int)mode, (unsigned long long)size, hdr.name);

        // Advance to next 512-byte boundary
        uint64_t data_blocks = (size + 511) / 512;
        lseek(fd, data_blocks * 512, SEEK_CUR);
    }

    printf("====================================================\\n");
    printf("Scanned %d valid archive entries successfully.\\n", entry_count);
    close(fd);
    return 0;
}
```

---

## 5. Production Post-Mortem: The Zip/Tar Bomb Denial-of-Service
### The Outage
A microservice accepting user profile photo uploads crashed violently. The entire host experienced an Out-of-Memory (OOM) panic, killing production Redis and Gateway containers.

### Root Cause Analysis
An attacker uploaded a 42 KB archive named `archive.tar.gz`.
Internally, the archive contained a 10 GB file composed entirely of zeros (`/dev/zero`). Due to DEFLATE/LZ77 run-length encoding:
$$\text{Compression Ratio} = \frac{10 \times 10^9 \text{ bytes}}{42 \times 10^3 \text{ bytes}} \approx 238,000 : 1$$
The backend code piped the decompressor directly into an in-memory buffer (`io.ReadAll(gzipReader)`), consuming all 64 GB of host RAM in 800 milliseconds until the Linux kernel OOM-killer fired.

### Architectural Defense
1. **Never read decompressed streams unbounded into memory**: Enforce a strict `LimitReader` (e.g. max 50 MB).
2. **Inspect Tar Headers Before Extraction**: Parse the 512-byte headers iteratively. Sum logical `size` fields before allocating disk blocks. Abort if cumulative size exceeds quota.
