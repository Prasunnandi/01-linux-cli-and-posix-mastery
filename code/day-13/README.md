# Day 13 Lab: Ext4 Superblock & Journaling Analyzer

## For Beginners to Python

Welcome to Day 13! In this lab, we learn how modern filesystems like ext4 protect against catastrophic disk failure.

### What Does This Script Do?
1. **Superblock Backup Calculation**: The primary superblock is the master map of a disk. If it gets damaged, the filesystem cannot open! ext4 saves backup copies in specific "sparse" block groups (powers of 3, 5, and 7). This script calculates exactly which groups hold backup superblocks.
2. **Journal Overhead Calculation**: It computes what percentage of disk space is dedicated to the write-ahead journal (`JBD2`), which ensures that if your power is cut, your disk never corrupts.

### How to Run
```bash
python superblock_analyzer.py
```
