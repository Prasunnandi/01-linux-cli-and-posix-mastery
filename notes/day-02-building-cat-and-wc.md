# 🐱 Day 2: Building `cat` & `wc` (Word Count) from Scratch

> **Zero External Dependency Rule**: Everything you need to master this topic is contained right here in this document. You do NOT need to visit any external website or search Google.

---

## 1. The Core Problem: How Do Programs Read Gigabytes of Data?

Imagine you have a log file that is **10 Gigabytes** in size. Your computer has **8 Gigabytes** of RAM (memory).
* If your program tries to load the entire file into memory with `f.read()`, your computer will instantly freeze and crash with an **`Out of Memory (OOM) Error`**!
* How do production systems and Unix utilities like `cat` and `wc` read 100-Gigabyte files in seconds using only **3 Megabytes of RAM**?

The secret is **Chunked Streaming & Buffer Memory**.

---

## 2. Real-World Analogy: Drinking with a Straw vs Swallowing the Whole Cup

```
  [ THE BAD WAY: SWALLOWING THE BUCKET ]          [ THE PRODUCTION WAY: THE STRAW ]
  
         ┌───────────────┐                             ┌───────────────┐
         │ 10 GB FILE    │                             │ 10 GB FILE    │
         └───────┬───────┘                             └───────┬───────┘
                 │ (Try to load all 10GB)                      │ (Take 4KB sip)
                 ▼                                             ▼
         ┌───────────────┐                             ┌───────────────┐
         │ 8 GB RAM      │                             │ 4 KB BUFFER   │
         │   [CRASH!]    │                             └───────┬───────┘
         └───────────────┘                                     │ (Print / Process)
                                                               ▼
                                                       ┌───────────────┐
                                                       │ STDOUT SCREEN │
                                                       └───────────────┘
                                                        (Repeat until EOF!)
```

* **Swallowing the Bucket**: Trying to hold the entire file in RAM simultaneously.
* **The Straw (Buffering)**: Reading a small chunk (e.g. 4096 bytes / 4KB), processing it, discarding it, and repeating until the end of the file. You can process an infinite stream with tiny memory!

---

## 3. Deep-Dive: What is `cat` (Concatenate)?

The name `cat` is short for **Concatenate** (meaning to link things together in a chain).
Originally written by Ken Thompson and Dennis Ritchie at AT&T Bell Laboratories in 1971, `cat` has two main superpowers:
1. **Printing files**: If you give it one file, it streams it line-by-line to your screen (`cat file.txt`).
2. **Joining files**: If you give it multiple files, it concatenates them sequentially into a single stream:
   ```bash
   cat chapter1.txt chapter2.txt chapter3.txt > complete_book.txt
   ```

### How `cat` Works Internally (The Syscall Loop):
Under the hood in C/Linux, `cat` is an endless loop:
```
while ((bytes_read = read(fd, buffer, 4096)) > 0) {
    write(STDOUT_FILENO, buffer, bytes_read);
}
```
* `read()` returns the number of bytes read.
* When the end of the file is reached, `read()` returns **`0`** (called **EOF - End of File**), and the loop terminates cleanly.

---

## 4. Deep-Dive: What is `wc` (Word Count)?

`wc` counts three specific metrics across any text file:
1. **Lines (`-l`)**: Count of newline characters (`\n`).
2. **Words (`-w`)**: Count of words separated by whitespace (spaces, tabs, newlines).
3. **Bytes / Characters (`-c` / `-m`)**: Total byte size.

### The Standard `wc` Output Format:
When you run `wc report.txt`, it outputs three numbers followed by the filename:
```
      14      120      850 report.txt
       │        │        │
       ▼        ▼        ▼
     Lines    Words    Bytes
```

### The State Machine Inside `wc`:
How does a computer know what a "word" is without AI? It uses a simple **State Machine**:
* Maintain a flag: `in_word = False`
* Read character by character:
  * If the character is NOT a space, tab, or newline:
    * If `in_word == False`, we just entered a brand new word! Increment `word_count += 1`. Set `in_word = True`.
  * If the character IS a space, tab, or newline:
    * Set `in_word = False`.
  * If character == `'\n'`:
    * Increment `line_count += 1`.

```
Character:  'H'   'e'   'l'   'l'   'o'   ' '   'W'   'o'   'r'   'l'   'd'   '\n'
in_word  :   T     T     T     T     T     F     T     T     T     T     T     F
Word Count:  1 ───────────────────────────────► 2 ───────────────────────────────► Total: 2 Words, 1 Line!
```

---

## 5. Common Freshers' Pitfalls & Traps

> [!NOTE]
> **Why `wc -l` misses the last line if no newline exists**:
> In Unix, a line is strictly defined as: **"A sequence of characters terminated by a newline (`\n`)"**.  
> If the last line of a file does not have a newline at the end, standard `wc -l` will count $N-1$ lines! Always ensure files end with a clean newline.

---

## 6. Complete Self-Contained Q&A

**Q1: What does `cat` stand for and what was its original purpose?**  
**Answer**: `cat` stands for "Concatenate". Its original purpose was to take multiple files and chain them together sequentially into one single output stream.

**Q2: How does reading a file in 4KB chunks prevent Out of Memory errors?**  
**Answer**: By reusing a single 4096-byte memory buffer, the program only ever holds 4KB in RAM at any instant. After processing the chunk, the same buffer is overwritten with the next 4KB, allowing a machine with 512MB RAM to effortlessly process a 100GB file.

**Q3: In `wc`, what defines the boundary between two words?**  
**Answer**: Any whitespace character, which includes spaces (`' '`), tabs (`'\t'`), carriage returns (`'\r'`), and newlines (`'\n'`).

---

## 7. Hands-on Lab Verification

Run your custom implementations in `code/day-02/`:
```bash
# Test custom cat
python code/day-02/my_cat.py notes/day-01-streams-and-redirection.md

# Test custom wc
python code/day-02/my_wc.py notes/day-01-streams-and-redirection.md
```
Observe how the output matches the exact formatting of standard Linux utilities!
