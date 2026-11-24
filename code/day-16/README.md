# Hands-On Lab: Day 16 - LVM Extent Simulator (`lvm_allocator_sim.py`)

## 1. What Are We Building & Why Does It Matter?
Logical Volume Manager (LVM2) allows resizing disk storage on-the-fly without unmounting disks. It does this by breaking physical disks into small allocation blocks called **Physical Extents (PE)** (typically 4 MB each).
A **Logical Volume (LV)** is created by linking multiple extents together.

In this lab, we build `lvm_allocator_sim.py`, an Object-Oriented Python simulator that models Volume Groups, tracks free Physical Extents, and maps Logical Extents across multiple simulated drives.

---

## 2. Python Concepts for Beginners
1. **Classes and Object-Oriented Programming (`class`)**:
   - A class is a blueprint for creating objects.
   - `def __init__(self, ...)` is the constructor function that initializes the object when created.
   - `self` refers to the specific instance of the class.
2. **Lists of Objects**:
   - We store allocated extents in a list: `self.allocated_extents = []`.
3. **Methods**:
   - Functions defined inside a class that modify or read its state (e.g. `add_physical_volume`, `create_logical_volume`).

---

## 3. Step-by-Step Code Walkthrough

```python
class VolumeGroup:
    def __init__(self, name: str, pe_size_mb: int = 4):
        self.name = name
        self.pe_size_mb = pe_size_mb
        self.total_pe = 0
        self.allocated_pe = 0

    def add_physical_volume(self, pv_name: str, size_mb: int):
        num_pe = size_mb // self.pe_size_mb
        self.total_pe += num_pe
```
- `//` is integer floor division: `1000 // 4` gives `250` Physical Extents.
- When an LV is requested: `create_logical_volume(lv_name, size_mb)`:
  - We calculate needed extents: `needed_pe = size_mb // 4`.
  - If `self.free_pe >= needed_pe`, we allocate the extents and track them!

---

## 4. How to Run the Script

```bash
cd code/day-16
python lvm_allocator_sim.py
```

### Expected Output
```
Created Volume Group 'vg_data' (PE Size: 4 MB)
Added PV /dev/nvme0n1 (1000 MB -> 250 PEs)
Added PV /dev/nvme1n1 (1000 MB -> 250 PEs)
Total Pool Capacity: 500 PEs (2000 MB)

Allocated LV 'lv_database' (1200 MB -> 300 PEs)
Remaining Free Extents in Pool: 200 PEs (800 MB)
```

---

## 5. Beginner Exercises to Try
1. Try allocating an LV that exceeds available storage (e.g. 3,000 MB). Verify that the code prevents the allocation and prints an error message.
2. Add a `remove_logical_volume(lv_name)` method that frees allocated extents back to the pool.
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

