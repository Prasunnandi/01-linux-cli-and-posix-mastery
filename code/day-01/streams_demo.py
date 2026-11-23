# -*- coding: utf-8 -*-
"""
Day 1 Hands-On Lab: Proving the 3 Standard Streams (stdin, stdout, stderr)
Author: 2300-Days Mastery Curriculum
Beginner & Fresher Friendly!
"""

import sys

def main():
    print("==================================================")
    print("  WELCOME TO DAY 1: THE 3 STANDARD STREAMS LAB!   ")
    print("==================================================")
    
    # 1. Writing to STDOUT (Standard Output - File Descriptor 1)
    # This is where normal, happy messages go!
    sys.stdout.write("[SUCCESS] This message is sent to STDOUT (FD 1).\n")
    sys.stdout.flush()

    # 2. Writing to STDERR (Standard Error - File Descriptor 2)
    # This is where error alarms go! Even if stdout is saved to a file,
    # stderr will still pop up on your screen to warn you!
    sys.stderr.write("[WARNING] This message is sent to STDERR (FD 2)!\n")
    sys.stderr.flush()

    print("\n--- Interactive Input Test ---")
    print("Now type your name and press Enter (testing STDIN - FD 0):")
    
    # 3. Reading from STDIN (Standard Input - File Descriptor 0)
    try:
        user_input = sys.stdin.readline().strip()
        if user_input:
            print(f"Hello, {user_input}! Your input was successfully read via STDIN!")
        else:
            print("You pressed Enter without typing anything! That's okay too.")
    except Exception as e:
        sys.stderr.write(f"Error reading stdin: {e}\n")

    print("\n--- PRO TIP FOR YOUR TERMINAL ---")
    print("Try running this script in your terminal like this:")
    print("  python streams_demo.py > output.txt")
    print("Notice how the [SUCCESS] message goes into output.txt,")
    print("but the [WARNING] message STILL appears on your screen!")
    print("That is the superpower of separated standard streams!")

if __name__ == "__main__":
    main()
