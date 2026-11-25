# Hands-On Lab: Day 24 - Function Scope Tracker (`function_scope_tracker.py`)

## 1. What Are We Building & Why Does It Matter?
In languages like Python, variables defined inside functions are automatically local.
In Bash, **variables inside functions are GLOBAL by default** unless explicitly declared with `local`!
If a function uses `i=5` without `local i`, it overwrites the global variable `i`, which frequently corrupts loops in the calling script.

In this lab, we build `function_scope_tracker.py` to model the call-stack scope frames and demonstrate why `local` is mandatory.

---

## 2. Python Concepts for Beginners
1. **Stack Data Structures (`list.append()` and `list.pop()`)**:
   - A stack works like a stack of plates: Last-In, First-Out (LIFO).
   - Entering a function pushes a new dictionary onto the list (`append`).
   - Exiting a function pops the top dictionary off (`pop`).
2. **Reverse Iteration (`reversed(self.scopes)`)**:
   - Searches from the innermost scope frame backwards to the global frame.

---

## 3. Step-by-Step Code Walkthrough

```python
def set_variable(self, name: str, value: str, is_local: bool):
    if is_local:
        self.scopes[-1][name] = value # Writes to top frame
    else:
        self.scopes[0][name] = value  # Writes to global frame!
```
- When `is_local=False`, the variable writes directly to `scopes[0]` (the global table), demonstrating how missing `local` corrupts global script state.

---

## 4. How to Run the Script

```bash
cd code/day-24
python function_scope_tracker.py
```

### Expected Output
```
====================================================
BASH FUNCTION SCOPE STACK & LOCAL VARIABLE SIMULATOR
====================================================
Inside Function Scope:
  i         : 5
  local_var : secret

Outside (Global Scope Post-Call):
  i         : 5 (Accidentally mutated by helper!)
  local_var : (undefined) (Cleanly destroyed)

[VERIFIED] Scoping mechanics and global leakage verified!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`UnboundLocalError: local variable referenced before assignment`**:
   - In Python, if you assign to a variable inside a function, Python treats it as local to the entire function. If you try to read it before that assignment, Python throws this error. Use `global var_name` or pass it as an argument.
2. **Mutable Default Arguments Trap**:
   - Never write `def func(scope={})`! In Python, dictionary default arguments are evaluated once at module load time and shared across all calls. Always use `def func(scope=None): if scope is None: scope = {}`.
3. **Variable Shadowing**:
   - Naming a local variable `list` or `dict` shadows Python's built-in types and leads to strange `TypeError: 'list' object is not callable` errors.

---

## 6. Beginner Exercises & Challenges
1. **Dynamic Scoping Demonstration**:
   - Write a simulation where `func_a()` calls `func_b()`. If `func_a` defines `local x=10`, can `func_b` see `x` in Bash? (Answer: YES! Bash uses dynamic scoping, unlike Python which uses lexical scoping). Model this difference in code.
2. **Return Value vs Output Capture**:
   - Beginners often confuse `return 42` (an exit status byte 0-255) with returning string data. Add a validator that throws an error if someone tries to `return "hello"`.
3. **Pass-by-Reference with `declare -n`**:
   - In Bash 4.3+, `declare -n ref=$1` creates a nameref (pointer). Model nameref dereferencing in the simulator!
