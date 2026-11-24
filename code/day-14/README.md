# Hands-On Lab: Day 14 - Disk I/O Performance & Utilization Engine (`iostat_calculator.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux systems performance analysis, `iostat` reads from the kernel file `/proc/diskstats`.
Every time a disk reads or writes a sector, the kernel increments cumulative counters:
- Total reads completed.
- Total sectors written.
- Total milliseconds spent doing I/O.

To calculate current disk speed (reads per second, writes per second, and percent disk utilization), monitoring tools take **two snapshots** of `/proc/diskstats` separated by a time delta $\Delta t$ (e.g. 1.0 second) and compute the rate of change.

In this lab, we build `iostat_calculator.py`, which simulates taking two time snapshots and calculates real-world disk performance metrics.

---

## 2. Python Concepts for Beginners
1. **Dictionaries as Structured Records**:
   - We store time snapshot data in dictionaries:
     ```python
     t1 = {"reads": 1000, "writes": 5000, "io_ms": 200}
     ```
2. **Delta Calculations**:
   - The symbol $\Delta$ (delta) means "change over time".
   - $	ext{Reads per second} = rac{	ext{Reads at } t_2 - 	ext{Reads at } t_1}{\Delta t}$.
3. **Floating Point Math (`float`)**:
   - When calculating rates, results are numbers with decimal points: `d_reads / delta_sec`.

---

## 3. Step-by-Step Code Walkthrough

```python
def calculate_disk_metrics(t1_stats: dict, t2_stats: dict, delta_sec: float) -> dict:
    d_reads = t2_stats["reads"] - t1_stats["reads"]
    d_writes = t2_stats["writes"] - t1_stats["writes"]
    d_io_ms = t2_stats["io_ms"] - t1_stats["io_ms"]

    rps = d_reads / delta_sec
    wps = d_writes / delta_sec
    # %util = (time spent doing I/O in ms / elapsed time in ms) * 100
    util_percent = (d_io_ms / (delta_sec * 1000.0)) * 100.0
```
- If the disk spent 800 milliseconds active during a 1.0-second interval, its `%util` is $rac{800}{1000} 	imes 100 = 80.0\%$.
- When `%util` reaches 100%, the storage device is completely saturated and cannot handle additional concurrent I/O operations without queueing!

---

## 4. How to Run the Script

```bash
cd code/day-14
python iostat_calculator.py
```

### Expected Output
```
Disk I/O Metrics (over 1.00s sample):
  Reads per second (r/s)  : 150.00
  Writes per second (w/s) : 320.00
  Total IOPS              : 470.00
  Disk Utilization (%util): 45.00%
Storage Health: Operational (Headroom Available)
```

---

## 5. Beginner Exercises to Try
1. Change `t2_stats["io_ms"]` to simulate 1000ms of I/O in 1.0 second. Verify that `%util` reaches `100.0%`.
2. Add a warning alert: if `util_percent > 85.0`, print `"WARNING: Disk saturation imminent!"`.
---

## 6. Common Python Errors & How to Fix Them
As a beginner to Python, you may run into these common errors while experimenting:

1. **`ValueError: invalid literal for int() with base 10`**:
   - **Why it happens**: You called `int("hello")` or tried to convert an empty string `""` into a number.
   - **How to fix**: Always inspect what string you are passing into `int()`. Use `.strip()` to remove stray newline characters or check `if s.isdigit():` before converting.
2. **`KeyError: 'some_key'`**:
   - **Why it happens**: You tried to access a dictionary key that does not exist (`metrics["non_existent"]`).
   - **How to fix**: Use the `.get()` method instead: `metrics.get("some_key", default_value)`. This returns `default_value` safely without crashing your program.
3. **`IndexError: list index out of range`**:
   - **Why it happens**: You tried to access `items[5]` when the list only contains 3 items.
   - **How to fix**: Always verify the length of your list with `len(items)` before indexing into it.
4. **`FileNotFoundError`**:
   - **Why it happens**: You attempted to open a file that does not exist in the current working directory.
   - **How to fix**: Print `os.getcwd()` to check where your script is currently looking, or use absolute paths.

---

## 7. Line-by-Line Code Reference

Here is a summary of every standard library function and built-in used in this lab:
- `open(filename, mode)`: Opens a file stream for reading (`'r'`) or writing (`'w'`).
- `len(collection)`: Returns the number of items in a list, string, or dictionary.
- `print(...)`: Outputs text or variable values to the standard output stream (terminal).
- `assert condition, "error message"`: Sanity-checks that internal logic holds true; crashes with message if false.
- `if __name__ == '__main__':`: Standard Python boilerplate that executes test code when run directly from the command line, but does not run when imported as a module by other scripts.

