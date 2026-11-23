# -*- coding: utf-8 -*-
"""
Day 3 Lab: Custom `grep` Implementation from Scratch
Supports regex search, case-insensitivity (-i), line numbers (-n), and inverse matching (-v).
"""
import sys
import re

def run_grep():
    args = sys.argv[1:]
    if not args:
        print("Usage: python my_grep.py [-i] [-n] [-v] <pattern> [file_paths...]")
        return

    ignore_case = False
    show_line_nums = False
    invert_match = False
    clean_args = []

    for a in args:
        if a == "-i":
            ignore_case = True
        elif a == "-n":
            show_line_nums = True
        elif a == "-v":
            invert_match = True
        else:
            clean_args.append(a)

    if not clean_args:
        print("Error: Missing search pattern!")
        return

    pattern_str = clean_args[0]
    file_paths = clean_args[1:]

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern_str, flags)
    except re.error as e:
        sys.stderr.write(f"my_grep: invalid regex pattern '{pattern_str}': {e}\n")
        return

    def process_file(stream, prefix=""):
        line_num = 0
        for line in stream:
            line_num += 1
            has_match = bool(regex.search(line))
            
            # If invert_match is True, we print when there is NO match
            should_print = (not has_match) if invert_match else has_match

            if should_print:
                output = ""
                if prefix:
                    output += f"{prefix}:"
                if show_line_nums:
                    output += f"{line_num}:"
                output += line
                sys.stdout.write(output)

    if not file_paths:
        process_file(sys.stdin)
    else:
        multiple_files = len(file_paths) > 1
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    prefix = path if multiple_files else ""
                    process_file(f, prefix)
            except FileNotFoundError:
                sys.stderr.write(f"my_grep: {path}: No such file or directory\n")
            except Exception as e:
                sys.stderr.write(f"my_grep: {path}: Error: {e}\n")

if __name__ == "__main__":
    run_grep()
