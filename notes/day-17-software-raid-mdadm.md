# Day 17: Linux Software RAID (mdadm) 0, 1, 5, 10

## 1. Architectural Foundations: Redundant Array of Independent Disks (RAID)

Enterprise storage systems demand both **fault tolerance** (surviving sudden physical drive failures without data loss) and **high performance** (aggregating I/O throughput across multiple physical disks). While hardware RAID controllers rely on proprietary PCI cards with battery-backed cache, Linux **Software RAID** via the kernel's **`md` (Multiple Devices)** driver offers superior transparency, CPU-accelerated parity calculations, and zero vendor lock-in.

---

## 2. RAID Level Taxonomy & Mathematical Proofs

```
+-------------------------------------------------------------------------+
|                         RAID Level Comparison                           |
+-------------------------------------------------------------------------+
| Level   | Architecture        | Fault Tolerance | Usable Capacity       |
+---------+---------------------+-----------------+-----------------------+
| RAID 0  | Block Striping      | 0 Disks (None)  | N x Disk Capacity     |
| RAID 1  | Mirroring           | N - 1 Disks     | 1 x Disk Capacity     |
| RAID 5  | Distributed Parity  | 1 Disk          | (N - 1) x Capacity    |
| RAID 6  | Dual Parity (Reed-S)| 2 Disks         | (N - 2) x Capacity    |
| RAID 10 | Stripe of Mirrors   | 1 Disk per Mirr | (N / 2) x Capacity    |
+---------+---------------------+-----------------+-----------------------+
```

### 2.1 The Mathematics of RAID 5 XOR Parity
RAID 5 distributes single-parity data blocks cyclically across all member drives. The parity block $P$ is computed using the bitwise exclusive-OR (XOR, $\oplus$) operation across all data blocks in the stripe:

$$P = D_1 \oplus D_2 \oplus D_3$$

**Truth Table of XOR & Self-Inversion Property:**
The XOR operation has the mathematical property that $A \oplus A = 0$ and $A \oplus 0 = A$. Therefore:

$$D_2 = P \oplus D_1 \oplus D_3$$

If Disk 2 suffers a catastrophic physical hardware failure, the kernel reconstructs its missing data blocks in real time on the fly simply by XORing the surviving data disks ($D_1, D_3$) with the parity disk ($P$)!

### 2.2 The RAID 5 Write Hole Problem
A single logical write to a RAID 5 array requires four distinct physical disk I/O operations (the **Read-Modify-Write cycle**):
1. Read Old Data ($D_{old}$)
2. Read Old Parity ($P_{old}$)
3. Calculate New Parity: $P_{new} = (D_{old} \oplus D_{new}) \oplus P_{old}$
4. Write New Data ($D_{new}$) and Write New Parity ($P_{new}$)

If power is abruptly severed between writing $D_{new}$ and $P_{new}$, the parity block becomes out-of-sync with the data block. This state is known as the **Write Hole**. Modern Linux `mdadm` resolves this by enabling a dedicated write-ahead journal (`--write-journal`) on NVMe storage.

---

## 3. Production Operations with `mdadm`

```bash
# 1. Create a 3-disk RAID 5 array with 1 hot spare:
$ mdadm --create /dev/md0 --level=5 --raid-devices=3 /dev/sdb /dev/sdc /dev/sdd --spare-devices=1 /dev/sde

# 2. Inspect real-time sync and rebuild status:
$ cat /proc/mdstat
Personalities : [raid6] [raid5] [raid4] 
md0 : active raid5 sdd[2] sde[3](S) sdc[1] sdb[0]
      41943040 blocks super 1.2 level 5, 512k chunk, algorithm 2 [3/3] [UUU]

# 3. Simulate a physical disk failure on /dev/sdb:
$ mdadm /dev/md0 --fail /dev/sdb

# 4. Remove the failed drive and add a replacement:
$ mdadm /dev/md0 --remove /dev/sdb
$ mdadm /dev/md0 --add /dev/sdf
```

### 3.1 The Danger of Unrecoverable Read Errors (URE) During Rebuild
When a drive fails in an $8\text{ TB}$ RAID 5 array, the rebuild process must read all $8\text{ TB}$ from every surviving drive to reconstruct the missing data. Modern consumer SATA drives have an **Unrecoverable Read Error (URE)** rate of $10^{-14}$ bits (1 sector error per $\approx 12.5\text{ TB}$ read). 
During an intensive multi-hour rebuild, encountering a single URE halts the rebuild and destroys the entire array! For drives $\ge 4\text{ TB}$, **RAID 6 (Dual Parity) or RAID 10 is mandatory**.
