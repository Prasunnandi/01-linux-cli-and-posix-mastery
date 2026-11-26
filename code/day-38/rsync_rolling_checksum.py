#!/usr/bin/env python3
"""
Day 38 Lab: Rsync Delta-Transfer & Rolling Checksum Engine
Implements Andrew Tridgell's rsync algorithm:
- Splitting target file into blocks
- Computing fast O(1) Adler-32 rolling checksums and MD5 signatures
- Sliding a window byte-by-byte to detect matching blocks and emit byte deltas
"""

import hashlib
from dataclasses import dataclass
from typing import List, Dict, Tuple, Union


MOD_ADLER = 65536


def adler32_rolling(block: bytes) -> Tuple[int, int]:
    """Computes initial (a, b) components of Adler-32 rolling checksum."""
    a = 0
    b = 0
    n = len(block)
    for i, byte in enumerate(block):
        a = (a + byte) % MOD_ADLER
        b = (b + (n - i) * byte) % MOD_ADLER
    return a, b


def roll_checksum(prev_a: int, prev_b: int, block_len: int, old_byte: int, new_byte: int) -> Tuple[int, int]:
    """O(1) rolling update of Adler-32 checksum when window slides 1 byte forward."""
    new_a = (prev_a - old_byte + new_byte) % MOD_ADLER
    new_b = (prev_b - (block_len * old_byte) + new_a) % MOD_ADLER
    return new_a, new_b


@dataclass
class BlockSignature:
    index: int
    adler_hash: int
    md5_hash: str


class RsyncDeltaEngine:
    def __init__(self, block_size: int = 8):
        self.block_size = block_size

    def generate_signatures(self, basis_file: bytes) -> Dict[int, BlockSignature]:
        """Receiver splits basis file into blocks and computes signatures."""
        signatures = {}
        for i in range(0, len(basis_file), self.block_size):
            chunk = basis_file[i:i + self.block_size]
            a, b = adler32_rolling(chunk)
            adler = (b << 16) | a
            md5 = hashlib.md5(chunk).hexdigest()
            signatures[adler] = BlockSignature(index=i // self.block_size, adler_hash=adler, md5_hash=md5)
        return signatures

    def compute_deltas(self, new_file: bytes, signatures: Dict[int, BlockSignature]) -> List[Union[int, bytes]]:
        """
        Sender scans new file:
        - If rolling checksum + MD5 matches a basis block, emits block index integer!
        - If no match, accumulates literal un-matched byte deltas.
        """
        deltas = []
        unmatched = bytearray()
        i = 0
        n = len(new_file)

        while i <= n - self.block_size:
            chunk = new_file[i:i + self.block_size]
            a, b = adler32_rolling(chunk)
            adler = (b << 16) | a

            if adler in signatures:
                # Potential match: verify strong MD5
                cand_md5 = hashlib.md5(chunk).hexdigest()
                if cand_md5 == signatures[adler].md5_hash:
                    if unmatched:
                        deltas.append(bytes(unmatched))
                        unmatched.clear()
                    deltas.append(signatures[adler].index)  # Emit matched block index!
                    i += self.block_size
                    continue

            unmatched.append(new_file[i])
            i += 1

        if i < n:
            unmatched.extend(new_file[i:])
        if unmatched:
            deltas.append(bytes(unmatched))

        return deltas

    def reconstruct(self, basis_file: bytes, deltas: List[Union[int, bytes]]) -> bytes:
        """Receiver reconstructs new file using local basis blocks and received deltas."""
        reconstructed = bytearray()
        for item in deltas:
            if isinstance(item, int):
                # Matched block: extract directly from local basis file!
                start = item * self.block_size
                reconstructed.extend(basis_file[start:start + self.block_size])
            elif isinstance(item, bytes):
                # Literal byte delta: append inserted data
                reconstructed.extend(item)
        return bytes(reconstructed)


def main():
    print("====================================================")
    print("DAY 38: RSYNC ROLLING CHECKSUM & DELTA ENGINE")
    print("====================================================")

    # Basis file on Receiver (Old database dump)
    basis = b"DATABASE_RECORD_001_VALID_RECORD_002_VALID_RECORD_003_END"
    # New file on Sender (Inserted "MODIFIED_" in the middle!)
    new_data = b"DATABASE_RECORD_001_MODIFIED_RECORD_002_VALID_RECORD_003_END"

    engine = RsyncDeltaEngine(block_size=8)

    print(f"Basis File Size : {len(basis)} bytes")
    print(f"New File Size   : {len(new_data)} bytes\n")

    # Step 1: Receiver generates signatures
    sigs = engine.generate_signatures(basis)
    print(f"Receiver generated {len(sigs)} block signatures (8-byte chunks).")

    # Step 2: Sender computes deltas
    deltas = engine.compute_deltas(new_data, sigs)
    wire_bytes = sum(len(d) if isinstance(d, bytes) else 4 for d in deltas)
    print(f"Deltas to transmit across network: {len(deltas)} tokens")
    print(f"Total Wire Bytes Transferred     : {wire_bytes} bytes (Saved {len(new_data) - wire_bytes} bytes!)")

    # Step 3: Receiver reconstructs file
    rebuilt = engine.reconstruct(basis, deltas)
    assert rebuilt == new_data, "Reconstructed file must exactly match new file!"

    print("-" * 55)
    print(f"Original Text    : {new_data.decode('utf-8')}")
    print(f"Reconstructed    : {rebuilt.decode('utf-8')}")
    print("[VERIFIED] Rsync delta-transfer algorithm reconstructed file with 100% fidelity!")


if __name__ == "__main__":
    main()
