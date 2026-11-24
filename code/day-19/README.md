# Day 19 Lab: Linux Sysfs & PCI Device Inspector

## For Beginners to Python

Welcome to Day 19! In this lab, we learn how the Linux kernel discovers and names hardware plugged into PCI and PCIe slots.

### Key Concepts
Every PCI device has an address like `0000:03:00.0` (Domain : Bus : Device . Function) and a 16-bit Vendor ID (e.g. `0x10de` is NVIDIA, `0x8086` is Intel).

### How to Run
```bash
python sysfs_hardware_scanner.py
```
