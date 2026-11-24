#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raid_parity_engine.py - RAID 5 XOR Parity & Disaster Recovery Engine
Demonstrates byte-level XOR parity calculation and missing drive data recovery.
"""

def compute_raid5_parity(disk1_bytes: bytes, disk2_bytes: bytes, disk3_bytes: bytes) -> bytes:
    assert len(disk1_bytes) == len(disk2_bytes) == len(disk3_bytes), "Disks must have identical chunk sizes!"
    parity = bytearray(len(disk1_bytes))
    for i in range(len(disk1_bytes)):
        parity[i] = disk1_bytes[i] ^ disk2_bytes[i] ^ disk3_bytes[i]
    return bytes(parity)

def recover_failed_disk(surviving_disk_a: bytes, surviving_disk_b: bytes, parity_disk: bytes) -> bytes:
    # XOR self-inversion: Missing_Disk = Parity ^ Surviving_A ^ Surviving_B
    recovered = bytearray(len(parity_disk))
    for i in range(len(parity_disk)):
        recovered[i] = parity_disk[i] ^ surviving_disk_a[i] ^ surviving_disk_b[i]
    return bytes(recovered)

if __name__ == "__main__":
    d1 = b"Transaction_001;"
    d2 = b"Order_Batch_ABC;"
    d3 = b"Account_Balance;"
    
    parity = compute_raid5_parity(d1, d2, d3)
    print("=== RAID 5 XOR Parity Generation ===")
    print(f"Disk 1 Data: {d1.decode('latin1')}")
    print(f"Disk 2 Data: {d2.decode('latin1')}")
    print(f"Disk 3 Data: {d3.decode('latin1')}")
    print(f"Calculated Parity (Hex): {parity.hex()}")
    
    # Simulate Disk 2 Failure!
    print("\n[!] DISK 2 CATASTROPHIC FAILURE SIMULATED!")
    recovered_d2 = recover_failed_disk(d1, d3, parity)
    print(f"Recovered Disk 2 Data: {recovered_d2.decode('latin1')}")
    assert recovered_d2 == d2, "Disaster recovery failed!"
    print("[SUCCESS] Recovered data matches original lost data perfectly!")
