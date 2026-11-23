"""
Day 07: External K-Way Merge Sort & Deduplication Engine
Zero-Knowledge-Gap Implementation of Linux GNU `sort` and `uniq` internals.

This simulator demonstrates:
1. Phase 1 (Run Generation): Breaking a dataset larger than RAM into sorted temporary chunks.
2. Phase 2 (K-Way Heap Merge): Merging K sorted chunks simultaneously using a Min-Heap (priority queue)
   in O(N * log K) time with strictly bounded O(K) memory overhead.
3. Stream Deduplication: Simulating GNU `uniq` and `sort -u` streaming deduplication.
"""

import heapq
import os
import tempfile
import random
from typing import List, Generator, Tuple


class ExternalMergeSorter:
    """
    Simulates how GNU sort operates when sorting files larger than physical RAM.
    """
    def __init__(self, memory_chunk_limit: int = 5):
        """
        :param memory_chunk_limit: Max number of records held in memory simultaneously.
        """
        self.chunk_limit = memory_chunk_limit
        self.temp_files = []

    def split_into_sorted_runs(self, data_stream: List[int]) -> List[str]:
        """
        Phase 1: Read up to chunk_limit items, sort in RAM, flush to temporary files.
        """
        self.temp_files = []
        buffer = []

        for item in data_stream:
            buffer.append(item)
            if len(buffer) >= self.chunk_limit:
                buffer.sort()
                tmp = tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8')
                for val in buffer:
                    tmp.write(f"{val}\n")
                tmp.close()
                self.temp_files.append(tmp.name)
                buffer = []

        # Flush any remaining items
        if buffer:
            buffer.sort()
            tmp = tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8')
            for val in buffer:
                tmp.write(f"{val}\n")
            tmp.close()
            self.temp_files.append(tmp.name)

        return self.temp_files

    def k_way_merge(self, run_filenames: List[str]) -> Generator[int, None, None]:
        """
        Phase 2: K-Way Merge using a Min-Heap.
        Maintains exactly one element per file in memory at any given time.
        Time Complexity: O(N * log K) where K is number of runs, N is total items.
        Space Complexity: O(K) memory.
        """
        # Open file pointers
        file_handles = [open(f, 'r', encoding='utf-8') for f in run_filenames]
        min_heap: List[Tuple[int, int]] = []  # tuple: (current_value, file_index)

        # Initialize heap with the first element of each run
        for idx, fh in enumerate(file_handles):
            line = fh.readline()
            if line:
                heapq.heappush(min_heap, (int(line.strip()), idx))

        while min_heap:
            val, file_idx = heapq.heappop(min_heap)
            yield val

            # Advance the file pointer of the run that supplied this minimum
            next_line = file_handles[file_idx].readline()
            if next_line:
                heapq.heappush(min_heap, (int(next_line.strip()), file_idx))

        # Cleanup handles and temp files
        for fh in file_handles:
            fh.close()
        for f in run_filenames:
            if os.path.exists(f):
                os.remove(f)

    def sort(self, data: List[int]) -> List[int]:
        runs = self.split_into_sorted_runs(data)
        return list(self.k_way_merge(runs))


def stream_deduplicate(sorted_stream: Generator[int, None, None]) -> Generator[int, None, None]:
    """
    Simulates GNU `uniq`: Yields only distinct adjacent elements in O(1) memory.
    Requires input stream to be pre-sorted.
    """
    last_seen = None
    for item in sorted_stream:
        if item != last_seen:
            yield item
            last_seen = item


# --- SELF-CONTAINED VERIFICATION LAB ---
if __name__ == "__main__":
    print("=" * 60)
    print("DAY 07 LAB: SIMULATING GNU EXTERNAL SORT & STREAM DEDUP")
    print("=" * 60)

    # 1. Generate an unsorted dataset of 25 numbers
    random.seed(42)
    raw_data = [random.randint(1, 30) for _ in range(25)]
    print(f"\n[1] Raw Unsorted Input (25 items):\n    {raw_data}")

    # 2. Simulate sorting with a tiny memory buffer limit of 5 items
    sorter = ExternalMergeSorter(memory_chunk_limit=5)
    runs = sorter.split_into_sorted_runs(raw_data)
    print(f"\n[2] Phase 1 Completed: Generated {len(runs)} sorted temporary runs on disk.")

    # 3. Perform K-Way Merge
    sorted_result = list(sorter.k_way_merge(runs))
    print(f"\n[3] Phase 2 Completed: K-Way Merge Result (Sorted):\n    {sorted_result}")

    # Verify correctness against Python's built-in sort
    assert sorted_result == sorted(raw_data), "Validation Failure: External Sort output does not match expected sorted list!"
    print("    [PASS] External Sort output matches Python Timsort perfectly.")

    # 4. Stream Deduplication (`sort -u` / `uniq`)
    deduped = list(stream_deduplicate(iter(sorted_result)))
    print(f"\n[4] Stream Deduplication (Simulated `uniq`):\n    {deduped}")
    assert deduped == sorted(list(set(raw_data))), "Validation Failure: Deduplication output mismatch!"
    print("    [PASS] Stream Deduplication matched mathematical set deduplication.")

    print("\n" + "=" * 60)
    print("ALL DAY 07 VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 60)
