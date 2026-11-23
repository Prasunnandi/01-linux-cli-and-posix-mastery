# Day 03 Lab: Building `grep` from Scratch in Python

> **Welcome to Day 3!** Today we build a clone of the legendary Linux command `grep` (Global Regular Expression Print). In this lab, you will learn how computers search through millions of lines of text to find patterns in milliseconds.

---

## 🎯 What Does `my_grep.py` Do?
`my_grep.py` scans lines of text from files or standard input and prints only the lines that match a specific word or regular expression pattern.

It supports three powerful command-line flags:
* **`-i` (Ignore Case)**: Finds matches regardless of UPPERCASE or lowercase (e.g. finds `error`, `Error`, and `ERROR`).
* **`-n` (Line Numbers)**: Shows the exact line number where the match was found.
* **`-v` (Invert Match)**: Inverts the filter, printing only the lines that **do NOT** contain the search word!

---

## 🚀 How to Run the Code

### 1. Basic Search
Search for the word `"import"` inside `my_grep.py`:
```bash
python my_grep.py import my_grep.py
```

### 2. Case-Insensitive Search with Line Numbers (`-i -n`)
Find the word `"python"` regardless of capitalization, showing line numbers:
```bash
python my_grep.py -i -n python my_grep.py
```

### 3. Inverting the Search (`-v`)
Print every line that is **NOT** a comment (lines that don't start with `#`):
```bash
python my_grep.py -v "#" my_grep.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. `import re` (The Regular Expressions Library)
* `re` is Python's built-in regular expression engine.
* It allows you to search not just for exact words, but for dynamic patterns (like email addresses, phone numbers, or dates).
* Key function: `re.search(pattern, line)`
  - Returns a match object if the pattern exists inside the line.
  - Returns `None` if the pattern is not found.

### 2. Booleans & Flags (`True` / `False`)
* We use simple True/False variables to remember what options the user selected:
  ```python
  ignore_case = False
  show_line_nums = False
  invert_match = False
  ```
* When the script sees `"-i"` in the terminal arguments, it sets `ignore_case = True`.

### 3. Compiling Regex Patterns: `re.compile()`
* Instead of re-evaluating the search string on every single line of a 100,000-line file, `re.compile()` translates your search pattern into optimized machine instructions ahead of time:
  ```python
  regex = re.compile(pattern_str, flags=re.IGNORECASE if ignore_case else 0)
  ```

### 4. Enumerating Lines: `enumerate(stream, start=1)`
* In Python, `enumerate()` gives you both the **line number** and the **line content** together!
  ```python
  for line_num, line in enumerate(f, start=1):
      # line_num is 1, 2, 3...
  ```

---

## 🔍 Code Walkthrough

```python
import sys
import re

def search_stream(stream, regex, show_line_nums, invert_match, filename=""):
    for line_num, line in enumerate(stream, start=1):
        # 1. Does this line match our pattern?
        matched = bool(regex.search(line))
        
        # 2. Check if this line should be printed (handles -v invert matching)
        should_print = (matched and not invert_match) or (not matched and invert_match)

        # 3. Print the line with formatting
        if should_print:
            prefix = ""
            if filename:
                prefix += f"{filename}:"
            if show_line_nums:
                prefix += f"{line_num}:"
            sys.stdout.write(f"{prefix}{line}")
```

---

## 📋 Expected Terminal Output
When you run `python my_grep.py -n import my_grep.py`, you will see:
```text
6:import sys
7:import re
```
*(Lines 6 and 7 of `my_grep.py` contain the word `import`!)*

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Run `python my_grep.py "def " my_grep.py` to quickly list every function defined in the script!
2. **Challenge 2**: Try searching across multiple files at the same time:
   `python my_grep.py "sys" my_grep.py ../day-02/my_cat.py`
