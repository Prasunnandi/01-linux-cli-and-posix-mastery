# -*- coding: utf-8 -*-
"""
Day 5 Lab: Interactive Linux Permission Calculator
Translates between symbolic notation (rwxr-xr--) and numeric octal (755).
"""

def parse_symbolic(perm_str):
    if len(perm_str) != 9:
        raise ValueError("Permission string must be exactly 9 characters long (e.g. 'rwxr-xr--')")

    def chunk_to_digit(chunk):
        val = 0
        if chunk[0] == 'r': val += 4
        if chunk[1] == 'w': val += 2
        if chunk[2] == 'x': val += 1
        return str(val)

    u = chunk_to_digit(perm_str[0:3])
    g = chunk_to_digit(perm_str[3:6])
    o = chunk_to_digit(perm_str[6:9])
    return u + g + o

def parse_numeric(octal_str):
    if len(octal_str) != 3 or not all(c in '01234567' for c in octal_str):
        raise ValueError("Octal string must be exactly 3 digits between 0 and 7 (e.g. '755')")

    def digit_to_symbols(d_char):
        d = int(d_char)
        r = 'r' if (d & 4) else '-'
        w = 'w' if (d & 2) else '-'
        x = 'x' if (d & 1) else '-'
        return r + w + x

    return digit_to_symbols(octal_str[0]) + digit_to_symbols(octal_str[1]) + digit_to_symbols(octal_str[2])

def main():
    print("==================================================")
    print("  LINUX FILE PERMISSIONS CALCULATOR & SIMULATOR   ")
    print("==================================================")
    
    test_cases = ["755", "644", "700", "777", "600"]
    print("Standard Production Permissions Decoded:")
    for num in test_cases:
        sym = parse_numeric(num)
        print(f"  chmod {num}  ==>  {sym}  (Owner: {sym[0:3]} | Group: {sym[3:6]} | Others: {sym[6:9]})")

    print("\nSymbolic to Numeric Test:")
    symbolic_tests = ["rwxr-xr-x", "rw-r--r--", "rwx------", "rwxr-xr--"]
    for s in symbolic_tests:
        num = parse_symbolic(s)
        print(f"  {s}  ==>  chmod {num}")
    print("==================================================")

if __name__ == "__main__":
    main()
