#!/usr/bin/env python3
"""
Day 48 Lab: ELF Core Dump Header & CPU Register Frame Parser
Parses Linux ELF core dump binary files (e_type = ET_CORE):
- 64-bit ELF file header (7f 45 4c 46 ...)
- Program headers (PT_LOAD segments and PT_NOTE segment)
- Extracts faulting signal number (si_signo) and CPU register frame (RIP, RSP).
Uses Python standard library only.
"""

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class ELFCoreReport:
    magic: bytes
    is_64bit: bool
    machine_arch: int
    signal_num: int
    fault_address: int
    reg_rip: int
    reg_rsp: int
    memory_segments: List[Tuple[int, int]]  # (vaddr, memsz)


class ELFCoreDumpAnalyzer:
    ELF_MAGIC = b"\x7fELF"
    ET_CORE = 4
    EM_X86_64 = 62
    PT_LOAD = 1
    PT_NOTE = 4

    @staticmethod
    def pack_synthetic_core(signal_num: int, fault_addr: int, rip: int, rsp: int) -> bytes:
        """Packs a minimal valid 64-bit ELF core dump binary."""
        buf = bytearray()

        # 1. 64-bit ELF Header (64 bytes total)
        # e_ident: 16 bytes
        e_ident = bytearray(ELFCoreDumpAnalyzer.ELF_MAGIC)
        e_ident.extend([2, 1, 1, 0])  # 2=64-bit, 1=Little Endian, 1=Version, 0=SysV
        e_ident.extend(b"\x00" * 8)    # Padding

        # ELF64 Header format: 16s H H I Q Q Q I H H H H H H -> 64 bytes
        elf_header = struct.pack(
            "<16sHHIQQQIHHHHHH",
            bytes(e_ident),
            ELFCoreDumpAnalyzer.ET_CORE,     # e_type = ET_CORE (4)
            ELFCoreDumpAnalyzer.EM_X86_64,   # e_machine = x86_64 (62)
            1,                               # e_version = 1
            0,                               # e_entry = 0
            64,                              # e_phoff = 64 (Program headers start at byte 64)
            0,                               # e_shoff = 0
            0,                               # e_flags = 0
            64,                              # e_ehsize = 64
            56,                              # e_phentsize = 56 bytes per program header
            2,                               # e_phnum = 2 (1 NOTE, 1 LOAD)
            0, 0, 0                          # section header counters
        )
        buf.extend(elf_header)

        # 2. Program Headers (2 x 56 bytes = 112 bytes)
        # Header 1: PT_NOTE (Offset: 176, Size: 128)
        ph_note = struct.pack(
            "<IIQQQQQQ",
            ELFCoreDumpAnalyzer.PT_NOTE, 0,
            176, 0, 0, 128, 128, 0
        )
        buf.extend(ph_note)

        # Header 2: PT_LOAD (Vaddr: 0x400000, Size: 4096)
        ph_load = struct.pack(
            "<IIQQQQQQ",
            ELFCoreDumpAnalyzer.PT_LOAD, 5,  # 5 = R-X permissions
            304, 0x00400000, 0x00400000, 4096, 4096, 4096
        )
        buf.extend(ph_load)

        # 3. PT_NOTE Segment Payload (Synthetic elf_prstatus at byte 176)
        # Note Header: namesz(4), descsz(4), type(4) -> 12 bytes
        note_name = b"CORE\x00\x00\x00\x00"
        note_hdr = struct.pack("<III8s", 5, 80, 1, note_name)
        buf.extend(note_hdr)

        # elf_prstatus payload: signal(4), fault_addr(8), rip(8), rsp(8)
        prstatus_payload = struct.pack("<I4sQQQ", signal_num, b"\x00"*4, fault_addr, rip, rsp)
        buf.extend(prstatus_payload)
        # Pad to offset 304
        buf.extend(b"\x00" * (304 - len(buf)))

        # 4. PT_LOAD Memory Segment Data
        buf.extend(b"\x90" * 64)  # Mock NOP instructions

        return bytes(buf)

    @staticmethod
    def parse_core_dump(data: bytes) -> ELFCoreReport:
        if len(data) < 64:
            raise ValueError("Buffer too small for ELF header")

        magic = data[:4]
        if magic != ELFCoreDumpAnalyzer.ELF_MAGIC:
            raise ValueError(f"Invalid ELF magic: {magic!r}")

        ei_class = data[4]
        is_64 = (ei_class == 2)

        e_type, e_machine, _, _, e_phoff, _, _, _, e_phentsize, e_phnum = struct.unpack(
            "<HHIQQQIHHH", data[16:58]
        )

        if e_type != ELFCoreDumpAnalyzer.ET_CORE:
            raise ValueError(f"File is not an ELF core dump (e_type={e_type})")

        segments = []
        sig_num = 0
        fault_addr = 0
        rip = 0
        rsp = 0

        # Traverse Program Headers
        for i in range(e_phnum):
            ph_offset = e_phoff + (i * e_phentsize)
            p_type, p_flags, p_offset, p_vaddr, _, p_filesz, p_memsz = struct.unpack(
                "<IIQQQQQ", data[ph_offset:ph_offset + 48]
            )

            if p_type == ELFCoreDumpAnalyzer.PT_LOAD:
                segments.append((p_vaddr, p_memsz))

            elif p_type == ELFCoreDumpAnalyzer.PT_NOTE:
                # Parse PRSTATUS note payload
                note_payload = data[p_offset:p_offset + p_filesz]
                if len(note_payload) >= 44:
                    # Skip 20-byte note header
                    sig_num, _, fault_addr, rip, rsp = struct.unpack(
                        "<I4sQQQ", note_payload[20:52]
                    )

        return ELFCoreReport(
            magic=magic,
            is_64bit=is_64,
            machine_arch=e_machine,
            signal_num=sig_num,
            fault_address=fault_addr,
            reg_rip=rip,
            reg_rsp=rsp,
            memory_segments=segments
        )


def main():
    print("====================================================")
    print("DAY 48: ELF CORE DUMP & CPU REGISTER FRAME ANALYZER")
    print("====================================================")

    # Pack synthetic core dump of a SIGSEGV at address 0xDEADBEEF
    sig_segv = 11
    fault_addr = 0x00000000DEADBEEF
    mock_rip = 0x0000000000401142
    mock_rsp = 0x00007FFDE3B5F980

    raw_core = ELFCoreDumpAnalyzer.pack_synthetic_core(
        signal_num=sig_segv,
        fault_addr=fault_addr,
        rip=mock_rip,
        rsp=mock_rsp
    )
    print(f"1. Packed Synthetic ELF Core Dump: {len(raw_core)} bytes")

    # Parse core dump
    print("2. Parsing ELF Core Binary Structure...")
    report = ELFCoreDumpAnalyzer.parse_core_dump(raw_core)

    print("3. Extracted Crash Diagnostics Telemetry:")
    print(f"   ELF Class       : {'64-bit' if report.is_64bit else '32-bit'}")
    print(f"   Target Machine  : {report.machine_arch} (62 = x86_64)")
    print(f"   Fatal Signal    : {report.signal_num} (11 = SIGSEGV)")
    print(f"   Faulting Memory : 0x{report.fault_address:016X}")
    print(f"   Instruction RIP : 0x{report.reg_rip:016X}")
    print(f"   Stack Ptr RSP   : 0x{report.reg_rsp:016X}")
    print(f"   Memory Segments : {len(report.memory_segments)} mapped PT_LOAD segments")

    assert report.is_64bit is True
    assert report.signal_num == 11
    assert report.fault_address == fault_addr
    assert report.reg_rip == mock_rip
    assert len(report.memory_segments) == 1
    print("   [PASS] Fatal signal, registers, and memory segments decoded with 100% precision.")

    print("\n[VERIFIED] ELF core dump binary analyzer passed all test assertions!")


if __name__ == "__main__":
    main()
