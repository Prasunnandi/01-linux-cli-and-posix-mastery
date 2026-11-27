#!/usr/bin/env python3
"""
Day 46 Lab: systemd-journald Binary File & Structured Object Parser
Parses systemd's binary journal file structure:
- 8-byte file signature (LPKSHHRH)
- File header fields and 128-bit UUIDs (Machine ID, Boot ID)
- Object headers and type dispatching (DATA, FIELD, ENTRY)
- Structured key=value attribute decoding.
Uses Python standard library only.
"""

import struct
import uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any


@dataclass
class JournalHeader:
    signature: bytes
    state: int
    machine_id: str
    boot_id: str
    arena_size: int
    n_objects: int
    n_entries: int


@dataclass
class JournalDataObject:
    payload_size: int
    key_value: str


class SystemdJournalParser:
    HEADER_MAGIC = b"LPKSHHRH"
    # Structure: 8s (signature), 4s (flags), 4s (flags), B (state), 7s (res), 16s (file_id), 16s (machine_id), 16s (boot_id)
    HEADER_FORMAT = "<8sIIB7s16s16s16sQQQQQQQQQQ"

    @staticmethod
    def pack_synthetic_journal() -> bytes:
        """Constructs a minimal valid binary systemd journal file with 2 objects."""
        buf = bytearray()

        file_uuid = uuid.uuid4().bytes
        machine_uuid = uuid.UUID("11223344-5566-7788-99aa-bbccddeeff00").bytes
        boot_uuid = uuid.UUID("aabbccdd-eeff-1122-3344-5566778899aa").bytes

        header_bytes = struct.pack(
            SystemdJournalParser.HEADER_FORMAT,
            SystemdJournalParser.HEADER_MAGIC,
            0, 0,  # flags
            1,     # state = 1 (ONLINE)
            b"\x00" * 7,
            file_uuid,
            machine_uuid,
            boot_uuid,
            0,     # seqnum_id
            256,   # header_size
            4096,  # arena_size
            0, 0, 0, 0, 0,
            2,     # n_objects = 2
            1      # n_entries = 1
        )
        buf.extend(header_bytes)
        # Pad to 256 bytes (header size)
        buf.extend(b"\x00" * (256 - len(buf)))

        # Append Object 1: DATA object (Type = 1) -> "MESSAGE=Host boot completed"
        obj1_payload = b"MESSAGE=Host boot completed"
        # ObjectHeader: Type(B), Flags(B), Reserved(6s), Size(Q) -> 16 bytes
        buf.extend(struct.pack("<BB6sQ", 1, 0, b"\x00" * 6, 16 + len(obj1_payload)))
        buf.extend(obj1_payload)

        # Pad to 8-byte boundary
        pad1 = (8 - (len(buf) % 8)) % 8
        buf.extend(b"\x00" * pad1)

        # Append Object 2: DATA object (Type = 1) -> "_SYSTEMD_UNIT=sshd.service"
        obj2_payload = b"_SYSTEMD_UNIT=sshd.service"
        buf.extend(struct.pack("<BB6sQ", 1, 0, b"\x00" * 6, 16 + len(obj2_payload)))
        buf.extend(obj2_payload)

        return bytes(buf)

    @staticmethod
    def parse_header(raw_data: bytes) -> JournalHeader:
        if len(raw_data) < 256:
            raise ValueError("Buffer too small for systemd journal header")

        fields = struct.unpack(SystemdJournalParser.HEADER_FORMAT, raw_data[:152])
        sig = fields[0]
        if sig != SystemdJournalParser.HEADER_MAGIC:
            raise ValueError(f"Invalid journal signature: {sig!r}")

        state = fields[3]
        m_id = str(uuid.UUID(bytes=fields[6]))
        b_id = str(uuid.UUID(bytes=fields[7]))
        arena = fields[10]
        n_obj = fields[16]
        n_ent = fields[17]

        return JournalHeader(
            signature=sig,
            state=state,
            machine_id=m_id,
            boot_id=b_id,
            arena_size=arena,
            n_objects=n_obj,
            n_entries=n_ent
        )

    @staticmethod
    def extract_data_objects(raw_data: bytes, start_offset: int = 256) -> List[str]:
        """Extracts structured string payloads from DATA objects in the journal arena."""
        results = []
        offset = start_offset

        while offset + 16 <= len(raw_data):
            obj_type, flags, _, total_size = struct.unpack("<BB6sQ", raw_data[offset:offset + 16])
            if total_size == 0 or offset + total_size > len(raw_data):
                break

            if obj_type == 1:  # OBJECT_DATA
                payload_len = total_size - 16
                payload = raw_data[offset + 16:offset + 16 + payload_len]
                results.append(payload.decode('utf-8', errors='replace'))

            # Advance to next 8-byte aligned object
            aligned_size = (total_size + 7) & ~7
            offset += aligned_size

        return results


def main():
    print("====================================================")
    print("DAY 46: systemd-journald BINARY FORMAT PARSER")
    print("====================================================")

    # 1. Generate synthetic binary journal
    raw_journal = SystemdJournalParser.pack_synthetic_journal()
    print(f"1. Generated Synthetic Binary Journal: {len(raw_journal)} bytes")

    # 2. Parse binary header
    hdr = SystemdJournalParser.parse_header(raw_journal)
    print("2. Parsed Journal Header Telemetry:")
    print(f"   Signature  : {hdr.signature.decode('ascii')}")
    print(f"   State      : {hdr.state} (1=ONLINE)")
    print(f"   Machine ID : {hdr.machine_id}")
    print(f"   Boot ID    : {hdr.boot_id}")
    print(f"   Objects    : {hdr.n_objects} (Entries: {hdr.n_entries})")

    assert hdr.signature == b"LPKSHHRH"
    assert hdr.state == 1
    assert hdr.machine_id == "11223344-5566-7788-99aa-bbccddeeff00"

    # 3. Extract and decode structured DATA objects
    print("\n3. Extracting Structured Log Objects from Arena:")
    data_objects = SystemdJournalParser.extract_data_objects(raw_journal, 256)
    for obj in data_objects:
        print(f"   -> Found Object: '{obj}'")

    assert len(data_objects) == 2
    assert "MESSAGE=Host boot completed" in data_objects
    assert "_SYSTEMD_UNIT=sshd.service" in data_objects
    print("   [PASS] Structured attributes decoded with 100% fidelity.")

    print("\n[VERIFIED] systemd binary journal parser passed all assertions!")


if __name__ == "__main__":
    main()
