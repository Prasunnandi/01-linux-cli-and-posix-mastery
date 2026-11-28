# Day 54: POSIX Access Control List (ACL) Mask Calculator Lab Tutorial

Welcome to Day 54 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of POSIX.1e Access Control Lists, calculating the dynamic ACL Mask and implementing the kernel VFS access decision algorithm.

---

## 1. What Are We Building & Why Does It Matter?

Standard Linux permissions (`chmod`) allow permissions for only one owner, one group, and others. POSIX ACLs (`getfacl`, `setfacl`) allow granting access to multiple distinct users and groups on the same file.

Crucially, POSIX ACLs introduce the **ACL Mask**:
- The Mask defines an absolute ceiling on permissions for all named users and groups.
- Even if `user:alice:rwx` is set, if the mask is `r--`, Alice's effective permission is strictly read-only ($7 \cap 4 = 4$).
- Executing `chmod g+w` on an ACL file overwrites the mask rather than the owning group!

In this lab, you implement this exact bitwise logic in pure Python.

---

## 2. Python Concepts for Beginners

### A. Bitwise Flags for Permissions
Represent permissions using binary octal values: Read (4 = `100_2`), Write (2 = `010_2`), Execute (1 = `001_2`):
```python
PERM_R = 4
PERM_W = 2
PERM_X = 1

# Check if permission bit is set
if (user_perms & PERM_W) == PERM_W:
    print("Write permitted")
```

### B. Bitwise Intersection (AND `&`)
Calculate effective permissions by intersecting entry permissions with the mask:
```python
effective_perms = entry_perms & mask_perms
```

### C. Bitwise Union (OR `|`)
Calculate the automatic mask by taking the union of all group and named user permissions:
```python
mask = 0
for entry in entries:
    mask |= entry.perms
```

---

## 3. Step-by-Step Code Walkthrough

1. **`ACLTag` Enum**: Defines the 6 POSIX entry types (`USER_OBJ`, `USER`, `GROUP_OBJ`, `GROUP`, `MASK`, `OTHER`).
2. **`POSIXACLEngine`**:
   - `calculate_mask()`: Computes the bitwise union of all named users, named groups, and owning group.
   - `get_effective_perms()`: Applies `entry.perms & mask` for named entities.
   - `check_access()`: Implements the exact 4-tier kernel decision algorithm:
     1. Is caller the file owner? Evaluate `USER_OBJ` directly (ignores Mask).
     2. Does caller match a named `USER`? Evaluate `perms & Mask`.
     3. Does caller match any group? Union all matching groups and evaluate `union & Mask`.
     4. Fall through to `OTHER`.
3. **`main()` Test Suite**: Validates auto-mask calculation, mask restriction on named users, owner bypass, and other-user rejection.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-54/posix_acl_mask_calculator.py
```

Expected output:
```text
=== Day 54: POSIX Access Control List (ACL) Mask Calculator ===
[*] Test 1 Passed: Auto-calculated mask union = rwx (7)
[*] Test 2 Passed: Alice write blocked by ACL Mask: Denied: Named User 'alice' effective perms (r--) insufficient
[*] Test 3 Passed: Alice read access permitted: Granted via Named User 'alice' (Effective: r--)
[*] Test 4 Passed: Owner ignores mask and retains full authority: Granted via Owner (USER_OBJ)
[*] Test 5 Passed: Other user denied access: Denied via OTHER
All POSIX ACL Mask Calculator assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`TypeError: unsupported operand type(s) for &: 'NoneType'`**: Always verify whether an explicit `ACLTag.MASK` exists in the entry list before applying bitwise intersection.
- **Precedence Confusion**: Remember that if a caller matches a named user, the algorithm terminates immediately—it does not evaluate subsequent group permissions.

---

## 6. Beginner Exercises & Challenges

1. **Implement Default ACL Inheritance**: Write an `inherit_directory_acls()` function that generates child access ACLs from parent Default ACLs.
2. **Format to `getfacl` Text Output**: Add a serializer that converts an `ACLEntry` list into the exact output format produced by `getfacl`.
3. **Simulate `chmod g-w` Mask Mutation**: Implement a method demonstrating how standard `chmod` calls unintentionally alter the ACL Mask on files with extended ACLs.
