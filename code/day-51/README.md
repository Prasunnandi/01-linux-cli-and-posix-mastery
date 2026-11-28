# Day 51: Linux User & Shadow Password Database Engine Lab Tutorial

Welcome to Day 51 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of the POSIX user management system, parsing `/etc/passwd` and `/etc/shadow`, verifying cryptographic password digests, and auditing UID collisions.

---

## 1. What Are We Building & Why Does It Matter?

On every Linux system, process identity and file access control depend on numeric User Identifiers (UIDs) and Group Identifiers (GIDs). Because `/etc/passwd` must be world-readable for tools like `ls` to display user names, hashed passwords are kept in `/etc/shadow`, readable only by root.

In this lab, you build:
- Parsers for both `/etc/passwd` and `/etc/shadow` records.
- PBKDF2-HMAC-SHA512 password verification with random salt generation.
- Epoch-based password expiration calculations ($T / 86400$).
- Account locking checks (symbols `!` and `*`).
- An auditor detecting dangerous UID 0 collisions where rogue accounts duplicate root's authority.

---

## 2. Python Concepts for Beginners

### A. Epoch Time Calculations
Unix epoch time measures elapsed seconds since January 1, 1970. Dividing by 86,400 yields elapsed days:
```python
import time

epoch_seconds = time.time()
epoch_days = int(epoch_seconds // 86400)
```

### B. Constant-Time Hash Comparison (`hmac.compare_digest`)
Standard equality checks (`==`) terminate on the first mismatched byte, creating timing side-channel vulnerabilities. Use `hmac.compare_digest()` for constant-time comparisons:
```python
import hmac

is_valid = hmac.compare_digest(computed_hash, stored_hash)
```

### C. Data Classes (`@dataclass`)
Data classes automatically generate constructors and field representations for structured records:
```python
from dataclasses import dataclass

@dataclass
class PasswdEntry:
    username: str
    uid: int
    gid: int
```

---

## 3. Step-by-Step Code Walkthrough

1. **`PasswdEntry` & `ShadowEntry`**: Models the standard 7-field `/etc/passwd` and 9-field `/etc/shadow` structures.
2. **`UserDatabaseEngine`**:
   - `hash_password()`: Combines plaintext with a random salt and hashes it with 5000 rounds of PBKDF2-HMAC-SHA512.
   - `add_user()`: Generates random salt, hashes the password, records creation timestamp, and maps UID to username.
   - `authenticate()`:
     - Rejects locked accounts (`!` or `*`).
     - Enforces absolute expiration (`expire_days`).
     - Enforces password maximum validity age (`max_days`).
     - Verifies password using `hmac.compare_digest()`.
   - `audit_uid_zero_collisions()`: Finds all accounts sharing UID 0 other than `root`.
3. **`main()` Test Suite**: Validates password verification, expiration calculation, locking flags, and UID 0 collision detection.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-51/passwd_shadow_database_engine.py
```

Expected output:
```text
=== Day 51: Linux User & Shadow Password Database Engine ===
[*] Test 1 Passed: Valid credentials accepted (Authentication successful)
[*] Test 2 Passed: Invalid credentials rejected (Invalid password)
[*] Test 3 Passed: Password aging expiration enforced (Password expired; change required)
[*] Test 4 Passed: Account locking flag (!) enforced (Account is locked)
[*] Test 5 Passed: Security audit successfully detected UID 0 collision: ['backdoor_admin']
All User & Shadow Database Engine assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`TypeError: unsupported operand type(s) for //: 'NoneType'`**: Ensure `current_timestamp` defaults to `time.time()` if not explicitly passed.
- **Timing Attack Vulnerabilities**: Never use `str1 == str2` when validating cryptographic hashes. Always use `hmac.compare_digest()`.
- **Integer Division Truncation**: Use `// 86400` to calculate complete elapsed calendar days without fractional float residuals.

---

## 6. Beginner Exercises & Challenges

1. **Implement Warning Period Alerts**: Add an `is_in_warning_period()` method returning `True` if `current_days` is within `warn_days` of password expiration.
2. **Support Multiple Crypt Hashes**: Extend `hash_password()` to support legacy MD5 (`$1$`) or modern yescrypt (`$y$`) formats based on a parameter.
3. **Export to Flat Files**: Write a method that serializes `passwd_db` and `shadow_db` into standard colon-delimited Linux `/etc/passwd` and `/etc/shadow` text files.
