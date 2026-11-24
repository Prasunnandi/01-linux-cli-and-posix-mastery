# Day 18: Archival & High-Speed Compression (tar, zstd)

## 1. Architectural Foundations: Archiving vs Compression

In the Unix ecosystem, the tasks of **combining multiple files into a single stream** and **compressing data to reduce byte size** are strictly decoupled:
- **Archiver (`tar`)**: Serializes directory hierarchies, metadata, permissions, and file contents into a contiguous binary byte stream.
- **Compressor (`gzip`, `bzip2`, `xz`, `zstd`)**: Consumes an arbitrary byte stream and applies entropy coding and dictionary algorithms to remove redundancy.

---

## 2. Anatomy of a POSIX `tar` Header (Ustar Format)

A `.tar` (Tape Archive) file is structured as a sequence of **512-byte blocks**. Every file is preceded by a 512-byte header block, followed by the file's data rounded up to the nearest 512 bytes, and terminated by two consecutive zero-filled 512-byte blocks.

```
+-------------------------------------------------------------------------+
|                  POSIX Ustar Header Block (512 Bytes)                   |
+-------------------------------------------------------------------------+
| Offset (Bytes) | Size (Bytes) | Description                             |
+----------------+--------------+-----------------------------------------+
| 0              | 100 bytes    | File Name (NUL-terminated ASCII)        |
| 100            | 8 bytes      | File Mode (Octal ASCII string)          |
| 108            | 8 bytes      | Owner UID (Octal ASCII string)          |
| 116            | 8 bytes      | Owner GID (Octal ASCII string)          |
| 124            | 12 bytes     | File Size in Bytes (Octal ASCII string) |
| 136            | 12 bytes     | Modification Time (mtime in Octal)      |
| 148            | 8 bytes      | Header Checksum (Simple sum of bytes)   |
| 156            | 1 byte       | Type Flag ('0'=regular, '2'=symlink)    |
| 157            | 100 bytes    | Target Name (for symbolic links)        |
| 257            | 6 bytes      | Magic String ("ustar\0")                |
| 263            | 2 bytes      | Ustar Version ("00")                    |
| 265            | 32 bytes     | Owner User Name                         |
| 297            | 32 bytes     | Owner Group Name                        |
| 345            | 155 bytes    | Filename Prefix (for paths > 100 chars) |
| 500            | 12 bytes     | Zero Padding to fill 512-byte block     |
+----------------+--------------+-----------------------------------------+
```

---

## 3. Modern Compression Algorithms: Gzip vs XZ vs Zstandard (Zstd)

Compression algorithms navigate a fundamental trade-off: **Compression Ratio** vs **Compression Throughput (MB/s)**.

```
Throughput (MB/s)
  ^
  |   [ Zstandard (Level 3) ]   <-- 500+ MB/s, Gzip-beating ratio
  |          \
  |           \   [ Gzip ]     <-- Legacy standard, 40 MB/s
  |            \
  |             \  [ XZ / LZMA ] <-- Maximum ratio, extremely slow (5 MB/s)
  +------------------------------------------------------------> Compression Ratio
```

### 3.1 Zstandard (Zstd) by Yann Collet (Meta)
Zstandard revolutionized enterprise compression by combining:
1. **LZ77 Match Finding**: Eliminates duplicated byte sequences across sliding windows.
2. **Finite State Entropy (FSE)**: A cutting-edge Asymmetric Numeral Systems (ANS) entropy coder that matches Huffman/Arithmetic coding precision at near-memory bus speeds.

### 3.2 Production Benchmark Comparison

| Compressor | Algorithm | Compression Speed | Decompression Speed | Ratio |
| :--- | :--- | :--- | :--- | :--- |
| **`gzip -6`** | DEFLATE (LZ77+Huffman) | $35\text{ MB/s}$ | $250\text{ MB/s}$ | $2.75\times$ |
| **`bzip2 -9`** | Burrows-Wheeler Transform | $12\text{ MB/s}$ | $35\text{ MB/s}$ | $3.10\times$ |
| **`xz -9`** | LZMA2 | $4\text{ MB/s}$ | $70\text{ MB/s}$ | $3.45\times$ |
| **`zstd -3`** *(Default)* | FSE + LZ77 | **$550\text{ MB/s}$** | **$1600\text{ MB/s}$** | **$2.90\times$** |
| **`zstd -19`** *(Ultra)* | FSE + LZ77 | $8\text{ MB/s}$ | $1400\text{ MB/s}$ | $3.50\times$ |

### High-Throughput Production Pipelines:
```bash
# Parallel multi-threaded Zstd archive of 500GB log directory:
$ tar -I 'zstd -T0 -3' -cf logs_backup.tar.zst /var/log/

# Extract high-speed archive:
$ tar -I 'zstd -T0' -xf logs_backup.tar.zst
```
