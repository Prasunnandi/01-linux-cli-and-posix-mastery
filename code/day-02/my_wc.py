# -*- coding: utf-8 -*-
"""
Day 2 Lab: Custom `wc` (Word Count) Implementation from Scratch
Counts lines, words, and characters with exact formatting.
"""
import sys

def count_stream(stream):
    lines = 0
    words = 0
    chars = 0
    for line in stream:
        lines += 1
        chars += len(line)
        words += len(line.split())
    return lines, words, chars

def run_wc(file_paths):
    if not file_paths:
        lines, words, chars = count_stream(sys.stdin)
        print(f"{lines:8d} {words:8d} {chars:8d}")
        return

    total_lines = 0
    total_words = 0
    total_chars = 0

    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                l, w, c = count_stream(f)
                total_lines += l
                total_words += w
                total_chars += c
                print(f"{l:8d} {w:8d} {c:8d} {path}")
        except FileNotFoundError:
            sys.stderr.write(f"my_wc: {path}: No such file or directory\n")
        except Exception as e:
            sys.stderr.write(f"my_wc: {path}: Error: {e}\n")

    if len(file_paths) > 1:
        print(f"{total_lines:8d} {total_words:8d} {total_chars:8d} total")

if __name__ == "__main__":
    run_wc(sys.argv[1:])
