# Hands-On Lab: Day 13 - Ext4 Superblock & Block Group Calculator (`superblock_analyzer.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux ext4 filesystems, the entire disk partition is partitioned into uniform units called **Block Groups** (typically 128 MB each).
To protect against catastrophic disk damage, ext4 does not keep just one copy of the filesystem header (the **Superblock**); it writes redundant backup copies of the superblock across multiple block groups.

However, copying the superblock to every single block group on an 8 TB drive would waste enormous space. Therefore, ext4 uses the **Sparse Superblock** feature: backup superblocks are only stored in:
- Block Group 0 (Primary)
- Block Group 1
- Block Groups that are powers of 3, 5, and 7 ($3^1=3, 3^2=9, 3^3=27, 5^1=5, 5^2=25, 7^1=7, 7^2=49, \dots$).

In this lab, we build `superblock_analyzer.py` to calculate exact block group locations where backup superblocks reside on any given disk size.

---

## 2. Python Concepts for Beginners
1. **Sets (`set()`)**:
   - A collection of unique elements with no duplicates. We use a set to collect block group indices because powers of 3, 5, and 7 might otherwise produce duplicate numbers if not careful.
2. **The `while` Loop**:
   - Repeats a block of code as long as a condition is true:
     ```python
     val = base
     while val < total_groups:
         superblocks.add(val)
         val *= base # Compute next power
     ```
3. **Sorting Lists (`sorted()`)**:
   - Converts the set into an ordered, ascending list of numbers: `[0, 1, 3, 5, 7, 9, 25, 27, 49]`.

---

## 3. Step-by-Step Code Walkthrough

```python
def calculate_sparse_superblocks(total_block_groups: int) -> list:
    superblocks = {0, 1} # Primary and first backup
    powers = [3, 5, 7]

    for p in powers:
        val = p
        while val < total_block_groups:
            superblocks.add(val)
            val *= p # val becomes 3, 9, 27, 81...
            
    return sorted(list(superblocks))
```
- For a filesystem with 50 block groups, the loop computes:
  - Powers of 3: 3, 9, 27 (81 is $\ge 50$, so loop terminates).
  - Powers of 5: 5, 25 (125 is $\ge 50$, terminates).
  - Powers of 7: 7, 49 (343 is $\ge 50$, terminates).
- The final sorted list of backup groups returned is: `[0, 1, 3, 5, 7, 9, 25, 27, 49]`.

---

## 4. How to Run the Script

```bash
cd code/day-13
python superblock_analyzer.py
```

### Expected Output
```
Total Block Groups: 50
Superblock Backup Locations (Block Groups):
  [0, 1, 3, 5, 7, 9, 25, 27, 49]
Total Backup Superblocks: 9
```

---

## 5. Beginner Exercises to Try
1. Increase `total_block_groups` to `1000` (representing a large production partition) and observe how many superblocks are generated.
2. Add a function that calculates total disk size in gigabytes assuming each block group is 128 MiB (`total_block_groups * 128 / 1024`).
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

