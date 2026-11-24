# Day 16 Lab: LVM Extent Simulator

## For Beginners to Python

Welcome to Day 16! In this lab, we simulate how Linux Logical Volume Management (LVM) pools multiple hard drives together into a single flexible volume group.

### Key Concepts
- `Physical Extents (PE)`: Uniform 4MB chunks of disk space.
- `Volume Group (VG)`: The unified pool holding all extents.
- `Logical Volume (LV)`: A virtual partition carved out of the pool.

### How to Run
```bash
python lvm_allocator_sim.py
```
