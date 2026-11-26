# Hands-On Lab: Day 38 - Rsync Rolling Checksum & Delta Engine (`rsync_rolling_checksum.py`)

## 1. What Are We Building & Why Does It Matter?
If you have a 10 GB file on a remote server and modify 50 bytes in the middle of it, standard `scp` retransmits the entire 10 GB over the network.
In 1996, Andrew Tridgell invented the **rsync algorithm**:
- The receiver splits its local file into chunks (e.g. 8-byte blocks) and computes two hashes per block: a fast **Adler-32 rolling checksum** and a strong **MD5 hash**.
- The receiver sends this tiny table of signatures to the sender.
- The sender slides a rolling window byte-by-byte across its new file.
- If a block matches, the sender sends only the **block index number (4 bytes)**!
- If bytes do not match, the sender transmits only the **raw modified byte deltas**.
- The receiver reconstructs the identical new file without transferring unchanged blocks!

In this lab, we build a complete working implementation of the rsync delta-transfer engine.

---

## 2. Python Concepts for Beginners
1. **Union Type Hints (`Union[int, bytes]`)**:
   - In Python, `deltas` contains both integers (representing matched block indices) and raw bytes (representing newly inserted text). `Union[int, bytes]` documents this flexibility.
2. **`isinstance(item, int)`**:
   - Used to inspect the type of an item dynamically during file reconstruction.
3. **The Modulo Operator (`%`) in Rolling Math**:
   - Keeps integer sums wrapped inside 16-bit boundaries ($2^{16} = 65,536$).

---

## 3. Step-by-Step Code Walkthrough

```python
def generate_signatures(self, basis_file: bytes) -> Dict[int, BlockSignature]:
    for i in range(0, len(basis_file), self.block_size):
        chunk = basis_file[i:i + self.block_size]
        adler = (b << 16) | a
        md5 = hashlib.md5(chunk).hexdigest()
        signatures[adler] = BlockSignature(index=i // self.block_size, ...)
```
- Splits the old file into 8-byte blocks and indexes them by their Adler-32 hash.

```python
def reconstruct(self, basis_file: bytes, deltas: List[Union[int, bytes]]) -> bytes:
    for item in deltas:
        if isinstance(item, int):
            start = item * self.block_size
            reconstructed.extend(basis_file[start:start + self.block_size])
        else:
            reconstructed.extend(item)
```
- The receiver reads the token stream: for integers, it copies blocks from its local disk; for byte chunks, it appends the newly inserted data.

---

## 4. How to Run the Script

```bash
cd code/day-38
python rsync_rolling_checksum.py
```

### Expected Output
```
====================================================
DAY 38: RSYNC ROLLING CHECKSUM & DELTA ENGINE
====================================================
Basis File Size : 57 bytes
New File Size   : 60 bytes

Receiver generated 8 block signatures (8-byte chunks).
Deltas to transmit across network: 5 tokens
Total Wire Bytes Transferred     : 29 bytes (Saved 31 bytes!)
-------------------------------------------------------
Original Text    : DATABASE_RECORD_001_MODIFIED_RECORD_002_VALID_RECORD_003_END
Reconstructed    : DATABASE_RECORD_001_MODIFIED_RECORD_002_VALID_RECORD_003_END
[VERIFIED] Rsync delta-transfer algorithm reconstructed file with 100% fidelity!
```

---

## 5. Common Python Errors & Troubleshooting
1. **Hash Collisions without Strong Hash**:
   - A 32-bit checksum alone will produce false positive matches on large files. Always verify candidate matches against a 128-bit MD5 or SHA256 hash!
2. **Off-by-One in Trailing Slices**:
   - If the file length is not a multiple of `block_size`, ensure trailing bytes are flushed into the deltas list.

---

## 6. Beginner Exercises & Challenges
1. **Benchmark Compression Ratio**: Test the engine with a 1 KB file where 1 word is changed. Calculate the percentage of bandwidth saved.
2. **Variable Block Sizes**: Test running the engine with `block_size=16` vs `block_size=4`. Observe how block size affects signature table size vs delta granularity.
