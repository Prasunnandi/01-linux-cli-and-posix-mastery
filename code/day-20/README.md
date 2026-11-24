# Hands-On Lab: Day 20 - Kernel Module Dependency Resolver (`module_dependency_resolver.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux, device drivers are loaded as kernel modules using `modprobe`.
However, modules frequently depend on other modules. For example:
- `fat.ko` depends on nothing.
- `vfat.ko` depends on `fat.ko`.
- `usb_storage.ko` depends on `scsi_mod.ko`.

If you try to load `vfat.ko` before `fat.ko`, the kernel rejects the module with `Unknown symbol in module`.
The `modprobe` tool reads `/lib/modules/$(uname -r)/modules.dep` and performs a **Topological Sort** on the dependency graph to determine the exact, safe order in which modules must be inserted.

In this lab, we build `module_dependency_resolver.py` to implement recursive topological sorting to resolve kernel module load sequences.

---

## 2. Python Concepts for Beginners
1. **Graphs Represented as Dictionaries**:
   - A graph is a set of nodes and connections. In Python, we represent dependencies as a dictionary where each key is a module, and its value is a list of modules it depends on:
     ```python
     deps = {
         "vfat": ["fat"],
         "fat": [],
         "ext4": ["crc16", "jbd2"],
         "jbd2": [],
         "crc16": [],
     }
     ```
2. **Recursion (Functions Calling Themselves)**:
   - To resolve dependencies, the function `dfs(node)` visits each prerequisite before appending the current module:
     ```python
     for prerequisite in dependency_graph.get(module, []):
         if prerequisite not in visited:
             dfs(prerequisite)
     ```
3. **Sets for Visited Tracking (`set()`)**:
   - Prevents processing the same module twice or getting stuck in infinite loops.

---

## 3. Step-by-Step Code Walkthrough

```python
def resolve_module_load_order(dependency_graph: dict, target_module: str) -> list:
    visited = set()
    load_order = []

    def dfs(module):
        visited.add(module)
        for dep in dependency_graph.get(module, []):
            if dep not in visited:
                dfs(dep)
        load_order.append(module)

    dfs(target_module)
    return load_order
```
- When `resolve_module_load_order(deps, "ext4")` is called:
  1. `dfs("ext4")` is invoked.
  2. `ext4` depends on `crc16`. `dfs("crc16")` is called.
  3. `crc16` has no dependencies, so `"crc16"` is appended to `load_order`.
  4. Next, `ext4` depends on `jbd2`. `dfs("jbd2")` is called and appended.
  5. Finally, `"ext4"` itself is appended!
- Result: `['crc16', 'jbd2', 'ext4']`. Every prerequisite is guaranteed to be loaded before the driver that needs it!

---

## 4. How to Run the Script

```bash
cd code/day-20
python module_dependency_resolver.py
```

### Expected Output
```
Resolving dependencies for 'ext4':
  Load Sequence: ['crc16', 'jbd2', 'ext4']

Resolving dependencies for 'overlay' (Docker filesystem):
  Load Sequence: ['overlay']

Resolving dependencies for 'xfs':
  Load Sequence: ['libcrc32c', 'xfs']
```

---

## 5. Beginner Exercises to Try
1. Add a multi-tier dependency chain: `module_a` depends on `module_b`, which depends on `module_c`. Verify that the resolver produces `['module_c', 'module_b', 'module_a']`.
2. Add circular dependency detection: if `A` depends on `B` and `B` depends on `A`, detect the cycle and raise an error.
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

