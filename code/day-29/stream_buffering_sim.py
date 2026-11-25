#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stream_buffering_sim.py - Stream Buffering & Pipeline Latency Simulator
Models C Standard I/O (stdio) buffering modes:
  - _IONBF: Unbuffered (flushes on every character)
  - _IOLBF: Line Buffered (flushes on newline '\n')
  - _IOFBF: Block Buffered (flushes only when 4096 bytes accumulate)
Demonstrates why pipes stall and how stdbuf forces line buffering.
"""

class BufferMode:
    UNBUFFERED = 0
    LINE_BUFFERED = 1
    BLOCK_BUFFERED = 2

class StreamBuffer:
    def __init__(self, mode: int, block_size: int = 4096):
        self.mode = mode
        self.block_size = block_size
        self.internal_buffer = []
        self.flushed_chunks = []

    def write(self, data: str):
        for char in data:
            self.internal_buffer.append(char)
            if self.mode == BufferMode.UNBUFFERED:
                self.flush()
            elif self.mode == BufferMode.LINE_BUFFERED and char == '\n':
                self.flush()
            elif self.mode == BufferMode.BLOCK_BUFFERED and len(self.internal_buffer) >= self.block_size:
                self.flush()

    def flush(self):
        if self.internal_buffer:
            self.flushed_chunks.append("".join(self.internal_buffer))
            self.internal_buffer = []

def test_buffering():
    msg = "ERROR: Database connection failed.\n"

    # 1. Line Buffered (TTY stdout)
    line_buf = StreamBuffer(BufferMode.LINE_BUFFERED)
    line_buf.write(msg)

    # 2. Block Buffered (Pipe stdout without stdbuf)
    block_buf = StreamBuffer(BufferMode.BLOCK_BUFFERED, block_size=4096)
    block_buf.write(msg) # Writes only 36 bytes -> DOES NOT FLUSH!

    # 3. stdbuf -oL override on pipe
    stdbuf_override = StreamBuffer(BufferMode.LINE_BUFFERED)
    stdbuf_override.write(msg)

    return {
        "line_flushed": len(line_buf.flushed_chunks),
        "block_flushed": len(block_buf.flushed_chunks),
        "stdbuf_flushed": len(stdbuf_override.flushed_chunks)
    }

if __name__ == "__main__":
    print("====================================================")
    print("C STDIO STREAM BUFFERING & PIPELINE STALL SIMULATOR")
    print("====================================================")
    res = test_buffering()
    print("Simulated 36-byte Log Write: 'ERROR: Database connection failed.\\n'")
    print("  Line Buffered (Interactive TTY)   : Flushed Chunks = %d (Immediate delivery)" % res["line_flushed"])
    print("  Block Buffered (Standard Pipe)    : Flushed Chunks = %d (STALLED in 4KB buffer!)" % res["block_flushed"])
    print("  Pipe with 'stdbuf -oL' Override   : Flushed Chunks = %d (Immediate delivery)" % res["stdbuf_flushed"])

    assert res["line_flushed"] == 1
    assert res["block_flushed"] == 0
    assert res["stdbuf_flushed"] == 1
    print("\n[SUCCESS] Stream buffering pathology and stdbuf fix verified!")
