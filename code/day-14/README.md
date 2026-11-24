# Day 14 Lab: Disk I/O Performance & Utilization Engine

## For Beginners to Python

Welcome to Day 14! In this lab, we build an I/O performance calculator similar to the industry-standard `iostat` tool.

### What Does This Script Do?
It takes two snapshots of disk counters from `/proc/diskstats` taken 1 second apart and calculates:
1. `reads_per_sec` & `writes_per_sec`: How many individual I/O operations occurred per second.
2. `r_await_ms`: Average time a read request waited in line and executed on the drive.
3. `utilization_pct`: How busy the drive was during that 1-second interval.

### How to Run
```bash
python iostat_calculator.py
```
