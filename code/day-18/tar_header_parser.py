#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tar_header_parser.py - POSIX Tar Ustar 512-Byte Header Engine
Serializes and parses standard POSIX tar header blocks.
"""

def create_tar_header(filename: str, file_size: int, mode: int = 0o644, uid: int = 1000, gid: int = 1000) -> bytes:
    header = bytearray(512)
    # Filename: 0-99
    header[0:len(filename)] = filename.encode('ascii')
    # Mode: 100-107 (Octal string)
    header[100:107] = f"{mode:06o} ".encode('ascii')
    # UID: 108-115
    header[108:115] = f"{uid:06o} ".encode('ascii')
    # GID: 116-123
    header[116:123] = f"{gid:06o} ".encode('ascii')
    # Size: 124-135
    header[124:135] = f"{file_size:011o} ".encode('ascii')
    # MTime: 136-147
    header[136:147] = f"{1700000000:011o} ".encode('ascii')
    # Typeflag: 156 ('0' = regular file)
    header[156] = ord('0')
    # Magic: 257-262 ("ustar\0")
    header[257:263] = b"ustar\x00"
    # Version: 263-264 ("00")
    header[263:265] = b"00"
    
    # Calculate checksum: sum of all bytes in header with chksum field treated as ASCII spaces
    header[148:156] = b"        "
    checksum = sum(header)
    header[148:155] = f"{checksum:06o}\x00".encode('ascii')
    return bytes(header)

def parse_tar_header(header_bytes: bytes) -> dict:
    filename = header_bytes[0:100].decode('ascii').rstrip('\x00')
    size_octal = header_bytes[124:135].decode('ascii').strip().rstrip('\x00')
    magic = header_bytes[257:263]
    return {
        "filename": filename,
        "size_bytes": int(size_octal, 8),
        "is_valid_ustar": (magic == b"ustar\x00")
    }

if __name__ == "__main__":
    test_hdr = create_tar_header("financial_audit.log", file_size=4096)
    parsed = parse_tar_header(test_hdr)
    print("=== POSIX Tar Header Generation & Parsing ===")
    print(f"Header Size: {len(test_hdr)} bytes")
    for k, v in parsed.items():
        print(f"  {k}: {v}")
