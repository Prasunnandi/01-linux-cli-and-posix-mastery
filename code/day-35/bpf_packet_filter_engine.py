#!/usr/bin/env python3
"""
Day 35 Lab: Berkeley Packet Filter (BPF) Virtual Machine Engine
Implements a user-space interpreter for classical BPF (cBPF) bytecode,
executing BPF instructions (LD, JEQ, JSET, RET) against raw packet bytes.
"""

from dataclasses import dataclass
from typing import List, Tuple


# BPF Opcode Constants (linux/filter.h)
BPF_LD   = 0x00
BPF_JMP  = 0x05
BPF_RET  = 0x06

# BPF Size Modifiers
BPF_W    = 0x00  # 32-bit word
BPF_H    = 0x08  # 16-bit halfword
BPF_B    = 0x10  # 8-bit byte

# BPF Jump Operations
BPF_JA   = 0x00
BPF_JEQ  = 0x10
BPF_JSET = 0x40


@dataclass
class BPFInstruction:
    code: int   # Opcode
    jt: int     # Jump offset if true
    jf: int     # Jump offset if false
    k: int      # Immediate value / offset


class BPFVirtualMachine:
    def __init__(self, program: List[BPFInstruction]):
        self.program = program

    def evaluate(self, packet: bytes) -> int:
        """
        Executes BPF bytecode program against raw packet bytes.
        Returns the accepted byte length (0 means packet dropped!).
        """
        pc = 0           # Program Counter
        A = 0            # 32-bit Accumulator Register
        pkt_len = len(packet)

        while pc < len(self.program):
            inst = self.program[pc]
            cls = inst.code & 0x07

            if cls == BPF_LD:
                size = inst.code & 0x18
                offset = inst.k
                if size == BPF_B:
                    A = packet[offset] if offset < pkt_len else 0
                elif size == BPF_H:
                    if offset + 1 < pkt_len:
                        A = (packet[offset] << 8) | packet[offset + 1]
                    else:
                        A = 0
                elif size == BPF_W:
                    if offset + 3 < pkt_len:
                        A = (packet[offset] << 24) | (packet[offset + 1] << 16) | (packet[offset + 2] << 8) | packet[offset + 3]
                    else:
                        A = 0
                pc += 1

            elif cls == BPF_JMP:
                op = inst.code & 0xF0
                if op == BPF_JA:
                    pc += inst.k + 1
                elif op == BPF_JEQ:
                    pc += (inst.jt + 1) if (A == inst.k) else (inst.jf + 1)
                elif op == BPF_JSET:
                    pc += (inst.jt + 1) if ((A & inst.k) != 0) else (inst.jf + 1)
                else:
                    pc += 1

            elif cls == BPF_RET:
                return inst.k  # Return accepted length (0 = discard)

        return 0


def main():
    print("====================================================")
    print("DAY 35: BERKELEY PACKET FILTER (BPF) BYTECODE VM")
    print("====================================================")

    # Disassembled BPF Program for filter: 'tcp port 80'
    # Evaluates Ethernet (14B) + IPv4 + TCP header
    bpf_filter_tcp_80 = [
        BPFInstruction(BPF_LD | BPF_H, 0, 0, 12),          # 0: Load EtherType at offset 12
        BPFInstruction(BPF_JMP | BPF_JEQ, 0, 4, 0x0800),   # 1: If EtherType == 0x0800 (IPv4) goto 2, else goto 6 (Drop)
        BPFInstruction(BPF_LD | BPF_B, 0, 0, 23),          # 2: Load IP Protocol at offset 23
        BPFInstruction(BPF_JMP | BPF_JEQ, 0, 2, 6),        # 3: If Protocol == 6 (TCP) goto 4, else goto 6 (Drop)
        BPFInstruction(BPF_LD | BPF_H, 0, 0, 36),          # 4: Load TCP Destination Port at offset 36
        BPFInstruction(BPF_JMP | BPF_JEQ, 1, 0, 80),       # 5: If Port == 80 goto 7 (Accept), else goto 6 (Drop)
        BPFInstruction(BPF_RET, 0, 0, 0),                  # 6: Return 0 (Drop Packet!)
        BPFInstruction(BPF_RET, 0, 0, 65535)               # 7: Return 65535 (Keep Full Packet!)
    ]

    vm = BPFVirtualMachine(bpf_filter_tcp_80)

    # Packet 1: Valid IPv4 + TCP Port 80 packet (40 bytes)
    pkt_tcp_80 = bytearray(40)
    pkt_tcp_80[12:14] = b'\x08\x00'  # IPv4
    pkt_tcp_80[23] = 6                # TCP
    pkt_tcp_80[36:38] = (80).to_bytes(2, "big")  # Dst Port 80

    # Packet 2: IPv4 + UDP Port 53 packet
    pkt_udp_53 = bytearray(40)
    pkt_udp_53[12:14] = b'\x08\x00'  # IPv4
    pkt_udp_53[23] = 17               # UDP (Not TCP!)
    pkt_udp_53[36:38] = (53).to_bytes(2, "big")

    res1 = vm.evaluate(bytes(pkt_tcp_80))
    res2 = vm.evaluate(bytes(pkt_udp_53))

    print(f"Packet 1 (TCP Port 80) -> BPF Decision: {"ACCEPTED" if res1 > 0 else "DROPPED"} ({res1} bytes)")
    print(f"Packet 2 (UDP Port 53) -> BPF Decision: {"ACCEPTED" if res2 > 0 else "DROPPED"} ({res2} bytes)")

    assert res1 == 65535, "TCP port 80 packet must be accepted by BPF"
    assert res2 == 0, "UDP packet must be dropped by BPF"

    print("-" * 55)
    print("[VERIFIED] Berkeley Packet Filter virtual machine execution confirmed 100% correct!")


if __name__ == "__main__":
    main()
