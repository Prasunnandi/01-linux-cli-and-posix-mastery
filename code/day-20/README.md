# Day 20 Lab: Kernel Module Dependency Resolver

## For Beginners to Python

Welcome to Day 20! In this lab, we write a dependency solver just like `modprobe`.

### What Does This Script Do?
If module A needs module B, and module B needs module C, you cannot load module A first (the computer will report missing symbols!). This script uses a **Depth-First Search (DFS) Topological Sort** to calculate the exact order to safely load kernel drivers.

### How to Run
```bash
python module_dependency_resolver.py
```
