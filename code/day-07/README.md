# Day 07 Lab: Simulating GNU External Merge Sort & Deduplication in Python

> **Welcome to Day 7!** Have you ever wondered: *"How does a computer sort a 100-Gigabyte file when the computer only has 8 Gigabytes of RAM?"*
> If you load the whole file into RAM, the system crashes! In this lab, you will learn the exact algorithm Linux GNU `sort` uses to solve this problem: **External K-Way Merge Sort**.

---

## 🎯 What Does This Lab Do?
`external_merge_sort_sim.py` simulates how Linux sorts data that is too big to fit in memory:
1. **Phase 1 (Run Generation)**: Reads a small chunk of data that fits in RAM (e.g. 5 items), sorts it in memory, and writes it to a temporary file on disk.
2. **Phase 2 (K-Way Merge)**: Opens all temporary files simultaneously, and uses a **Min-Heap (Priority Queue)** to merge them in sorted order while keeping only ONE number per file in memory!
3. **Stream Deduplication (`uniq`)**: Removes duplicates on the fly in $O(1)$ memory without creating giant memory sets.

---

## 🚀 How to Run the Code
Run the script in your terminal:
```bash
python external_merge_sort_sim.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. What is a Min-Heap? (`import heapq`)
* Imagine a stack of numbered cards where the **smallest card always floats to the top**.
* `heapq.heappush(heap, item)`: Adds an item to the heap in $O(\log K)$ time.
* `heapq.heappop(heap)`: Pops the absolute smallest item off the top in $O(\log K)$ time!
* This makes merging $K$ sorted files lightning fast.

### 2. Python Generators & The `yield` Keyword
* Normally, a function uses `return [1, 2, 3]`, which builds the entire list in memory and returns it all at once.
* But when sorting billions of numbers, that would crash your machine!
* **The `yield` magic**:
  ```python
  def count_to_three():
      yield 1
      yield 2
      yield 3
  ```
  Instead of building a giant list, `yield` produces numbers **one at a time on demand**, like a conveyor belt, keeping memory usage at almost zero!

### 3. Tuples: `(value, file_index)`
* A tuple in Python is an immutable pair wrapped in parentheses, like `(4, 0)`.
* When pushed into `heapq`, Python automatically sorts by the first element (`value`). If values tie, it looks at the second element (`file_index`).

### 4. What is `assert`?
* `assert sorted_result == sorted(raw_data)` is a built-in safety check.
* If the equation is `True`, Python stays silent and continues.
* If the equation is `False`, Python immediately halts with an `AssertionError`. It guarantees that our custom sorting algorithm mathematically matches Python's built-in sort!

---

## 🔍 Code Walkthrough

```python
import heapq

# 1. Phase 1: Splitting big input into tiny sorted temporary files
# (e.g. chunk size = 5 items)
runs = sorter.split_into_sorted_runs(raw_data)

# 2. Phase 2: K-Way Heap Merge
# Keep a heap of size K (one item per run file)
min_heap = []
for file_idx, fh in enumerate(file_handles):
    first_val = int(fh.readline().strip())
    heapq.heappush(min_heap, (first_val, file_idx))

while min_heap:
    # Pop the global minimum across all K files
    smallest_val, file_idx = heapq.heappop(min_heap)
    yield smallest_val

    # Read the next number from ONLY the file that gave us that minimum
    next_line = file_handles[file_idx].readline()
    if next_line:
        heapq.heappush(min_heap, (int(next_line.strip()), file_idx))
```

---

## 📋 Expected Terminal Output
```text
============================================================
DAY 07 LAB: SIMULATING GNU EXTERNAL SORT & STREAM DEDUP
============================================================

[1] Raw Unsorted Input (25 items):
    [21, 4, 1, 24, 9, 8, 8, 5, 24, 4, 22, 24, 29, 18, 3, 19, 14, 2, 1, 3, 7, 8, 17, 20, 1]

[2] Phase 1 Completed: Generated 5 sorted temporary runs on disk.

[3] Phase 2 Completed: K-Way Merge Result (Sorted):
    [1, 1, 1, 2, 3, 3, 4, 4, 5, 7, 8, 8, 8, 9, 14, 17, 18, 19, 20, 21, 22, 24, 24, 24, 29]
    [PASS] External Sort output matches Python Timsort perfectly.

[4] Stream Deduplication (Simulated `uniq`):
    [1, 2, 3, 4, 5, 7, 8, 9, 14, 17, 18, 19, 20, 21, 22, 24, 29]
    [PASS] Stream Deduplication matched mathematical set deduplication.
============================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: In `external_merge_sort_sim.py`, change `memory_chunk_limit = 2`. How many temporary runs are generated for 25 numbers? (Answer: $\lceil 25/2 \rceil = 13$ runs!).
2. **Challenge 2**: Notice how `stream_deduplicate` compares each item only to `last_seen`. Why does this require the list to be sorted first? What happens if you run it on unsorted data?
