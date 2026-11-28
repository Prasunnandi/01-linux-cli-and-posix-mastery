# Day 59: AppArmor Deterministic Finite Automaton (DFA) Lab Tutorial

Welcome to Day 59 of Linux CLI and POSIX Mastery. Today, you will build a Python simulation of the AppArmor Mandatory Access Control (MAC) engine, parsing path profiles, implementing `enforce` vs `complain` modes, and evaluating explicit denials.

---

## 1. What Are We Building & Why Does It Matter?

Under standard Linux Discretionary Access Control (DAC), if a web daemon running as `www-data` is compromised, the attacker has full access to everything owned by `www-data`.

AppArmor confines programs by path:
- Restricts applications to the exact files and capabilities they need to function.
- **Explicit Denials**: Overrides all other rules (e.g. denying access to `/etc/shadow` or `/bin/sh`).
- **Enforce Mode**: Violations are blocked with `-EACCES`.
- **Complain Mode**: Violations are permitted to execute, but an audit log entry is generated for learning application behavior.

In this lab, you simulate AppArmor's path evaluation engine in Python.

---

## 2. Python Concepts for Beginners

### A. Glob Pattern Matching (`fnmatch.fnmatch`)
Match path patterns containing `*` (single directory) and `**` (recursive directories):
```python
import fnmatch

is_matched = fnmatch.fnmatch("/var/www/html/index.html", "/var/www/html/**")
```

### B. Priority Inversion with Explicit Denials
In security engines, negative assertions (DENY) must always take precedence over positive assertions (ALLOW):
```python
# Check denials first
for deny_rule in self.denied_rules:
    if matches(deny_rule):
        return False  # Abort immediately!
```

### C. Enums for Security Modes
Represent operational modes clearly using Python enums:
```python
import enum

class AppArmorMode(enum.Enum):
    ENFORCE = "enforce"
    COMPLAIN = "complain"
```

---

## 3. Step-by-Step Code Walkthrough

1. **`AppArmorMode` & `ExecModifier`**: Enums defining profile enforcement modes and sub-process execution flags (`px`, `ix`, `ux`).
2. **`FileRule` Dataclass**: Captures path pattern, permission characters (`r`, `w`, `x`), and boolean denial flag.
3. **`AppArmorProfile`**:
   - `add_rule()`: Segregates rules into `file_rules` and `denied_rules`.
   - `check_access()`:
     1. Evaluates `denied_rules`. Rejects access immediately if in `ENFORCE` mode.
     2. Evaluates `file_rules`. Grants access if pattern and permissions match.
     3. If unprofiled, checks `mode`. Returns `True` with warning in `COMPLAIN` mode; returns `False` in `ENFORCE` mode.
4. **`main()` Test Suite**: Validates legitimate file reads/writes, explicit shadow denial, shell execution blocks, and complain mode learning.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-59/apparmor_dfa_path_matcher.py
```

Expected output:
```text
=== Day 59: AppArmor Deterministic Finite Automaton (DFA) Path Matcher ===
[*] Test 1 Passed: Legitimate read allowed: ALLOWED: Matched rule '/var/www/html/**' (r)
[*] Test 2 Passed: Log writing allowed: ALLOWED: Matched rule '/var/log/nginx/*.log' (w)
[*] Test 3 Passed: Access to /etc/shadow strictly blocked: DENIED: Explicit deny rule matched for /etc/shadow
[*] Test 4 Passed: Shell execution strictly blocked: DENIED: Explicit deny rule matched for /bin/sh
[*] Test 5 Passed: Unprofiled path blocked in enforce mode: DENIED: No rule allows r access to /opt/secret.txt
[*] Test 6 Passed: Complain mode permits access and logs audit record: COMPLAIN WARNING: No rule for /opt/secret.txt (Allowed in complain mode)
All AppArmor Path Matcher assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **Order of Evaluation Errors**: Always evaluate `denied_rules` before allowed rules to prevent permissive rules from shadowing explicit blocks.
- **Permission Substring Checks**: Check `if requested_perm in r.permissions:` to ensure multi-permission strings like `"rw"` match single requests for `"r"`.

---

## 6. Beginner Exercises & Challenges

1. **Implement Recursive Glob Parser**: Replace `fnmatch` with a custom regex compiler converting AppArmor `/path/**` syntax into a DFA.
2. **Add Capability Rules**: Extend `AppArmorProfile` to enforce capability restrictions (e.g. `capability net_bind_service`).
3. **Audit Log Formatter**: Format violation messages into standard Linux auditd `type=AVC` syslog lines.
