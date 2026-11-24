# Hands-On Lab: Day 11 - Virtual Memory & Page Activity Analyzer (`vmstat_parser.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux systems administration, `vmstat` (Virtual Memory Statistics) is one of the most fundamental tools for diagnosing performance bottlenecks. It reports instantaneous metrics about:
- **Processes in Run-Queue (`r`) and Uninterruptible Sleep (`b`)**.
- **Memory Allocation (`swpd`, `free`, `buff`, `cache`)**.
- **Paging / Swapping Activity (`si` swap-in, `so` swap-out)**.
- **CPU Time Slices (`us` user, `sy` system, `id` idle, `wa` I/O wait)**.

When a server becomes sluggish, engineers check `vmstat`. In this lab, we build `vmstat_parser.py`, a pure Python engine that parses raw text output from `vmstat`, extracts critical health metrics into structured Python dictionaries, and evaluates whether the system is experiencing **memory thrashing** (when `si` or `so` are greater than zero).

---

## 2. Python Concepts for Beginners
If you are new to Python, here are the key concepts used in this script:
1. **String Methods (`.strip()` and `.split()`)**:
   - `.strip()` removes leading and trailing whitespace/newlines from a string.
   - `.split()` splits a string by spaces into a list of individual words. For example: `"free buff cache".split()` becomes `['free', 'buff', 'cache']`.
2. **Lists (`[]`)**:
   - An ordered collection of items. In Python, list items are accessed by zero-based index: `headers[0]` is the first item.
3. **Dictionaries (`{}`)**:
   - Key-value stores. We use dictionaries to store named metrics, like `{"free_kb": 1048576, "swap_in": 0}`.
4. **Type Conversion (`int()`)**:
   - The `.split()` function returns strings (e.g. `"1024"`). We use `int("1024")` to convert the text into a real mathematical integer that we can add, compare, and check with `<` or `>`.
5. **Boolean Logic (`True` / `False`)**:
   - `stats["si"] > 0` returns `True` if data is currently being swapped from disk into RAM, indicating memory pressure.

---

## 3. Step-by-Step Code Walkthrough

Let's inspect the two functions inside `vmstat_parser.py`:

### Function 1: `parse_vmstat_line(header_line, data_line)`
```python
def parse_vmstat_line(header_line: str, data_line: str) -> dict:
```
- **Line 1-2**: `headers = header_line.strip().split()` extracts the column names into a list: `['r', 'b', 'swpd', 'free', 'buff', 'cache', 'si', 'so', 'bi', 'bo', 'in', 'cs', 'us', 'sy', 'id', 'wa', 'st']`.
- **Line 3-4**: `values = data_line.strip().split()` extracts the numeric values.
- **Line 5-8**: We verify that the number of values matches the number of headers using `len()`. If they don't match, we raise a `ValueError`.
- **Line 9-11**: We loop through each header and value pair using `zip(headers, values)` and build a dictionary where each numeric value is converted to an integer: `result[h] = int(v)`.

### Function 2: `is_memory_thrashing(metrics)`
```python
def is_memory_thrashing(metrics: dict) -> bool:
    return metrics.get("si", 0) > 0 or metrics.get("so", 0) > 0
```
- `.get("si", 0)` retrieves the value for swap-in. If the key doesn't exist, it safely defaults to `0`.
- If either swap-in (`si`) or swap-out (`so`) is greater than 0, it means the operating system is actively reading or writing memory pages to the swap partition on disk. This is a telltale sign of memory exhaustion!

---

## 4. How to Run the Script

Open your terminal or command prompt and navigate to this folder:
```bash
cd code/day-11
python vmstat_parser.py
```

### Expected Output
```
Parsed vmstat metrics:
  Run Queue (r): 2
  Blocked I/O (b): 0
  Free RAM (KB): 1048576
  Swap In (si): 0
  Swap Out (so): 0
  CPU Idle (%): 85
System Health Assessment:
  Memory Thrashing: False (Healthy RAM)
```

---

## 5. Beginner Exercises to Try
1. **Simulate Out-of-Memory Thrashing**: Change `data_line` in the `__main__` block to set `si` to `250` and `so` to `480`. Run the script again. Notice how `Memory Thrashing` flips to `True`!
2. **Calculate Free RAM in Gigabytes**: Add a print statement that computes: `free_gb = metrics['free'] / (1024 * 1024)` and print the result with two decimal places.
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

