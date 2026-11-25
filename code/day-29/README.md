# Hands-On Lab: Day 29 - Stream Buffering Simulator (`stream_buffering_sim.py`)

## 1. What Are We Building & Why Does It Matter?
Have you ever run `tail -f log | grep error | awk '{print $1}'` and noticed that **nothing appears on the screen for 20 minutes**, even though errors are actively happening?

This is the famous **stdio buffering stall**:
- When stdout is connected to a terminal, the C standard library uses **Line Buffering** (flushes on every newline `
`).
- When stdout is redirected into a pipe `|`, C automatically switches to **4KB Block Buffering**!
- It refuses to send any data down the pipe until 4,096 bytes accumulate!

In this lab, we build `stream_buffering_sim.py` to simulate all three buffering modes and show how `stdbuf -oL` fixes pipeline stalls.

---

## 2. Python Concepts for Beginners
1. **Enumerations & Constants**:
   - `BufferMode.LINE_BUFFERED` gives readable names to integer settings.
2. **Buffer Accumulation**:
   - Characters are stored in a list and converted to strings with `"".join(list)`.

---

## 3. Step-by-Step Code Walkthrough

```python
def write(self, data: str):
    for char in data:
        self.internal_buffer.append(char)
        if self.mode == BufferMode.BLOCK_BUFFERED and len(self.internal_buffer) >= self.block_size:
            self.flush()
```
- In Block Buffered mode, a 36-byte error message remains trapped in memory because `36 < 4096`.
- `stdbuf -oL` forces Line Buffered mode, flushing the line immediately upon seeing `
`.

---

## 4. How to Run the Script

```bash
cd code/day-29
python stream_buffering_sim.py
```

### Expected Output
```
====================================================
C STDIO STREAM BUFFERING & PIPELINE STALL SIMULATOR
====================================================
Simulated 36-byte Log Write: 'ERROR: Database connection failed.
'
  Line Buffered (Interactive TTY)   : Flushed Chunks = 1 (Immediate delivery)
  Block Buffered (Standard Pipe)    : Flushed Chunks = 0 (STALLED in 4KB buffer!)
  Pipe with 'stdbuf -oL' Override   : Flushed Chunks = 1 (Immediate delivery)

[SUCCESS] Stream buffering pathology and stdbuf fix verified!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **Buffering Delay Confusion**:
   - If you run `print("hello")` without `
` or `flush=True`, Python buffers the string in user memory and nothing appears in the pipe until the buffer flushes. Use `sys.stdout.flush()` or `print(..., flush=True)`.
2. **Binary vs Text Mode Buffering**:
   - In Python, writing raw bytes requires opening files or pipes in `'wb'` mode. Mixing text strings and bytes causes `TypeError: a bytes-like object is required, not 'str'`.
3. **BrokenPipeError: [Errno 32] Broken pipe**:
   - Occurs when writing to a pipe whose reading end has closed (for example, piping to `head -n 5`). Always catch `BrokenPipeError` and exit cleanly.

---

## 6. Beginner Exercises & Challenges
1. **Line Buffering vs Block Buffering**:
   - In C's `stdio`, `stdout` is line-buffered (flushes on `\n`) when connected to a terminal, but block-buffered (flushes every 4096 bytes) when redirected to a pipe. Model this behavior in `stream_buffering_sim.py`.
2. **The `stdbuf -oL` Solution**:
   - Simulate how `stdbuf -oL command | grep ...` injects `libstdbuf.so` via `LD_PRELOAD` to force line buffering through a pipeline.
3. **Measuring Throughput with `pv`**:
   - Add a simulated pipe viewer (`pv`) class that tracks bytes per second, elapsed time, and ETA for a streaming pipe.
