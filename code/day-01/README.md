# Day 01 Lab: Understanding the 3 Standard Streams in Python

> **Welcome to Python!** If this is your very first time reading or running Python code, do not worry. This guide is written specifically for complete beginners and freshers. You don't need any prior programming background to understand this.

---

## 🎯 What Does This Lab Do?
In Day 1, we learned that every program in Linux has 3 standard channels (like 3 pipes connected to the program):
1. **`stdin` (Standard Input - File Descriptor 0)**: Where the program reads input (like what you type on the keyboard).
2. **`stdout` (Standard Output - File Descriptor 1)**: Where the program sends its normal, successful results.
3. **`stderr` (Standard Error - File Descriptor 2)**: Where the program sends error messages and warnings so they don't get mixed up with normal output.

The script `streams_demo.py` demonstrates how to write directly to these 3 channels and prove that `stdout` and `stderr` can be separated!

---

## 🚀 How to Run the Code
Open your terminal (PowerShell, Command Prompt, or Bash), navigate to this folder, and run:

```bash
python streams_demo.py
```

### Try Stream Redirection in your Terminal!
To see the real magic of separating output from errors, try running this command in your terminal:

```bash
# This saves normal output to 'output.log', while error warnings still appear on your screen!
python streams_demo.py > output.log
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

If you are new to Python, here are the exact building blocks used in `streams_demo.py`:

### 1. `import sys`
* **What it means**: In Python, `import` brings in extra toolboxes called "modules".
* The `sys` module gives us tools to talk directly to the operating system and manage `stdin`, `stdout`, and `stderr`.

### 2. `sys.stdout.write(...)` vs `print(...)`
* You might already know `print("Hello")`.
* In Python, `print()` is actually a wrapper around `sys.stdout.write()`. `print()` automatically adds a newline (`\n`) at the end, while `sys.stdout.write()` lets you control the exact raw bytes sent to the screen.

### 3. `sys.stdout.flush()`
* Operating systems often save text in a small memory holding area called a **buffer** before drawing it to the screen.
* Calling `.flush()` tells the computer: *"Do not wait! Push all buffered text to the screen immediately!"*

### 4. `try ... except EOFError:`
* Think of this like a safety net.
* `try:` tells Python to attempt reading keyboard input.
* If the script runs inside an automated test where nobody is typing at a keyboard, an `EOFError` (End Of File error) occurs. The `except EOFError:` block catches this gracefully and prevents the program from crashing.

### 5. `if __name__ == "__main__":`
* This is a standard Python convention.
* It simply means: *"If someone clicked run on this file directly, execute the `main()` function!"*

---

## 🔍 Line-by-Line Code Walkthrough

```python
# 1. We import the system module
import sys

def main():
    # 2. We print a welcome banner
    print("==================================================")
    print("  WELCOME TO DAY 1: THE 3 STANDARD STREAMS LAB!   ")
    print("==================================================")
    
    # 3. We send a message to STDOUT (Channel 1)
    sys.stdout.write("[SUCCESS] This message is sent to STDOUT (FD 1).\n")
    sys.stdout.flush()

    # 4. We send an alert to STDERR (Channel 2)
    sys.stderr.write("[WARNING] This message is sent to STDERR (FD 2)!\n")
    sys.stderr.flush()

    # 5. We ask for user input from STDIN (Channel 0)
    print("\n--- Interactive Input Test ---")
    print("Now type your name and press Enter (testing STDIN - FD 0):")
    try:
        user_input = sys.stdin.readline().strip()
        if user_input:
            print(f"Hello, {user_input}! We read your input directly from STDIN.")
        else:
            print("No input received (non-interactive mode). That's totally fine!")
    except EOFError:
        print("EOF reached. Stream closed gracefully.")

if __name__ == "__main__":
    main()
```

---

## 📋 Expected Terminal Output
When you run `python streams_demo.py`, you will see:
```text
==================================================
  WELCOME TO DAY 1: THE 3 STANDARD STREAMS LAB!   
==================================================
[SUCCESS] This message is sent to STDOUT (FD 1).
[WARNING] This message is sent to STDERR (FD 2)!

--- Interactive Input Test ---
Now type your name and press Enter (testing STDIN - FD 0):
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Open `streams_demo.py` in your editor and change the text in `sys.stderr.write()` to your own custom warning message. Run the script again to see your change.
2. **Challenge 2**: Run `python streams_demo.py 2> errors.log`. Notice that `[WARNING]` disappeared from your terminal and was saved into `errors.log`!
