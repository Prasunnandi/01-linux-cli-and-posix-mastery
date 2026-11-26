# Hands-On Lab: Day 35 - Berkeley Packet Filter (BPF) VM Engine (`bpf_packet_filter_engine.py`)

## 1. What Are We Building & Why Does It Matter?
When you run `tcpdump -i eth0 port 80`, how does your computer filter through millions of packets per second without lagging?
It does NOT copy packets into user space to check them with Python or C strings.
Instead, your filter is compiled into **Berkeley Packet Filter (cBPF)** microcode bytecode.
This bytecode runs **directly inside the Linux kernel network interrupt handler**. If a packet does not match the filter, the kernel drops it immediately with zero user-space context switches.

In this lab, we build `bpf_packet_filter_engine.py`, a complete virtual machine interpreter that executes standard BPF bytecode instructions against raw packet byte streams.

---

## 2. Python Concepts for Beginners
1. **Bitwise Bitmask Extraction (`& 0x07` and `& 0x18`)**:
   - In BPF, instructions pack the instruction class, memory size, and operation into a single 16-bit integer opcode. Masking with `& 0x07` extracts the bottom 3 bits (instruction class).
2. **Byte Arrays (`bytearray(40)`)**:
   - Creates a mutable array of 40 zero bytes.
   - We assign packet header fields using slice assignment `pkt[12:14] = b'\x08\x00'`.
3. **Integer to Big-Endian Bytes (`.to_bytes(2, "big")`)**:
   - Network protocols are strictly Big-Endian. `(80).to_bytes(2, "big")` converts decimal 80 to `b'\x00\x50'`.

---

## 3. Step-by-Step Code Walkthrough

```python
if cls == BPF_LD:
    # Load 16-bit integer from packet offset
    A = (packet[offset] << 8) | packet[offset + 1]
```
- The accumulator register `A` loads bytes directly from the network packet at offset `k`.

```python
elif op == BPF_JEQ:
    pc += (inst.jt + 1) if (A == inst.k) else (inst.jf + 1)
```
- Implements conditional branching: if register `A` equals immediate value `k` (e.g. EtherType is IPv4 or Port is 80), it jumps to the true branch; otherwise, it jumps to the false branch.

---

## 4. How to Run the Script

```bash
cd code/day-35
python bpf_packet_filter_engine.py
```

### Expected Output
```
====================================================
DAY 35: BERKELEY PACKET FILTER (BPF) BYTECODE VM
====================================================
Packet 1 (TCP Port 80) -> BPF Decision: ACCEPTED (65535 bytes)
Packet 2 (UDP Port 53) -> BPF Decision: DROPPED (0 bytes)
-------------------------------------------------------
[VERIFIED] Berkeley Packet Filter virtual machine execution confirmed 100% correct!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`IndexError: bytearray index out of range`**:
   - If a packet is smaller than the offset being read (e.g. truncated packet), direct indexing crashes. The VM guards with `if offset < pkt_len:`.
2. **Relative Jump Offset Off-by-One**:
   - In BPF, jump offsets are relative to the *next* instruction. That's why the program counter advances by `jt + 1`.

---
### Additional Python Beginner Foundations
- **Virtual Machine Instructions in Software**:
  Berkeley Packet Filters (BPF) operate as an in-kernel register machine. Implementing an instruction dispatcher in Python (`match instruction.opcode:`) illustrates how low-level bytecode emulators and virtual machines work under the hood.
- **Slicing Byte Buffers Safely**:
  Raw network packets are byte arrays. Slicing `packet[offset:offset+4]` must always be guarded by length checks to prevent `IndexError` on truncated packets.

### Extended Debugging Guide
1. **EtherType Identification**: Ethernet frames start with 14 bytes (6B dest MAC, 6B src MAC, 2B EtherType). IPv4 is `0x0800`; ARP is `0x0806`. Checking EtherType first prevents interpreting non-IP traffic as IP packets.
2. **Endianness in Network Byte Order**: BPF registers store words in host order, but network packets are big-endian. Use `struct.unpack('!H', data)` when loading multi-byte words into registers.

## 6. Beginner Exercises & Challenges
1. **Add HTTPS Filter (Port 443)**: Modify the BPF program to accept traffic for port 443 (HTTPS) instead of port 80.
2. **Disassemble BPF**: Write a helper function `disassemble(program)` that prints human-readable assembly instructions (e.g. `ldh [12]`, `jeq #0x800`).
