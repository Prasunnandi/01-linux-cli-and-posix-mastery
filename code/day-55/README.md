# Day 55: ext4 Inode Immutable & Append-Only Flags Lab Tutorial

Welcome to Day 55 of Linux CLI and POSIX Mastery. Today, you will build a Python simulation of on-disk `ext4` filesystem inode flags, modeling the kernel VFS pre-check for `IMMUTABLE` (`+i`) and `APPEND` (`+a`) attributes.

---

## 1. What Are We Building & Why Does It Matter?

Standard UNIX permissions allow the superuser (`UID 0`) to modify or delete any file on the system. When an attacker attains root access, they can overwrite logs or install persistent rootkits.

Filesystem Extended Attributes (`chattr`, `lsattr`):
- Store flags directly inside the 32-bit `i_flags` field of the physical disk inode.
- Enforce Write-Once-Read-Many (WORM) semantics.
- **`+i` (Immutable)**: Disallows all writes, truncations, renames, and deletions—even by root!
- **`+a` (Append-Only)**: Permits appending new data (e.g. system logs) while strictly forbidding truncation or deletion.

In this lab, you simulate this kernel VFS enforcement layer in pure Python.

---

## 2. Python Concepts for Beginners

### A. Python Integer Bitmasks (`enum.IntFlag`)
`IntFlag` allows bitwise operations (`|`, `&`, `~`) between symbolic enumeration members:
```python
import enum

class InodeFlag(enum.IntFlag):
    IMMUTABLE = 0x00000010
    APPEND = 0x00000020

# Combine flags
active_flags = InodeFlag.IMMUTABLE | InodeFlag.APPEND
# Check if bit is set
if active_flags & InodeFlag.IMMUTABLE:
    print("File is immutable")
```

### B. Mutable Byte Buffers (`bytearray`)
Unlike Python's immutable `bytes`, a `bytearray` can be extended and modified in-place:
```python
buffer = bytearray(b"Initial")
buffer.extend(b" appended data")
```

### C. Bitwise Clearing with Bitwise NOT (`~`)
Clear a specific flag by bitwise ANDing with the bitwise NOT of the target flag:
```python
flags = flags & ~InodeFlag.IMMUTABLE
```

---

## 3. Step-by-Step Code Walkthrough

1. **`InodeFlag` Enum**: Maps the ext4 `i_flags` bitmasks (`IMMUTABLE = 0x10`, `APPEND = 0x20`, `NODUMP = 0x40`).
2. **`SimulatedExt4Inode` Dataclass**: Models the physical on-disk inode fields: `inode_num`, `uid`, `gid`, `size`, `flags`, `content`.
3. **`VFSInodeManager`**:
   - `chattr()`: Simulates `FS_IOC_SETFLAGS`. Validates that the caller holds `CAP_LINUX_IMMUTABLE` before mutating protected flags.
   - `vfs_write()`:
     - Rejects all writes if `IMMUTABLE` is set.
     - Rejects non-append writes if `APPEND` is set.
   - `vfs_unlink()`: Rejects file deletion if either `IMMUTABLE` or `APPEND` is active.
4. **`main()` Test Suite**: Validates normal writes, capability protection on `chattr`, root write rejection on immutable files, root deletion rejection, and append-only truncation blocks.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-55/ext4_inode_flags_simulator.py
```

Expected output:
```text
=== Day 55: ext4 Inode Immutable & Append-Only Flags Simulator ===
[*] Test 1 Passed: Initial write successful: Successfully wrote 18 bytes (New size: 18)
[*] Test 2 Passed: Unprivileged chattr rejected: Operation not permitted: CAP_LINUX_IMMUTABLE required
[*] Test 3 Passed: Applied IMMUTABLE flag (+i): Updated flags: 0x00000010
[*] Test 4 Passed: Root write blocked by IMMUTABLE flag: EPERM (Operation not permitted): Inode is IMMUTABLE (+i)
[*] Test 5 Passed: Root deletion blocked by IMMUTABLE flag: EPERM: Cannot delete IMMUTABLE (+i) file
[*] Test 6 Passed: Append-only mode permits appending while rejecting truncation: Successfully wrote 16 bytes (New size: 34)
All ext4 Inode Flags Simulator assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **`TypeError: unsupported operand type(s) for &: 'int' and 'NoneType'`**: Ensure `flags` are initialized with non-null values (e.g. `InodeFlag(0)`).
- **Mutable Default Arguments**: When declaring a dataclass field with a mutable default like `bytearray`, always use `field(default_factory=bytearray)`.

---

## 6. Beginner Exercises & Challenges

1. **Implement `NODUMP` (+d) Verification**: Add a backup simulation method that skips archiving any inode possessing the `NODUMP` flag.
2. **Support `NOATIME` (+A) Flag**: Track an `atime` timestamp in `SimulatedExt4Inode` and update it on read operations *unless* `NOATIME` is set.
3. **Recursive Directory Immutability**: Implement a helper function that applies `IMMUTABLE` recursively across an entire directory tree.
