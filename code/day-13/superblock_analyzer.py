#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
superblock_analyzer.py - Ext4 Superblock & Block Group Calculator
Calculates sparse superblock positions and journal commit space overhead.
"""

def calculate_sparse_superblocks(total_block_groups: int) -> list:
    superblocks = [0, 1]
    powers = [3, 5, 7]
    for p in powers:
        val = p
        while val < total_block_groups:
            if val not in superblocks:
                superblocks.append(val)
            val *= p
    superblocks.sort()
    return superblocks

def calculate_journal_overhead(block_count: int, block_size: int, journal_size_mb: int) -> dict:
    total_capacity_bytes = block_count * block_size
    journal_bytes = journal_size_mb * 1024 * 1024
    overhead_pct = (journal_bytes / total_capacity_bytes) * 100
    
    return {
        "total_capacity_gb": round(total_capacity_bytes / (1024**3), 2),
        "journal_size_mb": journal_size_mb,
        "journal_overhead_pct": round(overhead_pct, 4)
    }

if __name__ == "__main__":
    b_groups = 64
    sb_locations = calculate_sparse_superblocks(b_groups)
    print("=== Ext4 Superblock & Journaling Analysis ===")
    print(f"Total Block Groups: {b_groups}")
    print(f"Backup Superblock Groups: {sb_locations}")
    
    overhead = calculate_journal_overhead(block_count=26214400, block_size=4096, journal_size_mb=128)
    for k, v in overhead.items():
        print(f"  {k}: {v}")
