# Day 02 Lab: Building `cat` and `wc` from Scratch in Python

> **Welcome to Day 2!** Today we build two of the most famous Linux command-line tools completely from scratch using Python: `cat` (concatenate and print files) and `wc` (word, line, and byte counter).

---

## 🎯 What Do These Scripts Do?

1. **`my_cat.py`**: Reads one or more files (or reads from your keyboard if no file is given) and streams the text directly to your screen, one line at a time, without eating up all your computer's RAM.
2. **`my_wc.py`**: Analyzes a file or stream and counts:
   - **Lines**: How many newline breaks (`\n`) exist.
   - **Words**: How many distinct words are separated by spaces.
   - **Characters/Bytes**: How many total characters exist.

---

## 🚀 How to Run the Code

### 1. Running `my_cat.py`
To print any file to your terminal screen:
```bash
python my_cat.py my_cat.py
```
You can even pass multiple files at once:
```bash
python my_cat.py file1.txt file2.txt
```

### 2. Running `my_wc.py`
To count the lines, words, and characters of a file:
```bash
python my_wc.py my_cat.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. `sys.argv` (Command Line Arguments)
* In Python, `sys.argv` is a **list of words** typed into the terminal.
* When you run `python my_cat.py notes.txt`:
  - `sys.argv[0]` is `"my_cat.py"` (the script name).
  - `sys.argv[1]` is `"notes.txt"` (the first argument).
  - `sys.argv[1:]` slices the list to get all arguments after the script name.

### 2. The `with open(...) as f:` Pattern
* In Python, opening a file like this is considered best practice:
  ```python
  with open("file.txt", "r", encoding="utf-8") as f:
      for line in f:
          print(line)
  ```
* **Why?** The `with` statement ensures that Python **automatically closes the file** when finished, even if the program encounters an error!

### 3. Streaming with `for line in f:`
* Beginners often try to read an entire file with `f.read()`.
* **Danger**: If the file is 50 Gigabytes, `f.read()` will crash your computer by consuming all your RAM!
* Using `for line in f:` is a **streaming iterator**: it only holds one line in memory at any given millisecond.

### 4. String Splitting: `line.split()`
* `line.split()` splits a sentence into a list of words by looking for spaces, tabs, and newlines.
* Example: `"Linux is awesome".split()` produces `['Linux', 'is', 'awesome']`.
* `len(line.split())` gives the count of words (3)!

### 5. Number Formatting: `{lines:8d}`
* In Python f-strings, `:8d` means: *"Format this integer using at least 8 spaces of width"*.
* This ensures that columns of numbers line up in neat tables, just like real Linux commands!

---

## 🔍 Code Walkthrough: `my_wc.py`

```python
import sys

def count_stream(stream):
    lines = 0
    words = 0
    chars = 0
    
    # 1. Loop through each line in the stream
    for line in stream:
        lines += 1                # Increment line count by 1
        chars += len(line)        # Add number of characters in this line
        words += len(line.split())# Add number of words in this line
        
    return lines, words, chars

def run_wc(file_paths):
    # 2. If no files were given on command line, read from stdin (keyboard/pipe)
    if not file_paths:
        lines, words, chars = count_stream(sys.stdin)
        print(f"{lines:8d} {words:8d} {chars:8d}")
        return

    # 3. Otherwise, open and count each file one by one
    for path in file_paths:
        with open(path, "r", encoding="utf-8") as f:
            lines, words, chars = count_stream(f)
            print(f"{lines:8d} {words:8d} {chars:8d} {path}")
```

---

## 📋 Expected Terminal Output
When you run `python my_wc.py my_cat.py`, you will see:
```text
      35       98     1124 my_cat.py
```
*(35 lines, 98 words, 1,124 characters)*

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Run `python my_cat.py` without any file arguments. Type a sentence and hit Enter. Notice how it echoes your line back! (Press `Ctrl+C` to stop).
2. **Challenge 2**: In `my_wc.py`, add a `-l` flag so that if a user runs `python my_wc.py -l my_cat.py`, it only prints the line count and hides words and characters!
