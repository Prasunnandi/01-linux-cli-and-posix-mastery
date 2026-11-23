# Day 06: Stream Wrangling with `cut`, `awk`, and `sed`: Grammars, State Buffers & DSL Physics

> **Zero External Dependency Guarantee**: This document is an encyclopedic, self-contained masterclass. It contains complete historical origins, AWK language grammar and hash-table runtime internals, `sed` pattern/hold space state-machine mechanics, C-level string performance comparisons, production outage post-mortems, and FAANG staff-level interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & Historical Origins

In 1977, three titans of computer science at Bell Laboratories—Alfred Aho, Peter Weinberger, and Brian Kernighan—sought to create a programmable reporting tool capable of manipulating database records and text streams without writing verbose C programs. Combining their initials, they created **`awk`**.

Simultaneously, Lee E. McMahon created **`sed`** (Stream Editor) in 1974, adapting the line-editing command syntax of `ed` into a continuous streaming filter. Together with the simpler delimiter-slicing tool **`cut`**, these three utilities form the foundational text-processing triumvirate of POSIX systems.

```
STREAM PROCESSING TAXONOMY:
+-------------------+--------------------+--------------------+-----------------------+
| Utility           | Primary Paradigm   | Memory Footprint   | Best Suited For       |
+-------------------+--------------------+--------------------+-----------------------+
| `cut`             | Fixed Delimiter    | O(1) Streaming     | Fast column slicing   |
| `sed`             | Line State Machine | O(Line Length)     | Regex search/replace  |
| `awk`             | Turing-Complete DSL| O(Records/Hash)    | Arithmetic & analytics|
+-------------------+--------------------+--------------------+-----------------------+
```

---

## 2. Low-Level Mechanics of `cut`: Zero-Overhead Delimiter Slicing

The `cut` utility is optimized for speed. Unlike `awk`, which builds an Abstract Syntax Tree (AST) and evaluates field grammars, `cut` scans input buffers byte-by-byte, counting delimiter occurrences and writing target byte ranges directly to `stdout`.

### 2.1 The Two Processing Modes:
1. **Byte / Character Mode (`-b`, `-c`)**:
   Slices exact byte positions regardless of contents:
   ```bash
   # Extract the first 10 characters of every line:
   cut -c 1-10 /var/log/syslog
   ```
2. **Delimited Field Mode (`-d`, `-f`)**:
   Splits lines on a **single 1-byte delimiter** and extracts specified 1-based columns:
   ```bash
   # Extract usernames and login shells from /etc/passwd:
   cut -d ':' -f 1,7 /etc/passwd
   ```

### 2.2 Critical Limitations of `cut`:
* **Single-Byte Delimiter**: `cut -d '  '` (two spaces) or regular expressions are strictly forbidden.
* **No Field Reordering**: `cut -f 2,1` will still output field 1 followed by field 2!
* **No Delimiter Collapsing**: Multiple consecutive delimiters are treated as distinct empty fields. For whitespace-padded columns (e.g., `ps aux` or `df -h`), `cut` fails miserably—use `awk` instead!

---

## 3. The `awk` Programming Language & Runtime Architecture

`awk` is not merely a CLI utility; it is a full, Turing-complete domain-specific programming language with associative arrays, floating-point arithmetic, regular expression matching, and C-like control flow.

```
THE AWK EXECUTION LIFECYCLE:
+-------------------------------------------------------------------------+
|                              BEGIN { ... }                              |
|         Executed ONCE before any input records are read from disk       |
+-------------------------------------------------------------------------+
                                    |
                                    v
            +-----------------------------------------------+
            |               RECORD READING LOOP             |
            |   1. Read record based on RS (default: \n)    |
            |   2. Split record into $1..$NF based on FS    |
            |   3. Increment NR and FNR                     |
            +-----------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                       PATTERN / ACTION EVALUATION                       |
|   pattern1 { action1 }                                                  |
|   $3 >= 500 { print $1, $4 }                                            |
|   /ERROR/  { errors++ }                                                 |
+-------------------------------------------------------------------------+
                                    |
                                    v (Repeat for all records)
+-------------------------------------------------------------------------+
|                               END { ... }                               |
|          Executed ONCE after all input streams reach EOF                |
+-------------------------------------------------------------------------+
```

### 3.1 Special Internal Variables Reference Matrix

| Variable | Full Technical Name | Default Value | Architectural Purpose |
| :--- | :--- | :---: | :--- |
| **`$0`** | Entire Current Record | Raw Line | Holds the complete, unparsed input record string. |
| **`$1` .. `$NF`** | Individual Fields | Substring | Extracted fields from the current record. `$NF` is the last field! |
| **`FS`** | Field Separator | `" "` (Space) | Regexp or character used to split `$0`. Setting to `","` parses CSV. |
| **`OFS`** | Output Field Separator | `" "` (Space) | Delimiter inserted between arguments in `print a, b`. |
| **`RS`** | Record Separator | `"\n"` (Newline) | Delimiter defining record boundaries. Set to `""` for multi-line paragraphs! |
| **`ORS`** | Output Record Separator | `"\n"` | Appended to every `print` statement. |
| **`NR`** | Total Number of Records | `0` | Running counter of all records processed across all input files. |
| **`FNR`** | File Number of Records | `0` | Record counter that resets to 1 whenever a new file is opened. |
| **`NF`** | Number of Fields | Dynamically computed | Count of fields found in the current record. |
| **`FILENAME`**| Current File Path | String | Name of the file currently being processed. |

### 3.2 Associative Arrays: The AWK Superpower
Unlike C arrays, which require integer indices, AWK arrays are **associative hash tables** that accept arbitrary strings as keys:

```awk
# Calculate total bytes transferred per IP address from an Nginx log:
# $1 = Client IP, $10 = HTTP Response Bytes
awk '{ bytes[$1] += $10; hits[$1]++ } END {
    for (ip in bytes) {
        printf "%-16s | Requests: %6d | Volume: %10.2f MB\n", ip, hits[ip], bytes[ip] / (1024 * 1024)
    }
}' /var/log/nginx/access.log
```

#### Hash Table Scaling & Memory Warning:
Every entry in an AWK associative array allocates a hash node in userspace RAM. If processing a 100GB dataset with 50,000,000 distinct IP addresses, AWK heap memory will swell to several gigabytes!

---

## 4. The `sed` Stream Editor: Pattern Space & Hold Space Mechanics

`sed` processes input line-by-line using two internal, dynamically-allocated string memory buffers:
1. **The Pattern Space**: The active workspace buffer. Lines read from disk are placed here, transformed by substitution commands, and printed to `stdout`.
2. **The Hold Space**: A passive backup buffer used for long-term storage or multi-line staging. Data remains in the hold space across line cycles until explicitly overwritten or exchanged.

```
THE SED DUAL-BUFFER STATE MACHINE:
                       +---------------------------------+
Input Stream --------> |         PATTERN SPACE           | -------> Output Stream
                       | (Active transformation buffer)  |
                       +---------------------------------+
                                     |   ^
                                   h |   | g
                                   H |   | G
                                     v   |
                       +---------------------------------+
                       |           HOLD SPACE            |
                       | (Passive backup storage buffer) |
                       +---------------------------------+
                               (x exchanges both!)
```

### 4.1 The Complete Buffer Control Commands:
* **`h` (Hold)**: Copies Pattern Space to Hold Space (overwrites previous hold).
* **`H` (Hold Append)**: Appends a newline and Pattern Space to Hold Space.
* **`g` (Get)**: Copies Hold Space to Pattern Space (overwrites previous pattern).
* **`G` (Get Append)**: Appends a newline and Hold Space to Pattern Space.
* **`x` (Exchange)**: Swaps the contents of Pattern Space and Hold Space atomically!

### 4.2 Substitution Command Anatomy: `s/regex/replacement/flags`
The most common operation in `sed` is substitution:
```bash
sed 's/old_pattern/new_string/g' file.txt
```

#### Supported Flags:
- **`g` (Global)**: Replace all occurrences on the line, not just the first.
- **`p` (Print)**: Print the Pattern Space if a successful substitution occurred (often used with `sed -n`).
- **`w <file>`**: Write matching lines to an external file.
- **`I` or `i`**: Case-insensitive regular expression match.
- **`\1`, `\2` (Backreferences)**: Insert captured sub-expressions enclosed in `\(` and `\)`.

```bash
# Reorder date from YYYY-MM-DD to DD-MM-YYYY using backreferences:
sed -E 's/([0-9]{4})-([0-9]{2})-([0-9]{2})/\3-\2-\1/g' dates.txt
```

---

## 5. Production Shell Mastery: The Wrangling Pipeline

Let us analyze a real-world enterprise log auditing problem:
**"Find the top 5 offending IP addresses generating HTTP 5xx Server Errors, along with their error rates, sorted in descending order."**

```bash
cat /var/log/nginx/access.log | \
awk '$9 >= 500 && $9 < 600 { err[$1]++ } { total[$1]++ } END {
    for (ip in err) {
        pct = (err[ip] / total[ip]) * 100;
        printf "%-15s | Total: %6d | 5xx: %5d | ErrorRate: %5.1f%%\n", ip, total[ip], err[ip], pct
    }
}' | sort -k8 -nr | head -n 5
```

---

## 6. Real-World Production War Stories

### 6.1 War Story 1: The `sed -i` Kubernetes Pod Disaster
* **The Incident**: An automated configuration updating script in a Kubernetes deployment ran:
  ```bash
  sed -i 's/10.0.0.1/10.0.0.2/g' /etc/hosts
  ```
* **The Error**: The container threw `Device or resource busy` or broke Docker's live `/etc/hosts` container mount!
* **The Underlying Physics**:
  - `sed -i` (in-place edit) does **not** write directly into the existing file!
  - It creates a temporary file in the same directory (e.g., `sed123abc`), writes the modified stream to it, and then executes `rename("sed123abc", "/etc/hosts")`.
  - In Linux containers, `/etc/hosts` is an isolated **bind-mount** directly to a file on the host. The `rename()` system call cannot overwrite a mount point, resulting in `EBUSY`!
* **The SRE Fix**: Never use `sed -i` on bind-mounted files. Instead, use in-place shell redirection with a temporary file or copy:
  `sed 's/.../.../' /etc/hosts > /tmp/h && cat /tmp/h > /etc/hosts && rm /tmp/h`

---

## 7. Staff-Level Technical Interview Deep-Dives

### Question 1: What is the exact difference between `NR` and `FNR` in AWK, and how do you use them to join two files?
**Exhaustive Answer**:
* **`NR` (Number of Records)**: The aggregate record count across **all** files passed as CLI arguments. It never resets.
* **`FNR` (File Number of Records)**: The record count within the **current** file. It resets to `1` every time a new file is opened.
* **The Two-File Join Idiom**:
  ```awk
  # File 1: ID to Username mapping (id.txt)
  # File 2: Transaction logs with ID in column 1 (tx.log)
  awk 'NR == FNR { user[$1] = $2; next } { print $1, user[$1], $2 }' id.txt tx.log
  ```
  While `NR == FNR`, AWK knows it is reading the first file (`id.txt`), so it populates the `user` associative array. Once `NR > FNR`, it is reading the second file, and enriches transactions using the pre-populated array!

### Question 2: Why is `awk` significantly faster at processing columnar data than Python's `csv` module for large files?
**Exhaustive Answer**:
* Python's `csv.reader` allocates a separate `PyUnicode` object for every single field on every line, triggering millions of small allocations on the Python heap and thrashing garbage collector caches.
* GNU AWK (`gawk`) is written in optimized C. It maintains a single mutable record buffer in RAM and splits fields by replacing delimiters with null terminators (`\0`), keeping field pointers directly within the existing memory page. Zero heap allocations occur per line!

---

## 8. Complete Verification Checklist (Zero Gaps)
- [ ] What are the two internal memory buffers maintained by `sed`?
- [ ] How does `cut` differ from `awk` in terms of memory overhead and delimiter support?
- [ ] Write an AWK one-liner to calculate the sum of numbers in the third column of a CSV file.
- [ ] Why does `sed -i` fail on Docker container `/etc/hosts` bind mounts?
- [ ] Explain the classic `NR == FNR` pattern used in AWK to join two tabular files.
