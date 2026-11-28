# Day 52: Sudoers Rule Evaluator & Timestamp Ticket Engine Lab Tutorial

Welcome to Day 52 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of the `sudoers` declarative grammar evaluator, alias resolution engine, and timestamp ticket cache (`/run/sudo/ts/`).

---

## 1. What Are We Building & Why Does It Matter?

Distributing root passwords is an enterprise anti-pattern. `sudo` provides granular, auditable privilege delegation. Instead of executing everything as root, users invoke specific whitelisted commands while `sudo` verifies rules in `/etc/sudoers`.

In this lab, you build:
- An evaluator parsing User specifications, Host restrictions, RunAs identities, and Command rules.
- Support for `User_Alias` and `Cmnd_Alias`.
- The `NOPASSWD` execution modifier.
- The 15-minute credential ticket cache (`/run/sudo/ts/`) that suppresses password re-prompting on the same terminal.

---

## 2. Python Concepts for Beginners

### A. Tuple Dictionary Keys for Multi-Dimensional Caches
Dictionaries can use tuples as keys to track multi-parameter state (e.g. user and terminal device):
```python
ticket_cache = {}
ticket_key = ("alice", "/dev/pts/1")
ticket_cache[ticket_key] = current_timestamp
```

### B. Shell-Style Pattern Matching (`fnmatch.fnmatch`)
To match wildcards in command paths (such as `/usr/bin/systemctl * nginx`), use Python's built-in `fnmatch`:
```python
import fnmatch

matches = fnmatch.fnmatch("/usr/bin/systemctl restart nginx", "/usr/bin/systemctl * nginx")
```

### C. Sets for Fast Membership Testing
Store aliases in hash sets for $O(1)$ lookup time:
```python
authorized_users = {"alice", "bob", "carol"}
if user in authorized_users:
    # Authorized
```

---

## 3. Step-by-Step Code Walkthrough

1. **`SudoRule` Dataclass**: Captures the standard components of an `/etc/sudoers` line: `user_spec`, `host_spec`, `runas_user`, `command_spec`, `nopasswd`.
2. **`SudoersEngine`**:
   - `add_user_alias()` & `add_cmnd_alias()`: Registers user and command groupings.
   - `_matches_user()`: Checks direct username match, group membership (`%group`), or user alias.
   - `_matches_command()`: Checks command aliases or exact string matches.
   - `evaluate()`:
     - Scans rules from top to bottom (last matching rule wins).
     - Checks `nopasswd`.
     - Validates the 15-minute (`900` second) ticket window for the given user and TTY.
   - `update_ticket()`: Stores the authentication timestamp in the cache.
3. **`main()` Test Suite**: Validates NOPASSWD execution, unauthorized command rejection, password prompt triggers, and ticket cache expiration.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-52/sudoers_rule_evaluator_and_ticket_engine.py
```

Expected output:
```text
=== Day 52: Sudoers Rule Evaluator & Timestamp Ticket Engine ===
[*] Test 1 Passed: Alice authorized under NOPASSWD: Authorized via NOPASSWD
[*] Test 2 Passed: Alice unauthorized command rejected: User alice is not in the sudoers file
[*] Test 3 Passed: Charlie authorized with password prompt: Password authentication required
[*] Test 4 Passed: Charlie cached ticket accepted at t+300s: Authorized via valid ticket cache
[*] Test 5 Passed: Charlie ticket expired at t+901s, re-prompt enforced: Password authentication required
All Sudoers Rule Evaluator assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`KeyError` when looking up ticket**: Use `if ticket_key in self.ticket_cache:` before accessing dictionary elements directly.
- **Rule Ordering Bugs**: In `sudoers`, the *last* matching rule takes precedence. Ensure your loop iterates through all rules without returning on the first match.

---

## 6. Beginner Exercises & Challenges

1. **Implement `secure_path` Sanitization**: Add an environment sanitization method that strips custom `$PATH` definitions and enforces a hardened system default.
2. **Support `NOEXEC` Flag**: Add a boolean `noexec` flag to `SudoRule` that prevents the executed program from invoking secondary shell child processes.
3. **Add CIDR Subnet Host Matching**: Extend `host_spec` to match IP addresses against CIDR prefixes (e.g. `192.168.1.0/24`) using Python's `ipaddress` module.
