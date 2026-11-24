#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
partition_parser.py - Partition Table Parser (MBR vs GPT Capacity Analyzer)
Demonstrates 32-bit MBR limit math vs 64-bit GPT capacity calculations.
"""

def analyze_partition_limits(sector_size_bytes: int = 512) -> dict:
    # MBR uses 32-bit sector count
    max_mbr_sectors = 2**32
    max_mbr_bytes = max_mbr_sectors * sector_size_bytes
    max_mbr_tib = max_mbr_bytes / (1024**4)
    max_mbr_tb = max_mbr_bytes / (10**12)
    
    # GPT uses 64-bit sector count
    max_gpt_sectors = 2**64
    max_gpt_bytes = max_gpt_sectors * sector_size_bytes
    max_gpt_zb = max_gpt_bytes / (10**21)
    
    return {
        "sector_size_bytes": sector_size_bytes,
        "max_mbr_capacity_tib": round(max_mbr_tib, 2),
        "max_mbr_capacity_tb": round(max_mbr_tb, 3),
        "max_gpt_capacity_zettabytes": round(max_gpt_zb, 2),
        "can_mbr_support_16tb_drive": (16 * (10**12)) <= max_mbr_bytes,
        "can_gpt_support_16tb_drive": True
    }

if __name__ == "__main__":
    results = analyze_partition_limits()
    print("=== MBR vs GPT Storage Limits Analysis ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
