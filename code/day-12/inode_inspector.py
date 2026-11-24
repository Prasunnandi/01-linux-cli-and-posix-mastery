#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inode_inspector.py - Inode & Link Inspector
Demonstrates inode number extraction, link counts, and hard vs soft link identification.
"""
import os
import tempfile

def inspect_file_inodes():
    with tempfile.TemporaryDirectory() as tmpdir:
        original = os.path.join(tmpdir, "original.txt")
        with open(original, "w") as f:
            f.write("Production Storage Inode Test Data\n")
            
        hardlink = os.path.join(tmpdir, "hardlink.txt")
        os.link(original, hardlink)
        
        symlink = os.path.join(tmpdir, "symlink.txt")
        os.symlink(original, symlink)
        
        stat_orig = os.stat(original)
        stat_hard = os.stat(hardlink)
        stat_sym = os.lstat(symlink)
        
        return {
            "original_inode": stat_orig.st_ino,
            "original_link_count": stat_orig.st_nlink,
            "hardlink_inode": stat_hard.st_ino,
            "hardlink_link_count": stat_hard.st_nlink,
            "symlink_inode": stat_sym.st_ino,
            "symlink_link_count": stat_sym.st_nlink,
            "inodes_match_for_hardlink": (stat_orig.st_ino == stat_hard.st_ino),
            "inodes_match_for_symlink": (stat_orig.st_ino == stat_sym.st_ino)
        }

if __name__ == "__main__":
    results = inspect_file_inodes()
    print("=== Linux Inode & Link Inspector ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
