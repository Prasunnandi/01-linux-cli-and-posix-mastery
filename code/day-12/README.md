# Day 12 Lab: Inode & Link Inspector

## For Beginners to Python

Welcome to Day 12! In this lab, we explore the difference between **Hard Links** and **Soft (Symbolic) Links** at the operating system level.

### What Does This Script Do?
1. It creates a temporary test directory so nothing on your computer is permanently modified.
2. It writes a file called `original.txt`.
3. It creates a **hard link** to that file using `os.link()`.
4. It creates a **symbolic link** using `os.symlink()`.
5. It reads the internal metadata of each file using `os.stat()` and `os.lstat()`.
6. It proves that the hard link shares the **exact same Inode number** as the original file, while the symbolic link receives its own unique Inode!

### How to Run
```bash
python inode_inspector.py
```

### Expected Output
Notice that `inodes_match_for_hardlink` is `True`, while `inodes_match_for_symlink` is `False`:
```
=== Linux Inode & Link Inspector ===
  original_inode: 12345678
  original_link_count: 2
  hardlink_inode: 12345678
  hardlink_link_count: 2
  symlink_inode: 98765432
  symlink_link_count: 1
  inodes_match_for_hardlink: True
  inodes_match_for_symlink: False
```
