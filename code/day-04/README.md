# Day 04 Lab: Understanding Unix Pipes (`|`) in Python

> **Welcome to Day 4!** Today we explore the most powerful idea in Unix philosophy: **The Pipe (`|`)**. In this lab, you will learn how programs pass data directly from one to another inside the computer's memory without saving intermediate temporary files to your hard drive.

---

## 🎯 What Does This Lab Do?
In Linux, when you write:
```bash
cat server.log | grep "ERROR" | wc -l
```
Three completely independent programs run simultaneously!
* `cat` reads the log file and sends bytes into **Pipe 1**.
* `grep` reads from **Pipe 1**, filters for `"ERROR"`, and sends matching lines into **Pipe 2**.
* `wc -l` reads from **Pipe 2** and counts the total number of errors.

`pipeline_demo.py` simulates this exact sequence in Python, demonstrating how data flows through a memory pipeline.

---

## 🚀 How to Run the Code
Run the script in your terminal:
```bash
python pipeline_demo.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. Multi-line Strings (`""" ... """`)
* When you want to store several lines of text in a Python variable without putting `\n` on every line, use triple quotes:
  ```python
  sample_logs = """Line 1
  Line 2
  Line 3"""
  ```

### 2. List Comprehensions (Python's Filter Magic)
* In Python, you can filter a list in a single clean line:
  ```python
  matching_lines = [line for line in sample_logs.strip().split("\n") if "ERROR" in line]
  ```
* **How to read this**:
  - `sample_logs.strip().split("\n")`: Splits the big text block into individual lines.
  - `if "ERROR" in line`: Checks if the word `"ERROR"` is present.
  - `[line for line in ...]`: Collects all matching lines into a new list!

### 3. Subprocesses & `subprocess.PIPE`
* Python has a built-in library called `subprocess` that allows Python to launch external programs (like `ls`, `grep`, `ping`) and capture their output.
* Setting `stdout=subprocess.PIPE` creates an in-memory buffer that captures the child program's output so your Python script can read it.

---

## 🔍 Code Walkthrough

```python
import subprocess
import sys

def main():
    sample_logs = """2026-11-23 08:00:01 INFO Server started successfully
2026-11-23 08:00:15 ERROR Database connection failed: timeout
2026-11-23 08:00:22 INFO Healthcheck OK
2026-11-23 08:01:05 WARNING Memory usage above 80%
2026-11-23 08:01:40 ERROR Database connection failed: refused
2026-11-23 08:02:11 INFO User 104 logged in
2026-11-23 08:03:00 ERROR Out of memory exception in worker 4
"""
    # 1. Simulate: grep 'ERROR'
    matching_lines = [line for line in sample_logs.strip().split("\n") if "ERROR" in line]
    
    # 2. Simulate: wc -l
    error_count = len(matching_lines)

    # 3. Print the results
    print("Filtered Lines (stdout of grep):")
    for l in matching_lines:
        print("  -> " + l)

    print(f"\nPipeline Final Result (stdout of wc -l): {error_count} errors found.")
```

---

## 📋 Expected Terminal Output
```text
==================================================
   DAY 4 LAB: DEMYSTIFYING THE UNIX PIPE (|)      
==================================================
Filtered Lines (stdout of grep):
  -> 2026-11-23 08:00:15 ERROR Database connection failed: timeout
  -> 2026-11-23 08:01:40 ERROR Database connection failed: refused
  -> 2026-11-23 08:03:00 ERROR Out of memory exception in worker 4

Pipeline Final Result (stdout of wc -l): 3 errors found.
==================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Modify `pipeline_demo.py` to filter for `"WARNING"` instead of `"ERROR"`. How many warnings are counted?
2. **Challenge 2**: Try running an actual pipeline directly in your shell:
   ```bash
   python ../day-02/my_cat.py pipeline_demo.py | python ../day-03/my_grep.py def
   ```
   Notice how `my_cat.py` streams directly into `my_grep.py`!
