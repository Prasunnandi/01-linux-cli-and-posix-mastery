# Hands-On Python Labs Guide: Linux CLI & POSIX Mastery

> **Welcome to the Code Suite!** This directory contains self-contained Python implementations and simulations for the first 10 days of your curriculum.
> Every lab has been designed from the ground up to be **freshman and beginner friendly**, with zero external package dependencies (pure Python Standard Library).

---

## 🚀 Quick Start: How to Run Any Lab

You only need standard Python 3 (Python 3.8 or higher) installed on your system.

To run any day's lab, open your terminal and navigate to the code folder:

```bash
# Day 1: Standard Streams & Redirection
python day-01/streams_demo.py

# Day 2: Custom Cat & Word Count
python day-02/my_cat.py day-02/my_cat.py
python day-02/my_wc.py day-02/my_cat.py

# Day 3: Custom Grep Search
python day-03/my_grep.py -n "import" day-03/my_grep.py

# Day 4: Unix Subprocess Pipeline
python day-04/pipeline_demo.py

# Day 5: Linux Permissions & Octal Calculator
python day-05/permission_calculator.py

# Day 6: Log Wrangling & Aggregation (Awk/Sed)
python day-06/log_wrangler.py

# Day 7: External K-Way Merge Sort & Dedup
python day-07/external_merge_sort_sim.py

# Day 8: Linux procfs Memory & Load Telemetry
python day-08/proc_inspector.py

# Day 9: Process Lifecycle, Zombie & Orphan Simulation
python day-09/process_tree_tracer.py

# Day 10: POSIX Signals & Graceful Shutdown Daemon
python day-10/graceful_shutdown_daemon.py
```

---

## 📁 Directory Structure & Lab Index

Each day's folder includes its own dedicated **`README.md`** explaining the Python concepts, line-by-line code logic, and beginner practice exercises:

| Directory | Lab Script | Concepts Taught for Beginners | Beginner Guide |
| :--- | :--- | :--- | :---: |
| **`day-01/`** | `streams_demo.py` | `sys.stdout.write`, `sys.stderr.write`, `sys.stdin`, buffers | [day-01/README.md](day-01/README.md) |
| **`day-02/`** | `my_cat.py`, `my_wc.py` | `sys.argv`, `with open(...)`, streaming iterators, string splitting | [day-02/README.md](day-02/README.md) |
| **`day-03/`** | `my_grep.py` | `re` regular expressions, command-line flags, `enumerate()` | [day-03/README.md](day-03/README.md) |
| **`day-04/`** | `pipeline_demo.py` | List comprehensions, multi-line strings, memory piping | [day-04/README.md](day-04/README.md) |
| **`day-05/`** | `permission_calculator.py` | Bitwise AND (`&`), octal math, string slicing, validation | [day-05/README.md](day-05/README.md) |
| **`day-06/`** | `log_wrangler.py` | Text columnar parsing, type conversions, table formatting | [day-06/README.md](day-06/README.md) |
| **`day-07/`** | `external_merge_sort_sim.py`| Min-Heaps (`heapq`), generator functions (`yield`), assertions | [day-07/README.md](day-07/README.md) |
| **`day-08/`** | `proc_inspector.py` | Dictionaries, `@staticmethod`, exponential math (`math.exp`) | [day-08/README.md](day-08/README.md) |
| **`day-09/`** | `process_tree_tracer.py`| `enum.Enum`, Object-Oriented classes, `__repr__`, dictionaries | [day-09/README.md](day-09/README.md) |
| **`day-10/`** | `graceful_shutdown_daemon.py`| `signal.signal`, asynchronous handlers, FIFO queues (`.pop(0)`) | [day-10/README.md](day-10/README.md) |

---

## 💡 Python Beginner Cheatsheet

If you get stuck, remember these core Python rules:
1. **Indentation Matters**: In Python, code blocks inside `if`, `for`, `def`, or `class` must be indented by exactly 4 spaces.
2. **Zero Dependencies**: None of these labs require running `pip install`. Everything runs directly with Python's built-in standard library!
3. **Automated Verification**: Every script contains automated `assert` statements at the bottom. When you run a script and it displays `ALL VERIFICATIONS PASSED SUCCESSFULLY!`, you can be 100% confident your code executed with mathematical correctness.
