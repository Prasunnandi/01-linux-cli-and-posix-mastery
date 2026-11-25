# Hands-On Lab: Day 25 - Strict Mode & Pipeline Evaluator (`strict_mode_pipeline.py`)

## 1. What Are We Building & Why Does It Matter?
By default, Bash is notoriously forgiving:
1. If a command in a pipeline fails (`mysqldump | gzip`), Bash ignores the error if the last command (`gzip`) succeeds!
2. If you misspell a variable name (`rm -rf "$BACKUP_DIR/$NAME"`), Bash replaces it with an empty string, which can wipe your root drive!

Adding `set -euo pipefail` fixes these vulnerabilities. In this lab, we build `strict_mode_pipeline.py` to evaluate pipeline exit codes under both standard and strict mode.

---

## 2. Python Concepts for Beginners
1. **Lists of Integers**:
   - `pipeline = [2, 0]` represents the exit statuses of commands in a pipe.
2. **Reverse Scanning (`reversed()`)**:
   - Scans right-to-left to find the last failing command.
3. **Raising Exceptions (`raise KeyError(...)`)**:
   - Halts program execution immediately when an unbound variable is detected.

---

## 3. Step-by-Step Code Walkthrough

```python
def evaluate_pipeline(command_exit_codes: list, pipefail: bool) -> int:
    if not pipefail:
        return command_exit_codes[-1] # Returns last command's exit code
    for code in reversed(command_exit_codes):
        if code != 0:
            return code # Returns rightmost failure
    return 0
```
- When `pipefail=True`, `[2, 0]` evaluates to `2`, triggering an alert. Under default mode, it evaluates to `0`, silently concealing the database backup failure.

---

## 4. How to Run the Script

```bash
cd code/day-25
python strict_mode_pipeline.py
```

### Expected Output
```
====================================================
BASH STRICT MODE & PIPELINE EXIT EVALUATOR
====================================================
Pipeline: [mysqldump (exit: 2)] | [gzip (exit: 0)]
  Lax Bash Mode (default)      : Exit Code 0 (ERROR MASKED!)
  Strict Mode (set -o pipefail): Exit Code 2 (FAILURE DETECTED)

Testing 'set -u' (nounset) Variable Safety:
  Lax mode on unset $DATABASE_DIR: '' (Dangerous empty string!)
  Strict mode on unset $DATABASE_DIR: Caught 'bash: DATABASE_DIR: unbound variable (set -u aborted script!)'

[SUCCESS] Strict mode protections verified operational!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`KeyError: 'MY_VAR'`**:
   - Accessing `os.environ['MY_VAR']` directly raises `KeyError` if the variable is not set. Use `os.environ.get('MY_VAR', 'default')` to provide fallbacks, mirroring `${MY_VAR:-default}`.
2. **Subprocess Pipe Deadlocks**:
   - When piping data between subcommands using Python `subprocess.Popen`, using `stdout=PIPE` without draining it via `.communicate()` can cause child processes to freeze when the OS pipe buffer (64 KB) fills up.
3. **Boolean Status Confusion**:
   - In Linux shells, exit status `0` means **Success** and non-zero means **Failure**. In Python, `0` is **Falsy** and non-zero numbers are **Truthy**. Always remember this inversion when checking return codes!

---

## 6. Beginner Exercises & Challenges
1. **Pipes vs Subshells**:
   - Why does `pipefail` matter in `curl -s https://bad-url | jq .`? Write a test showing that without `pipefail`, the pipeline returns exit status `0` even if `curl` fails with error 404!
2. **The `set -u` Trap with Empty Arrays**:
   - In older Bash versions, expanding an empty array `${EMPTY_ARRAY[@]}` under `set -u` triggered an unbound variable error. Demonstrate how modern `${EMPTY_ARRAY[@]:-}` protects against this.
3. **Building a Production Script Wrapper**:
   - Wrap a simulated deployment task inside strict mode and verify that every failed sub-command triggers an immediate halt and post-mortem dump.
