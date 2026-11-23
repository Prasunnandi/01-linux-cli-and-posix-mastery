# Day 05 Lab: Linux File Permission & Octal Calculator

> **Welcome to Day 5!** Today we demystify Linux file permissions (`rwxr-xr--`) and the famous numeric codes like `755` and `644`. In this lab, you will learn how Python uses bitwise math to translate between human-readable permission symbols and binary octal numbers.

---

## 🎯 What Does This Lab Do?
In Linux, every file has three sets of permissions:
1. **User (Owner)**: What you can do.
2. **Group**: What teammates in your project group can do.
3. **Others (World)**: What anyone else on the system can do.

Each entity has three rights, represented by powers of 2:
* **Read (`r`)** = 4 (binary `100`)
* **Write (`w`)** = 2 (binary `010`)
* **Execute (`x`)** = 1 (binary `001`)

Adding them up gives an octal digit between `0` and `7`:
* `r + w + x` = $4 + 2 + 1 = 7$ (Full permissions)
* `r + x` = $4 + 0 + 1 = 5$ (Read and Execute, no write)
* `r` = $4 + 0 + 0 = 4$ (Read only)

`permission_calculator.py` bidirectionally converts between strings like `rwxr-xr-x` and numbers like `755`!

---

## 🚀 How to Run the Code
Run the interactive script in your terminal:
```bash
python permission_calculator.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. Bitwise AND Operator (`&`)
* In computers, numbers are stored as binary bits (`0`s and `1`s).
* The number `5` in binary is `101`:
  - Bit 2 (value 4) is `1` (Read allowed)
  - Bit 1 (value 2) is `0` (Write forbidden)
  - Bit 0 (value 1) is `1` (Execute allowed)
* In Python, `d & 4` checks if the 4-bit is turned ON. If it is non-zero, Python knows `r` should be granted!

### 2. String Slicing: `str[start:end]`
* Python lets you grab substrings easily:
  - `perm_str[0:3]`: Grabs characters at index 0, 1, 2 (the User permissions, e.g. `'rwx'`).
  - `perm_str[3:6]`: Grabs index 3, 4, 5 (the Group permissions).
  - `perm_str[6:9]`: Grabs index 6, 7, 8 (the Others permissions).

### 3. Raising Errors with `raise ValueError(...)`
* If a user types something invalid (like 10 letters instead of 9), the program raises a `ValueError`. This stops bad data from corrupting the calculations.

---

## 🔍 Code Walkthrough

```python
def parse_symbolic(perm_str):
    # 1. Helper function to turn a 3-character chunk like 'r-x' into a digit
    def chunk_to_digit(chunk):
        val = 0
        if chunk[0] == 'r': val += 4
        if chunk[1] == 'w': val += 2
        if chunk[2] == 'x': val += 1
        return str(val)

    # 2. Slice into User, Group, and Others
    u = chunk_to_digit(perm_str[0:3]) # e.g. 'rwx' -> '7'
    g = chunk_to_digit(perm_str[3:6]) # e.g. 'r-x' -> '5'
    o = chunk_to_digit(perm_str[6:9]) # e.g. 'r-x' -> '5'
    
    return u + g + o  # Returns '755'
```

---

## 📋 Expected Terminal Output
```text
==================================================
   DAY 5 LAB: LINUX PERMISSION CALCULATOR         
==================================================
Example 1: Translating 'rwxr-xr-x' -> Octal: 755
Example 2: Translating 'rw-r--r--' -> Octal: 644
Example 3: Translating '700'       -> Symbolic: rwx------
==================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: What is the symbolic permission string for `chmod 777 script.sh`? Run `permission_calculator.py` to verify!
2. **Challenge 2**: What numeric octal corresponds to `rw-rw-r--`? Calculate it on paper first ($4+2=6, 4+2=6, 4=4 \rightarrow 664$), then verify with the script!
