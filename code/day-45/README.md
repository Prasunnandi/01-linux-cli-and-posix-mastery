# Day 45: Crontab 5-Field Lexical Parser & Bitmask Matcher

## 1. What Are We Building & Why Does It Matter?
The UNIX `crontab` format is the most famous task-scheduling grammar in computer science history:
```text
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (0=Sun)
* * * * * command to execute
```
It supports complex syntax rules: wildcards (`*`), lists (`1,15,30`), ranges (`1-5`), and step intervals (`*/15`).
Furthermore, POSIX cron has a subtle, notorious edge case: if **both** Day-of-Month and Day-of-Week are specified as non-wildcard values, they are combined with an **OR** (disjunction) rather than an AND!

In this lab, we build a **Complete 5-Field Crontab Parser and Evaluator** in pure Python that models all syntax forms and POSIX edge cases.

---

## 2. Python Concepts for Beginners

### A. String Slicing and Splitting
When parsing multi-token inputs:
- `.split()` splits on arbitrary whitespace into 5 discrete string tokens.
- `part.split('-', 1)` splits on the dash, isolating range boundaries (`1` and `5`).

### B. Python `range()` Step Increments
Python's built-in `range(start, stop, step)` generates sequences matching cron step intervals:
```python
range(0, 60, 15)  # Yields 0, 15, 30, 45
```

### C. Sets for Fast Collection Unions
When a crontab field contains comma-separated values (`1-5,10,20-25`), we parse each chunk and merge them into a single set using `.update()`:
```python
matching_minutes = set()
matching_minutes.update(range(1, 6))
matching_minutes.add(10)
```

---

## 3. Step-by-Step Code Walkthrough

1. **`ParsedCronSchedule`**: Stores sets of permissible values for minutes, hours, days, months, and days-of-week.
2. **`matches()` Method**: Implements the matching logic, including the POSIX Disjunction rule when both DoM and DoW are non-wildcard.
3. **`parse_field()`**: The core tokenizer: recursively resolves commas, steps (`/`), ranges (`-`), and wildcards (`*`) into integer sets.
4. **`main()` Function**: Tests standard stepped expressions (`*/15 2 * * 1-5`) and validates the POSIX Disjunction rule.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-45/crontab_expression_evaluator.py
```

Expected output:
```text
====================================================
DAY 45: CRONTAB 5-FIELD LEXICAL PARSER & MATCHER
====================================================
Parsed Expression: '*/15 2 * * 1-5'
  Minutes : [0, 15, 30, 45]
  Hours   : [2]
  DoWs    : [1, 2, 3, 4, 5]

1. Test 02:15 Wednesday -> [MATCHED]
2. Test 02:10 Wednesday -> [SKIPPED] (Correct)
3. Test POSIX Disjunction (DoM=18, Monday) -> [MATCHED] (OR Rule verified)

[VERIFIED] Crontab lexical parser passed all RFC/POSIX test cases!
```

---

## 5. Common Python Errors & Troubleshooting

- **`ValueError: invalid literal for int() with base 10`**: Occurs if month names (`JAN`, `FEB`) or weekday names (`MON`, `TUE`) are parsed without a name-to-integer mapping table.
- **Day of Week Numbering**: In POSIX, Sunday can be represented as `0` or `7`. Our code standardizes to `0`.

---

## 6. Beginner Exercises & Challenges

1. **Named Aliases**: Add support for month abbreviations (`JAN`-`DEC`) and weekday abbreviations (`MON`-`SUN`).
2. **Special Cron Macros**: Implement shorthand macros like `@hourly` (`0 * * * *`), `@daily` (`0 0 * * *`), and `@reboot`.
3. **Next Execution Predictor**: Write a function that takes a current datetime and finds the exact next minute when the cron expression will fire.
