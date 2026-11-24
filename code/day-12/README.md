# Hands-On Lab: Day 12 - Inode & Link Inspector (`inode_inspector.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux, a file's name and its underlying data are separate concepts.
- The **Inode** is the data structure that holds the file's metadata (size, permissions, owner, timestamps, and pointers to disk blocks).
- A **Hard Link** is simply an additional directory entry pointing to the exact same inode number.
- A **Symbolic (Soft) Link** is a special file whose content is the text pathname of another file.

In this lab, we build `inode_inspector.py`, which uses Python's built-in `os` module to create files, generate hard and soft links, inspect inode numbers using `os.stat()` and `os.lstat()`, and verify what happens when the original file is deleted.

---

## 2. Python Concepts for Beginners
1. **The `os` Module**:
   - Python's standard bridge to the operating system. It provides POSIX system calls like `os.link()`, `os.symlink()`, `os.unlink()`, and `os.stat()`.
2. **`os.stat()` vs `os.lstat()`**:
   - `os.stat(path)` retrieves file metadata. If `path` is a symbolic link, it follows (dereferences) the link to inspect the target!
   - `os.lstat(path)` does **not** follow symbolic links; it inspects the link itself.
3. **Temporary Directories (`tempfile.TemporaryDirectory()`)**:
   - A safe Python context manager that creates a scratch directory for testing and automatically cleans it up when done.
4. **The `with` Statement (Context Managers)**:
   - Ensures that files and resources are automatically closed when the block finishes:
     ```python
     with open("file.txt", "w") as f:
         f.write("data")
     ```

---

## 3. Step-by-Step Code Walkthrough

```python
import os
import tempfile

def inspect_file_inodes():
    with tempfile.TemporaryDirectory() as tmpdir:
```
- **Step 1: Create the Original File**:
  We write `"Hello Linux Storage"` to `original.txt`.
- **Step 2: Inspect Inode Number**:
  We call `stat_orig = os.stat(orig_path)`.
  The inode number is stored in `stat_orig.st_ino`, and the hard link count is in `stat_orig.st_nlink`.
- **Step 3: Create a Hard Link**:
  `os.link(orig_path, hard_path)` invokes the Linux `link()` system call.
  When we inspect `hard_path`, its `st_ino` is **identical** to the original file, and `st_nlink` increments to `2`!
- **Step 4: Create a Soft Link**:
  `os.symlink(orig_path, soft_path)` invokes `symlink()`.
  When we inspect `soft_path` using `os.lstat()`, its inode number is **completely different** because a new inode was created for the symlink.
- **Step 5: Delete Original File**:
  We call `os.unlink(orig_path)`.
  The hard link still works perfectly and retains the data! The soft link becomes broken (dangling).

---

## 4. How to Run the Script

```bash
cd code/day-12
python inode_inspector.py
```

### Expected Output
```
Original File:
  Inode: 142857, Link Count: 1
Hard Link Created:
  Inode: 142857, Link Count: 2 (Matches Original!)
Soft Link Created:
  Inode: 142899, Link Count: 1 (Distinct New Inode!)
Original File Unlinked:
  Hard Link Inode: 142857, Link Count: 1 (Data still accessible!)
```

---

## 5. Beginner Exercises to Try
1. Read the contents of `hard_path` after `orig_path` is unlinked. Verify that the text `"Hello Linux Storage"` is still readable!
2. Try opening `soft_path` after `orig_path` is deleted using `open(soft_path, "r")`. Notice that Python raises `FileNotFoundError` because the symlink is dangling!
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

