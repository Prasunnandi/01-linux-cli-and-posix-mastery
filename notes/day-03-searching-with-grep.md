# 🔍 Day 3: Searching Text with `grep` & Regular Expressions

> **Zero External Dependency Rule**: Everything you need to master this topic is contained right here in this document. You do NOT need to visit any external website or search Google.

---

## 1. The Core Problem: Why Do We Need `grep`?

In production software engineering, servers generate gigabytes of log files every single hour.
When a customer complains: *"My payment failed 5 minutes ago!"*, you cannot open a 500-Megabyte log file in Notepad or VS Code—the editor will freeze and crash.

You need a tool that can scan 10,000,000 lines of text in milliseconds, find only the lines that match a specific pattern, and print them out instantly.

That tool is **`grep`**.

---

## 2. What Does `grep` Mean?

The name comes from the classic Unix text editor **`ed`**.
In `ed`, to search an entire file and print matching lines, users typed:

$$\mathbf{g} / \text{re} / \mathbf{p}$$

* **`g`** = **Global** (search the whole document from top to bottom)
* **`re`** = **Regular Expression** (the pattern you are looking for)
* **`p`** = **Print** (display the matching lines on the screen)

Put them together and you get: **`g-re-p`** $\rightarrow$ **`grep`**!

---

## 3. Real-World Analogy: The Detective's Filter

```
       500,000 SERVER LOG LINES
                  │
                  ▼
         ┌───────────────────┐
         │ grep -i "failed"  │  ◄── The Detective's Sieve
         └───────────────────┘
                  │
                  ▼
         3 MATCHING LINES ONLY
  [2026-11-23 08:14:02 ERROR: Payment failed for user 402]
  [2026-11-23 08:14:05 ERROR: Retrying payment failed: timeout]
  [2026-11-23 08:14:10 CRITICAL: Transaction aborted]
```

Without `grep`, finding these 3 lines would take 4 hours of manual scrolling. With `grep`, it takes 0.04 seconds.

---

## 4. The 5 Essential `grep` Flags (Production Superpowers)

Every software engineer and data analyst must know these 5 flags by heart:

| Flag | Name | What it Does in Plain English | Production Command Example |
| :---: | :--- | :--- | :--- |
| **`-i`** | Ignore Case | Treats uppercase and lowercase identically. Matches `error`, `Error`, `ERROR`. | `grep -i "error" app.log` |
| **`-n`** | Line Number | Tells you the exact line number inside the file where the match was found. | `grep -n "password" settings.py` |
| **`-v`** | Invert Match | **Excludes** matching lines! Shows every line that does **NOT** match the pattern. | `grep -v "DEBUG" app.log` |
| **`-c`** | Count | Instead of printing thousands of lines, it just returns a single number: how many lines matched. | `grep -c "404" access.log` |
| **`-r` / `-R`** | Recursive | Searches inside every file and subfolder inside a directory. | `grep -rn "TODO" src/` |

---

## 5. Regular Expressions (RegEx) Basics from Scratch

A **Regular Expression** is a mathematical formula for matching text patterns rather than exact words.

### The 4 Core Metacharacters:

### 1. `^` (Caret) — Start of Line Anchor
* Means: *"The line MUST start with this word."*
* Example: `^ERROR` matches lines that begin with `ERROR`. It will **NOT** match `[INFO] Server ERROR`.

### 2. `$` (Dollar) — End of Line Anchor
* Means: *"The line MUST end with this word."*
* Example: `timeout$` matches lines that end with `timeout`.

### 3. `.` (Dot) — The Wildcard
* Means: *"Any single character goes here."*
* Example: `c.t` matches `cat`, `cot`, `cut`, `c9t`, `c#t`.

### 4. `[ ]` (Character Class / Set)
* Means: *"Match any ONE character inside these brackets."*
* Example: `[0-9]` matches any digit (0, 1, 2... 9).
* Example: `[A-Z]` matches any uppercase letter.

```
Pattern: ^[0-9]
Matches: "1st place winner" (Starts with a number)
Rejects: "Winner: 1st place" (Does NOT start with a number)
```

---

## 6. Common Freshers' Pitfalls & Traps

> [!WARNING]
> **The Secret Dot Trap**:
> In regular expressions, a dot (`.`) means **"ANY character"**, not a literal period!  
> If you search `grep "192.168.1.1"` without escaping, the dots will match *any* character, matching `192X168Y1Z1`!  
> To search for a literal period, put a backslash in front: `grep "192\.168\.1\.1"`.

---

## 7. Complete Self-Contained Q&A

**Q1: How do you search for all lines that do NOT contain the word "DEBUG"?**  
**Answer**: Use the `-v` (invert match) flag: `grep -v "DEBUG" server.log`.

**Q2: What is the difference between `grep "error"` and `grep -i "error"`?**  
**Answer**: `grep "error"` is case-sensitive and will miss `Error` or `ERROR`. `grep -i "error"` ignores case and matches all variations.

**Q3: How do you search all files in the current folder and subfolders for the word "API_KEY"?**  
**Answer**: Use recursive search with line numbers: `grep -rn "API_KEY" .`.

---

## 8. Hands-on Lab Verification

Run your custom `my_grep.py` implementation in `code/day-03/`:
```bash
# Search with line numbers
python code/day-03/my_grep.py -n "Standard" notes/day-01-streams-and-redirection.md

# Search case-insensitive
python code/day-03/my_grep.py -i "descriptor" notes/day-01-streams-and-redirection.md

# Invert match (show lines without the word 'the')
python code/day-03/my_grep.py -v "the" notes/day-01-streams-and-redirection.md
```
Everything executes locally with zero external requirements!
