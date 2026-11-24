#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iostat_calculator.py - Disk I/O Performance & Utilization Engine
Simulates /proc/diskstats delta rate calculation (r/s, w/s, await, %util).
"""

def calculate_disk_metrics(t1_stats: dict, t2_stats: dict, delta_sec: float) -> dict:
    d_reads = t2_stats["reads"] - t1_stats["reads"]
    d_writes = t2_stats["writes"] - t1_stats["writes"]
    d_r_sectors = t2_stats["read_sectors"] - t1_stats["read_sectors"]
    d_w_sectors = t2_stats["write_sectors"] - t1_stats["write_sectors"]
    d_r_time = t2_stats["read_time_ms"] - t1_stats["read_time_ms"]
    d_w_time = t2_stats["write_time_ms"] - t1_stats["write_time_ms"]
    d_io_time = t2_stats["io_time_ms"] - t1_stats["io_time_ms"]
    
    r_per_sec = d_reads / delta_sec
    w_per_sec = d_writes / delta_sec
    r_kb_per_sec = (d_r_sectors * 512 / 1024) / delta_sec
    w_kb_per_sec = (d_w_sectors * 512 / 1024) / delta_sec
    
    r_await = (d_r_time / d_reads) if d_reads > 0 else 0.0
    w_await = (d_w_time / d_writes) if d_writes > 0 else 0.0
    util_pct = min(100.0, (d_io_time / (delta_sec * 1000.0)) * 100.0)
    
    return {
        "reads_per_sec": round(r_per_sec, 2),
        "writes_per_sec": round(w_per_sec, 2),
        "read_kb_per_sec": round(r_kb_per_sec, 2),
        "write_kb_per_sec": round(w_kb_per_sec, 2),
        "r_await_ms": round(r_await, 2),
        "w_await_ms": round(w_await, 2),
        "utilization_pct": round(util_pct, 2)
    }

if __name__ == "__main__":
    t1 = {"reads": 1000, "writes": 5000, "read_sectors": 20000, "write_sectors": 100000, "read_time_ms": 2000, "write_time_ms": 15000, "io_time_ms": 800}
    t2 = {"reads": 1150, "writes": 5800, "read_sectors": 24500, "write_sectors": 132000, "read_time_ms": 2225, "write_time_ms": 18600, "io_time_ms": 1740}
    
    metrics = calculate_disk_metrics(t1, t2, delta_sec=1.0)
    print("=== Linux Disk I/O Performance Metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
