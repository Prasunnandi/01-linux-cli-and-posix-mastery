# Day 56: Linux Capabilities Transformation Engine Lab Tutorial

Welcome to Day 56 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of the Linux Capabilities system, calculating the 5 capability sets and simulating mathematical transformations during `execve()`.

---

## 1. What Are We Building & Why Does It Matter?

The monolithic superuser (root / UID 0) has full authority over the entire operating system. If a service needs to bind port 80 or send ICMP ping packets, running it as SUID root exposes the system to catastrophic privilege escalation.

Linux Capabilities decompose root into approximately 41 granular permissions:
- `CAP_NET_BIND_SERVICE`: Bind sockets to ports $< 1024$.
- `CAP_NET_RAW`: Open raw sockets for ping/sniffing.
- `CAP_SYS_ADMIN`: Mount filesystems, configure namespaces.

The kernel maintains 5 distinct sets per process:
1. **Permitted ($P_P$)**: Upper bound of capabilities that can be used.
2. **Effective ($P_E$)**: Active capabilities checked by kernel syscalls.
3. **Inheritable ($P_I$)**: Capabilities preserved across `execve()` when permitted by the file.
4. **Bounding ($P_B$)**: Absolute system ceiling. Capabilities dropped here cannot be regained.
5. **Ambient ($P_A$)**: Capabilities preserved across unprivileged `execve()`.

In this lab, you implement the exact mathematical transformation equations in Python.

---

## 2. Python Concepts for Beginners

### A. Python Sets for Bitmask Mathematics
Python sets provide intuitive set operations matching formal Boolean logic:
```python
# Union (|)
permitted = ambient | (bounding & file_permitted)

# Intersection (&)
allowed = bounding & requested

# Discard element
bounding.discard(Capability.CAP_SYS_ADMIN)
```

### B. Integer Enumerations (`enum.IntEnum`)
Map numeric capability bits to human-readable constants:
```python
import enum

class Capability(enum.IntEnum):
    CAP_DAC_OVERRIDE = 1
    CAP_NET_BIND_SERVICE = 10
    CAP_SYS_ADMIN = 21
```

### C. Optional Object Parameters
Use `Optional[FileCaps]` to differentiate between binaries with file capabilities and unprivileged standard binaries:
```python
from typing import Optional

def transform(caller: ProcessCreds, file_caps: Optional[FileCaps]):
    if file_caps is None:
        # Standard binary
```

---

## 3. Step-by-Step Code Walkthrough

1. **`Capability` Enum**: Defines core Linux capabilities.
2. **`ProcessCreds` & `FileCaps` Dataclasses**: Encapsulates the 5 process sets and the 3 file attributes.
3. **`CapabilityTransitionEngine`**:
   - `execve_transition()`: Implements the formal POSIX/Linux transformation formulas:
     $$P_P' = P_A \cup (P_B \cap F_P) \cup (P_I \cap F_I)$$
     $$P_E' = F_E \ ? \ P_P' : P_A$$
   - `drop_bounding_capability()`: Permanently strips a capability from $P_B$ and clears it from all other sets.
4. **`main()` Test Suite**: Validates unconfined execution, scoped file capability assignment, ambient inheritance, and container bounding set defense.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-56/linux_capabilities_transition_engine.py
```

Expected output:
```text
=== Day 56: Linux Capabilities Transformation Engine ===
[*] Test 1 Passed: Executing unconfined binary retains zero capabilities
[*] Test 2 Passed: File capability granted scoped CAP_NET_RAW without granting full root
[*] Test 3 Passed: Ambient capability successfully preserved across unprivileged execve()
[*] Test 4 Passed: Pruned Bounding Set successfully defeated privilege escalation attempt
All Linux Capabilities Transformation Engine assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`AttributeError: 'NoneType' object has no attribute 'permitted'`**: Always check `if file_caps:` before accessing file capability sets.
- **Set Mutation Side-Effects**: Use `set(caller.cap_ambient)` to create independent copies rather than mutating caller sets in-place.

---

## 6. Beginner Exercises & Challenges

1. **Implement Capability Verification Helper**: Write a `has_capability(creds, cap)` function that verifies whether a process has an active capability in its Effective set.
2. **Simulate `prctl(PR_SET_NO_NEW_PRIVS)`**: Add support for the `no_new_privs` bit, which blocks `execve()` from ever elevating capabilities even if the file possesses capabilities or SUID bits.
3. **Serialize to `getcap` / `setcap` Syntax**: Write a function that converts `FileCaps` into standard text format (e.g. `cap_net_raw=ep`).
