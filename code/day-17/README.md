# Day 17 Lab: RAID 5 XOR Parity & Disaster Recovery Engine

## For Beginners to Python

Welcome to Day 17! In this lab, you write a Python simulation of RAID 5 storage recovery using bitwise **XOR** (`^`).

### What Does This Script Do?
1. Takes 3 pieces of data representing 3 hard drives.
2. Uses the XOR math operation to compute a 4th "Parity" drive.
3. Simulates physically unplugging Drive 2!
4. Reconstructs every single byte of the lost drive by XORing the surviving drives with the parity drive.

### How to Run
```bash
python raid_parity_engine.py
```
