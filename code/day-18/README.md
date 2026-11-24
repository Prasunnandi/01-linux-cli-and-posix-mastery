# Day 18 Lab: POSIX Tar 512-Byte Header Engine

## For Beginners to Python

Welcome to Day 18! In this lab, we look inside the binary format of a `.tar` archive file.

### Key Concepts
A tar file does not compress data by itself; it simply packages files one after another into uniform **512-byte blocks**. Each file starts with a 512-byte header holding its name, size in octal, permissions, and checksum.

### How to Run
```bash
python tar_header_parser.py
```
