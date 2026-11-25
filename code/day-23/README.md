# Hands-On Lab: Day 23 - Parameter Expansion Engine (`param_expansion_engine.py`)

## 1. What Are We Building & Why Does It Matter?
In shell scripting, using external programs like `basename`, `dirname`, and `sed` inside loops is thousands of times slower than using native shell parameter expansions.
Bash performs expansions like `${VAR##*/}` (longest prefix strip) and `${VAR%/*}` (shortest suffix strip) directly inside memory without spawning a single subshell.

In this lab, we build `param_expansion_engine.py` to recreate these fundamental string transformations using pure Python string slicing.

---

## 2. Python Concepts for Beginners
1. **String Slicing (`string[start:end]`)**:
   - `val[:idx]` extracts characters from the start up to index `idx`.
   - `val[idx:]` extracts characters from index `idx` to the end.
2. **`str.rfind(sub)`**:
   - Searches from right to left to find the last occurrence of a character (e.g. finding the last `/` in a file path). Returns `-1` if not found.
3. **`str.replace(old, new)`**:
   - Replaces all occurrences of a substring.

---

## 3. Step-by-Step Code Walkthrough

```python
def strip_longest_prefix(val: str, delim: str) -> str:
    idx = val.rfind(delim)
    return val[idx + len(delim):] if idx != -1 else val
```
- In `/var/log/nginx/access.log`, `val.rfind("/")` locates the last slash at index 14.
- `val[15:]` slices everything after the last slash, cleanly returning `"access.log"` in $O(N)$ time with zero external forks.

---

## 4. How to Run the Script

```bash
cd code/day-23
python param_expansion_engine.py
```

### Expected Output
```
====================================================
BASH IN-MEMORY PARAMETER EXPANSION ENGINE
====================================================
Original Path : /var/log/nginx/access.2026.log.gz
  ${VAR##*/}   -> Basename   : access.2026.log.gz
  ${VAR%/*}    -> Dirname    : /var/log/nginx
  ${VAR//./_}  -> Replaced   : access_2026_log_gz
  ${VAR:-def}  -> Fallback   : fallback_service

[SUCCESS] In-memory expansions verified 100% correct!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`IndexError: string index out of range`**:
   - Slicing `string[start:end]` in Python never raises an `IndexError` even if indices are out of bounds (it returns `""`). However, direct index lookup `string[i]` will crash if `i >= len(string)`.
2. **`AttributeError: 'NoneType' object has no attribute 'rfind'`**:
   - Ensure the path variable is a valid string, not `None`. Use `val = val or ""` to provide a safe default.
3. **Case Sensitivity**:
   - `str.replace()` is case-sensitive by default. Replacing `'.LOG'` will not match `'.log'`.

---

## 6. Beginner Exercises & Challenges
1. **Implement Substring Replacement (`${var//pattern/replace}`)**:
   - Extend `param_expansion_engine.py` to support global pattern replacement `${var//foo/bar}`. Use Python's `re.sub()` to perform the substitution.
2. **Case Conversion (`${var^^}` and `${var,,}`)**:
   - Add support for Bash 4+ case modification syntax: `${var^^}` converts to UPPERCASE, and `${var,,}` converts to lowercase.
3. **Array Slicing Expansion (`${arr[@]:start:length}`)**:
   - Add support for indexing arrays with parameter expansion syntax. Test with `${FILES[@]:1:2}`.
