# Hands-On Lab: Day 15 - Partition Table Analyzer (MBR vs GPT) (`partition_parser.py`)

## 1. What Are We Building & Why Does It Matter?
When formatting hard drives, engineers must choose between two partition schemes:
- **MBR (Master Boot Record)**: The 1983 legacy standard. Uses 32-bit sector counters, capping drive size at 2.19 Terabytes.
- **GPT (GUID Partition Table)**: The modern UEFI standard. Uses 64-bit sector counters, allowing storage drives up to 9.44 Zettabytes.

In this lab, we build `partition_parser.py` to calculate and compare the exact mathematical limits of MBR and GPT partition tables using Python's arbitrary-precision integer arithmetic.

---

## 2. Python Concepts for Beginners
1. **Large Number Exponents (`**`)**:
   - In Python, `2**32` means $2^{32}$ ($4,294,967,296$).
   - `2**64` means $2^{64}$ ($18,446,744,073,709,551,616$).
   - Unlike C or Java (which overflow if numbers exceed 32 or 64 bits), Python automatically supports arbitrarily large integers!
2. **String Formatting (`f"{value:,}"`)**:
   - Adding `:,` inside an f-string automatically formats large numbers with commas: `f"{1000000:,}"` prints as `1,000,000`.

---

## 3. Step-by-Step Code Walkthrough

```python
def analyze_partition_limits(sector_size_bytes: int = 512) -> dict:
    # MBR: 32-bit unsigned sector count
    max_mbr_sectors = 2**32
    max_mbr_bytes = max_mbr_sectors * sector_size_bytes
    max_mbr_tib = max_mbr_bytes / (1024**4) # TiB (1024^4 bytes)

    # GPT: 64-bit unsigned sector count
    max_gpt_sectors = 2**64
    max_gpt_bytes = max_gpt_sectors * sector_size_bytes
    max_gpt_zb = max_gpt_bytes / (1024**7) # ZiB (1024^7 bytes)
```
- With 512-byte sectors, MBR max bytes is $4,294,967,296 	imes 512 = 2,199,023,255,552	ext{ bytes} pprox 2.0	ext{ TiB}$.
- GPT max bytes is $2^{64} 	imes 512 pprox 9.44 	imes 10^{21}	ext{ bytes} pprox 8.0	ext{ ZiB}$!

---

## 4. How to Run the Script

```bash
cd code/day-15
python partition_parser.py
```

### Expected Output
```
MBR Maximum Capacity:
  Total Sectors : 4,294,967,296
  Total Capacity: 2.00 TiB (2,199,023,255,552 bytes)
GPT Maximum Capacity:
  Total Sectors : 18,446,744,073,709,551,616
  Total Capacity: 8.00 ZiB (Zettabytes)
Architectural Verdict:
  Any drive > 2TB MUST use GPT!
```

---

## 5. Beginner Exercises to Try
1. Run the function with 4096-byte native sectors (`analyze_partition_limits(sector_size_bytes=4096)`).
2. Observe how Advanced Format 4Kn drives increase the MBR limit to 16 TiB.
---

## 6. Common Python Errors & How to Fix Them
As a beginner to Python, you may run into these common errors while experimenting:

1. **`ValueError: invalid literal for int() with base 10`**:
   - **Why it happens**: You called `int("hello")` or tried to convert an empty string `""` into a number.
   - **How to fix**: Always inspect what string you are passing into `int()`. Use `.strip()` to remove stray newline characters or check `if s.isdigit():` before converting.
2. **`KeyError: 'some_key'`**:
   - **Why it happens**: You tried to access a dictionary key that does not exist (`metrics["non_existent"]`).
   - **How to fix**: Use the `.get()` method instead: `metrics.get("some_key", default_value)`. This returns `default_value` safely without crashing your program.
3. **`IndexError: list index out of range`**:
   - **Why it happens**: You tried to access `items[5]` when the list only contains 3 items.
   - **How to fix**: Always verify the length of your list with `len(items)` before indexing into it.
4. **`FileNotFoundError`**:
   - **Why it happens**: You attempted to open a file that does not exist in the current working directory.
   - **How to fix**: Print `os.getcwd()` to check where your script is currently looking, or use absolute paths.

---

## 7. Line-by-Line Code Reference

Here is a summary of every standard library function and built-in used in this lab:
- `open(filename, mode)`: Opens a file stream for reading (`'r'`) or writing (`'w'`).
- `len(collection)`: Returns the number of items in a list, string, or dictionary.
- `print(...)`: Outputs text or variable values to the standard output stream (terminal).
- `assert condition, "error message"`: Sanity-checks that internal logic holds true; crashes with message if false.
- `if __name__ == '__main__':`: Standard Python boilerplate that executes test code when run directly from the command line, but does not run when imported as a module by other scripts.

