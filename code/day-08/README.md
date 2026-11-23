# Day 08 Lab: Inspecting Linux Virtual Filesystem (`/proc`) in Python

> **Welcome to Day 8!** Today we explore the most fascinating directory in Linux: `/proc`. Files inside `/proc` do not exist on any physical disk or SSD! They are live windows directly into the Linux kernel's brain. In this lab, you will learn how to parse system memory health and calculate server load averages using Python.

---

## 🎯 What Does This Lab Do?
`proc_inspector.py` demonstrates:
1. **The True Usable Memory Equation**: Why `MemFree` is misleading, and how to compute `MemAvailable` by adding back evictable page cache:
   $$\text{Usable Memory} = \text{MemFree} + \text{Cached} + \text{Buffers}$$
2. **Exponentially Weighted Moving Average (EWMA)**: Simulating the mathematical decay formula the Linux kernel uses to update the 1-minute, 5-minute, and 15-minute load averages:
   $$L_t = L_{t-1} \cdot e^{-\Delta t / \tau} + n \cdot (1 - e^{-\Delta t / \tau})$$
3. **Cross-Platform Resilience**: If running on a Linux machine, it reads live kernel data; if running on Windows or macOS, it uses realistic synthetic kernel dumps so you can study Linux internals on any computer!

---

## 🚀 How to Run the Code
Run the script in your terminal:
```bash
python proc_inspector.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. Python Dictionaries (`dict`)
* A dictionary stores data in **key: value** pairs:
  ```python
  metrics = {"MemTotal": 32645120, "MemFree": 4123540}
  ```
* Looking up a key takes $O(1)$ constant time: `metrics["MemTotal"]` instantly returns `32645120`.
* `metrics.get("MemAvailable", default_value)` safely looks up a key without crashing if the key is missing.

### 2. What is `@staticmethod`?
* In Python object-oriented programming, classes group related functions together.
* An `@staticmethod` is simply a normal function placed inside a class namespace for neat organization. It does not require `self`.

### 3. Exponential Math with `math.exp()`
* `math.exp(x)` calculates the mathematical constant $e^x$.
* We use this to compute the exponential smoothing decay factor:
  ```python
  decay = math.exp(-delta_t_sec / tau_sec)
  ```

### 4. Safe Cross-Platform Detection with `os.path.exists()`
* `os.path.exists("/proc/meminfo")` returns `True` only if running on a real Linux operating system.
* If `False` (such as running on a Windows laptop), the script falls back to sample kernel telemetry, ensuring zero crashes!

---

## 🔍 Code Walkthrough

```python
import math

class ProcMemInfoParser:
    @staticmethod
    def parse(meminfo_content: str):
        metrics = {}
        for line in meminfo_content.strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                metrics[key.strip()] = int(val.strip().split()[0])
        return metrics

    @staticmethod
    def calculate_memory_health(metrics):
        total = metrics.get("MemTotal", 0)
        free = metrics.get("MemFree", 0)
        cached = metrics.get("Cached", 0)
        buffers = metrics.get("Buffers", 0)
        
        # Real usable memory includes cache and buffers that Linux can evict on demand
        available = metrics.get("MemAvailable", free + cached + buffers)
        used = total - available
        
        return {
            "Total_MB": total / 1024,
            "Free_MB": free / 1024,
            "Available_MB": available / 1024,
            "Utilization_Pct": (used / total) * 100
        }
```

---

## 📋 Expected Terminal Output
```text
============================================================
DAY 08 LAB: KERNEL PROCFS TELEMETRY & MEMORY CALCULATOR
============================================================

[1] Parsing /proc/meminfo...
    Total RAM       : 31880.00 MB
    Raw MemFree     : 4026.89 MB
    Page Cache      : 19943.92 MB
    True Available  : 24307.84 MB
    True Utilization: 23.75%
    [PASS] Memory equation verified: Usable RAM properly accounts for evictable cache.

[2] Parsing /proc/loadavg and testing EWMA math...
    1-min Load  : 0.72
    5-min Load  : 1.45
    15-min Load : 2.1
    Threads     : 3 running / 450 total
    Projected 1m load after 5s burst of 10 threads: 1.4620
    [PASS] EWMA mathematical decay model verified.
============================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Look at the output: Why is `True Available` (24,307 MB) so much higher than `Raw MemFree` (4,026 MB)? (Answer: Because Linux aggressively uses spare RAM for disk caching to make apps fast!).
2. **Challenge 2**: In `proc_inspector.py`, simulate what happens to the load average if 50 tasks suddenly become active for 5 seconds.
