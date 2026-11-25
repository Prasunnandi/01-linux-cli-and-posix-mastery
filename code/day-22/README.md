# Hands-On Lab: Day 22 - Shell Exit Status & EXIT Trap Engine (`exit_trap_runner.py`)

## 1. What Are We Building & Why Does It Matter?
In Unix, every program ends by returning an integer **Exit Code** between 0 and 255.
- `0` means **Success**.
- Anything non-zero (`1` to `255`) indicates an **Error**.

If a script creates temporary files or locks and crashes halfway through, those files will remain on disk forever unless an **EXIT Trap** (`trap 'cleanup' EXIT`) is configured. In this lab, we build `exit_trap_runner.py` to simulate command exit evaluation and guarantee cleanup handlers execute even under sudden errors.

---

## 2. Python Concepts for Beginners
1. **The `try ... except ... finally` Block**:
   - `try`: Code that might fail.
   - `except`: Catches errors and prevents the whole program from crashing silently.
   - `finally`: Code that is **guaranteed to run no matter what happens**! This is Python's direct equivalent of Bash's `trap ... EXIT`.
2. **First-Class Functions**:
   - In Python, functions can be passed around as variables! We pass `mock_cleanup_handler` into `engine.register_trap()`.

---

## 3. Step-by-Step Code Walkthrough

```python
def run_script_safely(self, abort_on_error: bool = True) -> int:
    try:
        # Step 2: Simulates command failure
        code = self.execute_command("fetch_remote_payload", should_succeed=False)
        if code != 0 and abort_on_error:
            raise RuntimeError("Command failed!")
    finally:
        # Executes unconditionally!
        for handler in self.trap_handlers:
            handler(self.execution_log)
```
- Even when `RuntimeError` is raised, Python jumps immediately into `finally:`, executing the cleanup handler before the program exits.

---

## 4. How to Run the Script

```bash
cd code/day-22
python exit_trap_runner.py
```

### Expected Output
```
====================================================
SHELL EXIT STATUS & EXIT TRAP EXECUTION ENGINE
====================================================

Execution Trace:
  |-- STEP 1: Created temporary lock /var/run/app.lock
  |-- EXEC: fetch_remote_payload -> FAILED (1)
  |-- ABORT: Command failed under set -e strict mode!
  |-- TRAP TRIGGERED: rm -f /var/run/app.lock (Cleanup completed cleanly)

Final Script Exit Status: 1
[SUCCESS] EXIT Trap executed deterministically despite script crash!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`KeyboardInterrupt` handling**:
   - If the user presses `Ctrl+C`, Python raises a `KeyboardInterrupt` exception. If unhandled, this crashes the program immediately. Using `try ... finally` guarantees cleanup routines run even during interrupts.
2. **`NameError: name 'sys' is not defined`**:
   - Make sure `import sys` is present at the top of your script before calling `sys.exit()`.
3. **Suppressing Exit Traps**:
   - Calling `os._exit()` directly bypasses Python's cleanup hooks and `finally` blocks! Always use `sys.exit()` for normal graceful termination.

---

## 6. Beginner Exercises & Challenges
1. **Simulate `SIGKILL` (Signal 9)**:
   - Try adding a trap for `SIGKILL` in the simulator. Why does the operating system prohibit trapping `SIGKILL`? Verify that the simulator raises an error if an uncatchable signal is trapped.
2. **Add Temporary File Cleanup**:
   - Enhance `exit_trap_runner.py` to create a list of mock temporary files `['/tmp/scratch1.lock', '/tmp/scratch2.tmp']` and guarantee they are deleted during the `EXIT` handler even if an uncaught exception is thrown.
3. **Trap Chaining**:
   - Modify the engine so that multiple functions can register for `EXIT`. Ensure they execute in reverse registration order (LIFO - Last In, First Out).
