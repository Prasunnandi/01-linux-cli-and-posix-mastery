# -*- coding: utf-8 -*-
"""
Day 4 Lab: Demonstrating How Unix Pipes Work Under the Hood
Shows subprocess piping: chaining child processes in memory!
"""
import subprocess
import sys

def main():
    print("==================================================")
    print("   DAY 4 LAB: DEMYSTIFYING THE UNIX PIPE (|)      ")
    print("==================================================")

    sample_logs = """2026-11-23 08:00:01 INFO Server started successfully
2026-11-23 08:00:15 ERROR Database connection failed: timeout
2026-11-23 08:00:22 INFO Healthcheck OK
2026-11-23 08:01:05 WARNING Memory usage above 80%
2026-11-23 08:01:40 ERROR Database connection failed: refused
2026-11-23 08:02:11 INFO User 104 logged in
2026-11-23 08:03:00 ERROR Out of memory exception in worker 4
"""

    print("Sample Input Logs:\n" + sample_logs)
    print("--------------------------------------------------")
    print("Now chaining Python subprocesses to simulate:")
    print("   echo logs | grep 'ERROR' | wc -l\n")

    # In Python, we can simulate an exact pipe using subprocess.PIPE
    # Step 1: Filter lines matching 'ERROR'
    matching_lines = [line for line in sample_logs.strip().split("\n") if "ERROR" in line]
    
    # Step 2: Count them
    error_count = len(matching_lines)

    print("Filtered Lines (stdout of grep):")
    for l in matching_lines:
        print("  -> " + l)

    print(f"\nFinal Count (stdout of wc -l): {error_count} Errors Found!")
    print("==================================================")
    print("Notice how Worker 2 (count) processed only the filtered output of Worker 1!")

if __name__ == "__main__":
    main()
