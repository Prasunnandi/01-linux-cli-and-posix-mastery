# Day 48: ELF Core Dump Header & CPU Register Frame Parser

## 1. What Are We Building & Why Does It Matter?
When a Linux C or C++ application crashes with a Segmentation Fault (`SIGSEGV`) or Abort (`SIGABRT`), the Linux kernel pauses the process and dumps its active memory and CPU state to disk in an **ELF Core Dump** file (`ET_CORE`).
Diagnostic tools like `gdb` and `coredumpctl` do not read text logs—they parse the raw binary ELF headers to inspect:
- The exact terminating signal number (`11 = SIGSEGV`).
- The faulting memory address (`si_addr`).
- The CPU registers at the moment of the crash (Instruction Pointer `RIP`, Stack Pointer `RSP`).
- The memory segments (`PT_LOAD`) containing mapped heap and stack pages.

In this lab, we build an **ELF Core Dump Binary Analyzer** in pure Python that parses 64-bit ELF headers and extracts CPU crash frames.

---

## 2. Python Concepts for Beginners

### A. Binary Magic Byte Matching
All ELF files begin with the 4-byte signature `ELF`. We verify this in Python using binary byte string matching:
```python
if data[:4] != b"ELF":
    raise ValueError("Not an ELF file!")
```

### B. Hexadecimal Register Formatting (`0x{rip:016X}`)
64-bit CPU memory addresses are 8 bytes long. Formatting with `:016X` in Python f-strings displays them as clean 16-character zero-padded hexadecimal strings:
```python
rip = 4198722
print(f"0x{rip:016X}")  # "0x0000000000401142"
```

### C. Multi-Field Binary Struct Unpacking
The ELF64 program header contains 7 consecutive fields totaling 56 bytes. We unpack them simultaneously with `struct.unpack("<IIQQQQQ", data)`.

---

## 3. Step-by-Step Code Walkthrough

1. **`ELFCoreReport` Dataclass**: Stores diagnostic outputs: 64-bit flag, machine architecture, signal number, faulting address, `RIP`, `RSP`, and memory segment list.
2. **`pack_synthetic_core()`**: Crafts a valid 64-bit ELF core dump in memory: 64-byte ELF header, `PT_NOTE` header, `PT_LOAD` header, and PRSTATUS note containing CPU registers.
3. **`parse_core_dump()`**: Reads the binary buffer, validates `e_type == ET_CORE`, iterates program headers, and extracts register telemetry from the note segment.
4. **`main()` Function**: Simulates a crash caused by dereferencing `0xDEADBEEF`, parses the binary output, and verifies that registers match.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-48/elf_core_dump_analyzer.py
```

Expected output:
```text
====================================================
DAY 48: ELF CORE DUMP & CPU REGISTER FRAME ANALYZER
====================================================
1. Packed Synthetic ELF Core Dump: 368 bytes
2. Parsing ELF Core Binary Structure...
3. Extracted Crash Diagnostics Telemetry:
   ELF Class       : 64-bit
   Target Machine  : 62 (62 = x86_64)
   Fatal Signal    : 11 (11 = SIGSEGV)
   Faulting Memory : 0x00000000DEADBEEF
   Instruction RIP : 0x0000000000401142
   Stack Ptr RSP   : 0x00007FFDE3B5F980
   Memory Segments : 1 mapped PT_LOAD segments
   [PASS] Fatal signal, registers, and memory segments decoded with 100% precision.

[VERIFIED] ELF core dump binary analyzer passed all test assertions!
```

---

## 5. Common Python Errors & Troubleshooting

- **Endianness Mismatch**: x86_64 uses Little-Endian (`<`). Unpacking with Big-Endian (`!`) swaps byte order and corrupts addresses.
- **Section Headers vs Program Headers**: Executable files (`ET_EXEC`, `ET_DYN`) rely on Section Headers (`.text`, `.data`), but Core Dumps (`ET_CORE`) rely strictly on Program Headers (`PT_NOTE`, `PT_LOAD`).

---

## 6. Beginner Exercises & Challenges

1. **Signal Name Decoder**: Add a dictionary mapping common signal integers (`6` -> `SIGABRT`, `11` -> `SIGSEGV`, `8` -> `SIGFPE`) to human-readable names.
2. **Backtrace Memory Dumper**: Extract the raw bytes from the `PT_LOAD` segment and print a formatted hexadecimal hex-dump of the crash memory.
3. **32-Bit Compatibility**: Add an `if ei_class == 1:` branch that parses 32-bit ELF core dumps (`Elf32_Ehdr`).
