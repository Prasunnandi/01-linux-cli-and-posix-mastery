# Day 47: RFC 5424 Syslog Protocol & Logrotate Inode Simulator

## 1. What Are We Building & Why Does It Matter?
For decades, UNIX systems distributed log messages across files and networks using the **Syslog Protocol (RFC 5424)**.
Every syslog event has a calculated Priority integer (`PRI = Facility * 8 + Severity`).
Furthermore, handling log files on disk requires understanding **Inode Lifecycles**:
- If you simply run `mv app.log app.log.1`, a running daemon continues writing to `app.log.1` because the underlying inode never changed!
- `logrotate` handles this via **SIGHUP signaling** (clean inode swap) or **`copytruncate`** (copying and wiping in-place).
- However, `copytruncate` has a dangerous **Race Condition**: any logs written between the copy and the wipe are permanently destroyed!

In this lab, we build an **RFC 5424 Wire Formatter and Logrotate Inode Simulator** in pure Python that models priority calculations, inode transitions, and copytruncate data loss.

---

## 2. Python Concepts for Beginners

### A. Mathematical Bitfield Equations
In syslog, `PRI` combines two integers:
```python
pri = (facility_number * 8) + severity_number
```
Because $8 = 2^3$, multiplying by 8 is equivalent to a 3-bit left shift `facility << 3`.

### B. Python `bytearray` for Mutable File Buffers
To model file disk writes and truncation:
- `.extend()` appends bytes to the end of the file.
- `.clear()` truncates the file back to 0 bytes, exactly like the Linux `truncate()` system call.

### C. Dictionaries for Lookups
We map text strings like `"auth"` and `"crit"` to standard RFC integer constants using dictionary lookups with fallback defaults (`dict.get(key, default)`).

---

## 3. Step-by-Step Code Walkthrough

1. **`SyslogRFC5424`**: Computes standard PRI integers and formats compliant RFC 5424 wire strings (`<PRI>VERSION TIMESTAMP HOSTNAME...`).
2. **`SimulatedFileInode`**: Models a Linux filesystem inode holding an identifier and raw byte buffer.
3. **`rotate_sighup()`**: Simulates standard rotation: renames the old file and allocates a brand new inode, modeling the daemon's SIGHUP re-open behavior.
4. **`rotate_copytruncate()`**: Simulates copytruncate: copies the bytes and wipes the buffer, capturing any mid-race bytes that get permanently lost.
5. **`main()` Function**: Executes automated tests verifying PRI values, inode switches, and copytruncate data loss.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-47/syslog_rfc5424_and_rotator.py
```

Expected output:
```text
====================================================
DAY 47: RFC 5424 SYSLOG & LOGROTATE SIMULATOR
====================================================
1. RFC 5424 PRI Calculation: auth.crit -> PRI=34 (Correct)
   Formatted Wire Message:
   <34>1 2026-11-27T02:00:00.000Z server01 sshd 1234 ID42 - Invalid password attempt

2. Executing SIGHUP Rotation...
   [PASS] Active Inode changed from 1000 to 1001. Zero data loss.

3. Demonstrating Copytruncate Race Condition...
   Bytes lost during copytruncate window: 25 bytes!
   [PASS] Copytruncate race condition data-loss mathematically verified!

[VERIFIED] Syslog and Logrotate simulation passed all tests with 100% fidelity!
```

---

## 5. Common Python Errors & Troubleshooting

- **`KeyError` in Dictionaries**: Always normalize input strings to lowercase (`facility.lower()`) before looking up in `FACILITY_MAP`.
- **String vs Bytes in File Buffers**: `bytearray.extend()` requires raw `bytes`, not Python strings. Always call `.encode('utf-8')`.

---

## 6. Beginner Exercises & Challenges

1. **RFC 5424 Parser**: Write a function `parse_syslog_message(msg)` that extracts the PRI, facility name, severity name, and text message from a formatted string.
2. **Compress Rotated Files**: Add a simulated `gzip` step in `rotate_sighup()` that compresses the archive into a mock `.gz` file.
3. **Logrotate Age Expiration**: Add a `max_retention_days = 7` limit that automatically purges archives older than 7 cycles.
