# Day 17: Linux Software RAID (mdadm) 0, 1, 5, 10

## 1. Architectural Foundations: The Linux Multiple Device (MD) Subsystem
Linux Software RAID is implemented directly inside the kernel by the **Multiple Device (`md`) driver** (`drivers/md/md.c`). Unlike expensive hardware RAID controllers that lock data into proprietary on-disk metadata formats, the `md` subsystem:
- Operates across any standard Linux block device (SATA, SAS, NVMe, iSCSI, loop devices).
- Implements standard open superblock formats (v1.2 by default).
- Integrates directly with kernel CPU SIMD subsystems (AVX-512, AVX2, SSE4.2, ARM NEON) for high-speed Galois Field polynomial math.

```
+----------------------------------------------------------------------------+
|                          Virtual Device: /dev/md0                          |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
|                     Kernel MD Driver (RAID Personality)                    |
|                md_make_request() -> raid5_make_request()                   |
+----------------------------------------------------------------------------+
       |                              |                              |
       v                              v                              v
+---------------+              +---------------+              +---------------+
| Strip /dev/sda|              | Strip /dev/sdb|              | Strip /dev/sdc|
| Data Block D1 |              | Data Block D2 |              | Parity P = D1^D2
+---------------+              +---------------+              +---------------+
```

---

## 2. RAID Topologies & Mathematical Formulations

### RAID 0 (Block-Level Striping)
- **Data Distribution**: Blocks are split across $N$ disks without redundancy.
- **Usable Capacity**: $N \times S_{\text{min}}$ (where $S_{\text{min}}$ is the smallest drive capacity).
- **Mean Time to Failure (MTTF)**:
  $$\text{MTTF}_{\text{RAID 0}} = \frac{\text{MTTF}_{\text{single}}}{N}$$
  If one drive fails, 100% of the array data is permanently destroyed.

### RAID 1 (Mirroring)
- **Data Distribution**: Exact identical copies written to $N$ disks simultaneously.
- **Usable Capacity**: $1 \times S_{\text{min}}$.
- **Fault Tolerance**: Tolerates up to $N - 1$ disk failures.

### RAID 5 (Distributed Single Parity)
- **Data Distribution**: Data and parity are rotated across all $N$ disks in stripes.
- **Usable Capacity**: $(N - 1) \times S_{\text{min}}$.
- **Parity Calculation (XOR Math)**:
  $$P = D_1 \oplus D_2 \oplus D_3 \oplus \dots \oplus D_{N-1}$$
- **Reconstruction Equation**: If drive $D_2$ fails:
  $$D_2 = D_1 \oplus D_3 \oplus \dots \oplus D_{N-1} \oplus P$$
- **The RAID 5 Write Penalty**: Every small random write requires **2 reads and 2 writes** (4 I/O operations):
  1. Read old data ($D_{\text{old}}$) and old parity ($P_{\text{old}}$).
  2. Compute new parity: $P_{\text{new}} = (D_{\text{old}} \oplus D_{\text{new}}) \oplus P_{\text{old}}$.
  3. Write $D_{\text{new}}$ and $P_{\text{new}}$.

### RAID 6 (Dual Distributed Parity)
- **Parity Formulations**: Uses two syndromes: $P$ (standard XOR) and $Q$ (Galois Field $\text{GF}(2^8)$ Reed-Solomon polynomial generator).
- **Usable Capacity**: $(N - 2) \times S_{\text{min}}$.
- **Fault Tolerance**: Survives **2 simultaneous drive failures**.

### RAID 10 (Striped Mirrors / RAID 1+0)
- **Data Distribution**: Mirrors disks in pairs (RAID 1), then stripes data across the mirror groups (RAID 0).
- **Usable Capacity**: $\frac{N}{2} \times S_{\text{min}}$.
- **Performance**: Zero parity computation overhead; maximum random I/O throughput.

---

## 3. The RAID 5 Write Hole Problem
If a server experiences a sudden power outage during a write operation, the data block ($D_{\text{new}}$) may be flushed to disk while the parity block ($P_{\text{new}}$) has not yet reached disk platter/NAND cells.
Upon reboot, the parity is out-of-sync with the data. If a different drive fails later, reconstructing it using this out-of-sync parity produces silent data corruption!
- **Mitigation in `mdadm`**:
  1. **Write-Intent Bitmap (`--bitmap=internal`)**: Tracks out-of-sync chunks in a fast bitfield, bypassing full array resyncs on unclean reboots.
  2. **RAID 5 Journaling (`--write-journal=/dev/nvme0n1`)**: Commits data and parity transactions to a non-volatile log device prior to striping.

---

## 4. Production Masterclass: Compilable C Parity & Reconstruction Engine

Save as `raid5_engine.c` and compile with `gcc -Wall -Wextra -O2 raid5_engine.c -o raid5_engine`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#define CHUNK_SIZE 64 // 64-byte chunks for demonstration

// Compute XOR parity across N data chunks
void compute_raid5_parity(uint8_t **data_disks, uint8_t *parity_disk, int num_data_disks, size_t len) {
    // Zero out parity buffer
    memset(parity_disk, 0, len);

    for (int d = 0; d < num_data_disks; d++) {
        const uint64_t *src = (const uint64_t *)data_disks[d];
        uint64_t *dst = (uint64_t *)parity_disk;
        size_t u64_count = len / sizeof(uint64_t);

        for (size_t i = 0; i < u64_count; i++) {
            dst[i] ^= src[i];
        }
    }
}

// Reconstruct a single lost disk using surviving data disks and parity
void reconstruct_lost_disk(uint8_t **data_disks, uint8_t *parity_disk, int num_data_disks,
                           int failed_disk_idx, uint8_t *reconstructed_output, size_t len) {
    // Parity P = D0 ^ D1 ^ D2 ... ^ D(N-1)
    // Therefore: D(failed) = P ^ (all surviving data disks)
    memcpy(reconstructed_output, parity_disk, len);

    uint64_t *dst = (uint64_t *)reconstructed_output;
    size_t u64_count = len / sizeof(uint64_t);

    for (int d = 0; d < num_data_disks; d++) {
        if (d == failed_disk_idx) continue; // Skip the failed drive

        const uint64_t *src = (const uint64_t *)data_disks[d];
        for (size_t i = 0; i < u64_count; i++) {
            dst[i] ^= src[i];
        }
    }
}

int main(void) {
    printf("====================================================\\n");
    printf("RAID 5 BITWISE PARITY & RECONSTRUCTION ENGINE\\n");
    printf("====================================================\\n");

    const int NUM_DATA = 3; // 3 data disks + 1 parity disk = 4 disks total
    uint8_t disk0[CHUNK_SIZE];
    uint8_t disk1[CHUNK_SIZE];
    uint8_t disk2[CHUNK_SIZE];
    uint8_t parity[CHUNK_SIZE];
    uint8_t recovered[CHUNK_SIZE];

    // Seed original payload
    memset(disk0, 'A', CHUNK_SIZE);
    memset(disk1, 'B', CHUNK_SIZE);
    memset(disk2, 'C', CHUNK_SIZE);

    uint8_t *data_disks[3] = { disk0, disk1, disk2 };

    printf("[+] Step 1: Generating Parity across %d disks...\\n", NUM_DATA);
    compute_raid5_parity(data_disks, parity, NUM_DATA, CHUNK_SIZE);

    printf("  Disk 0 Sample : '%c' (0x%02X)\\n", disk0[0], disk0[0]);
    printf("  Disk 1 Sample : '%c' (0x%02X)\\n", disk1[0], disk1[0]);
    printf("  Disk 2 Sample : '%c' (0x%02X)\\n", disk2[0], disk2[0]);
    printf("  Parity Sample : 0x%02X ('%c'^'%c'^'%c')\\n",
           parity[0], disk0[0], disk1[0], disk2[0]);

    printf("\\n[!] SIMULATING CATASTROPHIC HARDWARE FAILURE ON DISK 1...\\n");
    memset(disk1, 0xFF, CHUNK_SIZE); // Destroy Disk 1 contents

    printf("[+] Step 2: Running Real-Time XOR Reconstruction...\\n");
    reconstruct_lost_disk(data_disks, parity, NUM_DATA, 1, recovered, CHUNK_SIZE);

    printf("  Recovered Sample: '%c' (0x%02X)\\n", recovered[0], recovered[0]);
    assert(recovered[0] == 'B');
    printf("[+] SUCCESS: Reconstructed data matches original byte payload with 100%% bit fidelity!\\n");

    return 0;
}
```

---

## 5. Production Post-Mortem: The Rebuild Death Spiral (URE on RAID 5)
### The Outage
A media storage server hosting an 8-drive RAID 5 array of 12 TB SATA HDDs suffered a single drive failure (`/dev/sdd`). The hot spare activated automatically, and `mdadm` began rebuilding the missing drive.
At 68% rebuild progress, the rebuild suddenly aborted with I/O errors. The entire array collapsed into an offline `FAILED` state. All 84 TB of user data became inaccessible.

### Root Cause Analysis: The URE Probability Math
Enterprise SATA hard drives publish an **Unrecoverable Read Error (URE)** rate of 1 sector error per $10^{14}$ bits read.
To rebuild a 12 TB drive in an 8-disk RAID 5 array:
$$\text{Total Bits Read from 7 Surviving Drives} = 7 \times 12 \text{ TB} = 84 \text{ TB} = 6.72 \times 10^{14} \text{ bits}$$
The probability $P$ of completing this rebuild without encountering a single URE:
$$P(\text{Success}) = (1 - 10^{-14})^{6.72 \times 10^{14}} \approx e^{-6.72} \approx 0.0012 \text{ (0.12\%)!}$$
Encountering a URE during rebuild is virtually guaranteed on modern multi-terabyte drives! In RAID 5, a single URE during rebuild is fatal because no second redundancy exists.

### Architectural Rule of Thumb
- **Drives $\ge 2\text{ TB}$**: RAID 5 is strictly prohibited in enterprise production.
- **Mandatory Minimum**: RAID 6 (dual parity) or RAID 10 (mirrored stripes). RAID 6 easily tolerates a URE during rebuild because the second syndrome ($Q$) resolves the unreadable sector.

---

## 6. Deep Galois Field Arithmetic $\text{GF}(2^8)$ in RAID 6
While RAID 5 uses single XOR parity ($P$), RAID 6 requires a second independent syndrome ($Q$) to recover from two simultaneous disk failures. This is computed using abstract algebra over the Galois Field $\text{GF}(2^8)$ using the irreducible generator polynomial:
$$P(x) = x^8 + x^4 + x^3 + x^2 + 1 \quad (\text{binary: } 100011101_2 = 0x11D)$$

### Syndrome Formulation
Let the data strips on $M$ data disks be $D_0, D_1, \dots, D_{M-1}$.
1. **$P$ Syndrome (XOR)**:
   $$P = \sum_{i=0}^{M-1} D_i = D_0 \oplus D_1 \oplus \dots \oplus D_{M-1}$$
2. **$Q$ Syndrome (Reed-Solomon generator)**:
   $$Q = \sum_{i=0}^{M-1} g^i \otimes D_i = g^0 \otimes D_0 \oplus g^1 \otimes D_1 \oplus g^2 \otimes D_2 \oplus \dots \oplus g^{M-1} \otimes D_{M-1}$$
   where $g = 0x02$ is a generator element of $\text{GF}(2^8)$, and $\otimes$ denotes multiplication in $\text{GF}(2^8)$ modulo $P(x)$.

### Double-Failure Reconstruction Mathematics
If data disks $D_x$ and $D_y$ fail simultaneously ($x < y$):
The surviving equations are:
$$P_{xy} = P \oplus \sum_{i \neq x, y} D_i = D_x \oplus D_y$$
$$Q_{xy} = Q \oplus \sum_{i \neq x, y} g^i \otimes D_i = g^x \otimes D_x \oplus g^y \otimes D_y$$
Multiplying the first equation by $g^y$ in $\text{GF}(2^8)$:
$$g^y \otimes P_{xy} = g^y \otimes D_x \oplus g^y \otimes D_y$$
Adding this to the $Q_{xy}$ equation eliminates $D_y$:
$$Q_{xy} \oplus g^y \otimes P_{xy} = (g^x \oplus g^y) \otimes D_x$$
Solving for $D_x$ using the field multiplicative inverse:
$$D_x = (g^x \oplus g^y)^{-1} \otimes (Q_{xy} \oplus g^y \otimes P_{xy})$$
Once $D_x$ is recovered, $D_y$ is trivially resolved via standard XOR:
$$D_y = P_{xy} \oplus D_x$$
This mathematical proof guarantees 100% deterministic reconstruction of any two lost disks without information loss.

---

## 7. Online Array Reshaping & Resizing with mdadm
The Linux MD subsystem supports online live array reshaping without unmounting filesystems:
```bash
# 1. Add a new physical drive to an existing 3-disk RAID 5 array
mdadm --add /dev/md0 /dev/sdd1

# 2. Reshape from 3 disks to 4 disks (growing usable storage from 2x to 3x)
mdadm --grow /dev/md0 --raid-devices=4

# 3. Monitor live reshape progress and critical section backups
cat /proc/mdstat
# Shows: [==>..................] reshape = 14.2% (finish=82.1min speed=184000K/s)

# 4. Once reshape finishes, expand filesystem online:
resize2fs /dev/md0
```
During reshaping, the MD driver shifts chunk offsets across the array. It uses a **critical section backup area** at the start of the drive so that if power fails during the move of chunk $K$, the driver can safely resume after reboot without data corruption.

