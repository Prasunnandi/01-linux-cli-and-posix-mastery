# -*- coding: utf-8 -*-
"""
Day 2 Lab: Custom `cat` Implementation from Scratch
Reads files or standard input line-by-line and streams to stdout.
"""
import sys

def run_cat(file_paths):
    # If no files are given, read directly from standard input (stdin)!
    if not file_paths:
        print("Reading from standard input (type text, press Ctrl+Z or Ctrl+D to exit):")
        for line in sys.stdin:
            sys.stdout.write(line)
        return

    # Loop through every file passed as an argument
    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Read line-by-line (Memory efficient!)
                for line in f:
                    sys.stdout.write(line)
        except FileNotFoundError:
            sys.stderr.write(f"my_cat: {path}: No such file or directory\n")
        except Exception as e:
            sys.stderr.write(f"my_cat: {path}: Error: {e}\n")

if __name__ == "__main__":
    run_cat(sys.argv[1:])
