# Day 60: SELinux Type Enforcement & AVC Engine Lab Tutorial

Welcome to Day 60 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of Security-Enhanced Linux (SELinux), parsing Flask 4-tuple security contexts, evaluating Type Enforcement (TE) policy matrices, managing the Access Vector Cache (AVC), and enforcing Multi-Category Security (MCS) container isolation.

---

## 1. What Are We Building & Why Does It Matter?

While standard Linux permissions check user identity, SELinux implements Mandatory Access Control (MAC) based on security labels. Even if an attacker attains root (UID 0), if their process domain is `httpd_t`, the kernel strictly prohibits them from accessing files labeled `shadow_t` or executing unauthorized network sockets.

Core architectural components:
- **Security Context 4-Tuple**: `user:role:type:mls_level`.
- **Type Enforcement (TE)**: An explicit whitelist matrix: `allow <subject_type> <object_type> : <class> { permissions }`.
- **Access Vector Cache (AVC)**: In-kernel hash table storing past decisions to deliver sub-microsecond access validation.
- **Dynamic Booleans**: 1-bit kernel switches toggling policy branches without rebooting.
- **Multi-Category Security (MCS)**: Mathematical category sets ($c0$ to $c1023$) that isolate containers sharing the same type.

In this lab, you implement this complete security engine in pure Python.

---

## 2. Python Concepts for Beginners

### A. Frozen Dataclasses as Hashable Keys
By declaring `@dataclass(frozen=True)`, dataclass instances become immutable and can be used directly as dictionary keys:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SecurityContext:
    user: str
    role: str
    type_domain: str
    mls_level: str
```

### B. Category Dominance via Set Operations
Bell-LaPadula mathematical dominance dictates that the subject's categories must be a superset of the object's categories:
```python
is_dominated = object_categories.issubset(subject_categories)
```

### C. Cache Invalidation Patterns
When a security policy or boolean changes, clear the cached decisions to force re-evaluation against the authoritative policy matrix:
```python
def reset(self):
    self.cache.clear()
```

---

## 3. Step-by-Step Code Walkthrough

1. **`SecurityContext` Dataclass**: Represents the 4-tuple security context string and parses MCS categories (`s0:c12,c34`).
2. **`SELinuxSecurityServer` Class**:
   - `add_allow_rule()`: Adds explicit permissions to the policy matrix.
   - `check_mcs_dominance()`: Enforces category lattice isolation.
   - `compute_decision()`: Checks MCS dominance, Type Enforcement matrix, and active dynamic booleans.
3. **`AccessVectorCache` Class**:
   - Maintains an in-memory decision table.
   - On cache hit: returns cached verdict instantly.
   - On cache miss: queries the security server and caches the result.
   - `reset()`: Flushes cache when booleans toggle.
4. **`main()` Test Suite**: Validates cache miss-to-hit transitions, unauthorized read denials, boolean toggles, and MCS container isolation.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-60/selinux_avc_cache_and_type_enforcement.py
```

Expected output:
```text
=== Day 60: SELinux Type Enforcement & Access Vector Cache (AVC) Engine ===
[*] Test 1 Passed: Initial query populated cache: AVC MISS (Consulted policy matrix & populated cache)
[*] Test 2 Passed: Repeated query resolved from cache: AVC HIT (Sub-microsecond kernel cache)
[*] Test 3 Passed: Unauthorized read of shadow_t denied by Type Enforcement policy
[*] Test 4 Passed: SELinux Boolean dynamically enabled database connection: AVC MISS (Consulted policy matrix & populated cache)
[*] Test 5 Passed: MCS Category lattice successfully isolated container volumes
All SELinux Type Enforcement & AVC Engine assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`TypeError: unhashable type: 'set'`**: Do not store mutable `set` objects inside tuple cache keys. Convert sets to strings or frozen sets: `tuple(sorted(categories))`.
- **Default Deny Assumption**: SELinux has no default allow. If a key is absent from `policy_matrix`, the engine must return `False`.

---

## 6. Beginner Exercises & Challenges

1. **Implement `audit2allow` Rule Generator**: Write a function that inspects a list of denied AVC logs and outputs the minimal `allow` policy rules needed to permit them.
2. **Support Negative Category Ranges**: Extend the category parser to handle ranges (e.g. `c0.c10`).
3. **Simulate Permissive Mode**: Add an `enforcing: bool` flag to the engine that logs denials but allows the syscall to proceed if false.
