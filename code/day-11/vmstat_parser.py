#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vmstat_parser.py - Virtual Memory & Page Activity Analyzer
Parses and calculates memory pressure and swap statistics.
"""

def parse_vmstat_line(header_line: str, data_line: str) -> dict:
    headers = header_line.strip().split()
    values = data_line.strip().split()
    result = {}
    for h, v in zip(headers, values):
        try:
            result[h] = int(v)
        except ValueError:
            result[h] = v
    return result

def evaluate_memory_pressure(metrics: dict) -> dict:
    # r: runnable processes, b: blocked (I/O wait), si: swap-in, so: swap-out, wa: io-wait
    r = metrics.get('r', 0)
    b = metrics.get('b', 0)
    si = metrics.get('si', 0)
    so = metrics.get('so', 0)
    wa = metrics.get('wa', 0)
    
    is_thrashing = (si > 100 or so > 100) and wa > 20
    is_cpu_saturated = r > 4
    is_io_blocked = b > 2
    
    status = "HEALTHY"
    if is_thrashing:
        status = "CRITICAL: ACTIVE MEMORY THRASHING DETECTED"
    elif is_io_blocked:
        status = "WARNING: HIGH I/O WAIT QUEUE"
    elif is_cpu_saturated:
        status = "WARNING: HIGH RUN QUEUE CONCURRENCY"
        
    return {
        "status": status,
        "runnable_procs": r,
        "blocked_procs": b,
        "swap_in_kb_s": si,
        "swap_out_kb_s": so,
        "io_wait_pct": wa
    }

if __name__ == "__main__":
    header = "r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st"
    sample = "5  3  65536 215480  84210 1845120  450  820   120   450  150  420 15 25 10 50  0"
    
    parsed = parse_vmstat_line(header, sample)
    eval_res = evaluate_memory_pressure(parsed)
    print("=== Linux Virtual Memory (vmstat) Analysis ===")
    for k, v in eval_res.items():
        print(f"  {k}: {v}")
