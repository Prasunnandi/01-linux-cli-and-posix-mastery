# Day 06 Lab: Advanced Text Wrangling & Log Analysis in Python

> **Welcome to Day 6!** Today we learn how data engineers and systems administrators parse massive web server logs using Python to calculate bandwidth, detect cyber-attacks, and find 404 errors, mirroring the classic Unix tools `awk`, `sed`, and `cut`.

---

## 🎯 What Does This Lab Do?
Imagine a website like YouTube or Netflix generating 50 Gigabytes of access logs every hour. Each line represents one user clicking a link or video:
```text
192.168.1.10 - - [23/Nov/2026:08:00:01] "GET /index.html HTTP/1.1" 200 4520 12
```

`log_wrangler.py` simulates how the Unix tool `awk` slices this log into columns, checks if the HTTP status was successful (`200 OK`), and sums up the total megabytes of data transferred across the network!

---

## 🚀 How to Run the Code
Run the script in your terminal:
```bash
python log_wrangler.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. Splitting Text by Columns: `line.split()`
* By default, `line.split()` breaks a sentence at every space or tab.
* In a web server log:
  - `parts[0]` = Client IP Address (e.g. `'192.168.1.10'`)
  - `parts[6]` = URL requested (e.g. `'/index.html'`)
  - `parts[8]` = HTTP Status Code (e.g. `'200'`)
  - `parts[9]` = Bytes transferred (e.g. `'4520'`)

### 2. Converting Strings to Numbers: `int(...)`
* When reading from a log, `'4520'` is treated as text (a string).
* You cannot do math on strings! Calling `int(parts[9])` converts it into a real mathematical number that Python can add, subtract, and multiply.

### 3. Running Accumulators (`+=`)
* `total_bytes += bytes_sent` is shorthand for:
  `total_bytes = total_bytes + bytes_sent`
* It keeps a running total across thousands of lines.

### 4. Alignment in F-Strings: `{val:<15}`
* `f"{ip:<15}"` tells Python: *"Print the IP address and pad it with spaces so it takes up exactly 15 characters, left-aligned."*
* This makes terminal output look like a clean, beautiful spreadsheet!

---

## 🔍 Code Walkthrough

```python
def simulate_awk_aggregation(logs):
    lines = logs.strip().split("\n")
    total_bytes = 0
    success_requests = 0

    for line in lines:
        parts = line.split()
        if len(parts) < 11:
            continue # Skip malformed lines

        status = parts[8]
        bytes_sent = int(parts[9])
        url = parts[6]

        # Like AWK: if status is 200 (Success), aggregate!
        if status == "200":
            total_bytes += bytes_sent
            success_requests += 1
            print(f"{parts[0]:<15} {status:<8} {bytes_sent:<12} {url}")

    # END block: Print summary report
    print(f"Total Successful 200 Requests : {success_requests}")
    print(f"Total HTTP Bandwidth          : {total_bytes / (1024 * 1024):.2f} MB")
```

---

## 📋 Expected Terminal Output
```text
==================================================
   DAY 6 LAB: AWK / SED LOG WRANGLING SIMULATION  
==================================================
Simulating AWK command:
  awk '$9 == 200 { bytes += $10; reqs++ } END { ... }'

IP Address      Status   Bytes Sent   URL
-------------------------------------------------------
192.168.1.10    200      4520         /index.html
192.168.1.10    200      18450        /images/logo.png
10.0.50.2       200      10485760     /video/intro.mp4
10.0.50.2       200      20971520     /video/demo.mp4
192.168.1.10    200      840          /api/user

--- AWK END { ... } SUMMARY REPORT ---
Total Successful 200 Requests : 5
Total HTTP Bandwidth          : 30.02 MB
Video (MP4) Bandwidth         : 30.00 MB
==================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Modify `log_wrangler.py` to count how many `404` (Page Not Found) requests occurred.
2. **Challenge 2**: Calculate which IP address consumed the most total bandwidth!
