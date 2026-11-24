# Day 11 Lab: Virtual Memory & Page Activity Analyzer

## For Beginners to Python

Welcome to Day 11! This lab teaches you how to inspect Linux memory statistics (`vmstat`) using Python.

### What Does This Script Do?
1. It simulates reading a row of output from the Linux `vmstat` command.
2. It breaks the raw text line into distinct columns (like `free` memory, `swap-in`, and `run queue`).
3. It performs health calculations to determine if the computer is suffering from **Memory Thrashing** (when the system runs out of RAM and freezes because it is reading and writing to disk swap non-stop).

### Code Breakdown
- `parse_vmstat_line()`: Takes two strings—the column names and the numbers—and uses Python's `.split()` method to break them apart into a dictionary (key-value pairs).
- `evaluate_memory_pressure()`: Reads the numbers and checks logical conditions (`if si > 100 and wa > 20`).
- `if __name__ == "__main__":`: This is standard Python syntax meaning "run this code if the file is executed directly."

### How to Run
```bash
python vmstat_parser.py
```

### Expected Output
```
=== Linux Virtual Memory (vmstat) Analysis ===
  status: CRITICAL: ACTIVE MEMORY THRASHING DETECTED
  runnable_procs: 5
  blocked_procs: 3
  swap_in_kb_s: 450
  swap_out_kb_s: 820
  io_wait_pct: 50
```
