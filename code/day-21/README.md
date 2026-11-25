# Hands-On Lab: Day 21 - Process Environment & Subshell Simulator (`subshell_env_sim.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux, when you run commands inside parentheses `( ... )` or on the right side of a pipe `cat file | while read line; do ... done`, Bash spawns a **subshell**.
A subshell is a distinct child process created via the `fork()` system call. It receives a private copy of the parent's variables and environment table.

A common bug for beginners is trying to increment a counter or set a variable inside a pipeline loop, only to discover that the variable is still `0` after the loop finishes! In this lab, we build `subshell_env_sim.py` to model the exact mechanics of process memory isolation.

---

## 2. Python Concepts for Beginners
1. **Deep Copying (`copy.deepcopy()`)**:
   - In Python, if you do `dict2 = dict1`, both variables point to the **exact same memory dictionary**! Changing `dict2` will secretly alter `dict1`.
   - To simulate a real operating system `fork()`, we use `copy.deepcopy()`, which creates a completely independent clone in memory.
2. **Object-Oriented Programming (`class`)**:
   - `class ProcessContext` acts as our simulated Linux `task_struct`, storing process ID (`pid`), parent PID (`ppid`), environment variables (`env`), and local variables.
3. **The `assert` Statement**:
   - Checks that parent memory remained uncorrupted. If an assertion fails, Python crashes with an error.

---

## 3. Step-by-Step Code Walkthrough

```python
class ProcessContext:
    def fork_subshell(self, child_pid: int) -> 'ProcessContext':
        return ProcessContext(
            pid=child_pid,
            ppid=self.pid,
            name=f"{self.name}_child",
            env=copy.deepcopy(self.env),
            local_vars=copy.deepcopy(self.local_vars)
        )
```
- `fork_subshell` simulates the `fork()` system call.
- The child process mutates `APP_CONFIG` to `"child_mutated.yaml"` and `loop_counter` to `"999"`.
- When the parent state is inspected, its values are still `"production.yaml"` and `"0"`.

---

## 4. How to Run the Script

```bash
cd code/day-21
python subshell_env_sim.py
```

### Expected Output
```
====================================================
BASH PROCESS ENVIRONMENT & SUBSHELL ISOLATION
====================================================
Parent State (PID: 1000):
  APP_CONFIG   : production.yaml
  loop_counter : 0

Child Subshell State (PID: 1001):
  APP_CONFIG   : child_mutated.yaml
  loop_counter : 999

[VERIFIED] Memory isolation 100% operational: Child mutations did not leak!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`AttributeError: 'NoneType' object has no attribute 'deepcopy'`**:
   - Ensure you wrote `import copy` at the top of your file.
2. **`KeyError: 'APP_CONFIG'`**:
   - You tried to access a dictionary key that was not set. Use `.get("APP_CONFIG", "default")` to avoid crashes.
---

## 6. Beginner Exercises & Challenges
1. **Experiment with Variable Export**:
   - In `subshell_env_sim.py`, what happens if you add a new variable to `local_vars` without adding it to `env`? Verify that non-exported local variables are invisible when a subshell executes an external program.
2. **Model Nested Subshells**:
   - Extend the simulator to create a grandchild subshell `( ( echo deep ) )`. Verify that modifications inside the grandchild do not affect either the child or the root parent!
3. **Pipeline Variable Leak Trap**:
   - Write a standalone test demonstrating why `cat file | while read x; do count=$((count+1)); done; echo $count` outputs `0` in standard Bash (because the loop runs in a subshell!).
