# Day 53: PAM Stack Evaluator & Control Flag FSM Lab Tutorial

Welcome to Day 53 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of Pluggable Authentication Modules (PAM) stack evaluation, implementing the finite state machine for `required`, `requisite`, `sufficient`, and `optional` control flags.

---

## 1. What Are We Building & Why Does It Matter?

Instead of hardcoding password verification into every application, Linux uses PAM (`/etc/pam.d/`). When logging in via SSH, `sshd` calls PAM. PAM processes a stack of dynamically loaded modules (e.g. checking LDAP, Kerberos, TOTP tokens, password history).

The key complexity lies in PAM **Control Flags**:
- **`required`**: If this module fails, authentication fails, but PAM continues running remaining modules to prevent timing attacks.
- **`requisite`**: If this module fails, PAM aborts the stack immediately.
- **`sufficient`**: If this module succeeds (and no prior `required` failed), PAM terminates with success immediately.
- **`optional`**: Only impacts the outcome if it is the only module in the stack.

In this lab, you implement this exact state machine in pure Python.

---

## 2. Python Concepts for Beginners

### A. Python Callables for Modular Handlers
We can pass function names as arguments to represent dynamic module handlers:
```python
from typing import Callable

def my_handler(username: str, context: dict) -> int:
    return 0

handler_ptr: Callable[[str, dict], int] = my_handler
```

### B. Python Enums for Status Codes
Use `enum.Enum` to define clear, readable protocol states:
```python
import enum

class PAMControlFlag(enum.Enum):
    REQUIRED = "required"
    REQUISITE = "requisite"
    SUFFICIENT = "sufficient"
```

### C. List Comprehensions for Filtering Stacks
Filter rules belonging to a specific management group (e.g. `auth` or `session`):
```python
auth_rules = [r for r in rules if r.group == "auth"]
```

---

## 3. Step-by-Step Code Walkthrough

1. **`PAMControlFlag` & `PAMStatus`**: Enums defining RFC 86.0 flags and module return values.
2. **`PAMModuleRule` Dataclass**: Binds a service group, a control flag, a module name, and a callable handler.
3. **`PAMStackEngine`**:
   - `register_service_rule()`: Adds rules to service stacks (`/etc/pam.d/<service>`).
   - `evaluate_stack()`:
     - Maintains two state flags: `required_failed` and `sufficient_success`.
     - Iterates through module rules.
     - On `requisite` failure, returns `False` immediately.
     - On `sufficient` success without prior `required` failure, returns `True` immediately.
4. **`main()` Test Suite**: Validates multi-factor SSH authentication, requisite immediate abort, and sufficient biometric bypass.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-53/pam_stack_evaluator_fsm.py
```

Expected output:
```text
=== Day 53: PAM Stack Evaluator & Control Flag Finite State Machine ===
[*] Test 1 Passed: Multi-factor authenticated successfully: Stack completed: Final Verdict = SUCCESS
[*] Test 2 Passed: Requisite failure immediately aborted evaluation without evaluating TOTP
[*] Test 3 Passed: Sufficient module succeeded, bypassing password prompt cleanly
[*] Test 4 Passed: Sufficient module failed, fallback to required password succeeded
All PAM Stack Evaluator assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`TypeError: 'PAMControlFlag' object is not callable`**: Ensure you access `.value` when comparing strings against enum objects.
- **Accidental Short-Circuiting**: Remember that `required` modules must NOT abort execution immediately; they must record failure and allow subsequent modules to run.

---

## 6. Beginner Exercises & Challenges

1. **Implement `substack` Execution**: Extend the engine to support nested substacks, where a child stack returns a single composite status to the parent stack.
2. **Add Environment Mutation (`pam_env`)**: Allow modules to inject environment variables into the `context` dictionary.
3. **Implement Password Mutation (`password` group)**: Add support for checking password history uniqueness via a simulated `pam_pwhistory` module.
