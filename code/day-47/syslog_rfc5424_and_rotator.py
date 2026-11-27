#!/usr/bin/env python3
"""
Day 47 Lab: RFC 5424 Syslog Protocol & Logrotate Inode Simulator
Simulates:
1. RFC 5424 wire formatting: PRI calculation, facility/severity, and structured headers.
2. Logrotate mechanics: SIGHUP atomic inode re-opening vs copytruncate data-loss race condition.
Uses Python standard library only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


FACILITY_MAP = {
    "kern": 0, "user": 1, "mail": 2, "daemon": 3,
    "auth": 4, "syslog": 5, "local0": 16, "local7": 23
}

SEVERITY_MAP = {
    "emerg": 0, "alert": 1, "crit": 2, "err": 3,
    "warning": 4, "notice": 5, "info": 6, "debug": 7
}


class SyslogRFC5424:
    @staticmethod
    def calculate_pri(facility: str, severity: str) -> int:
        fac_num = FACILITY_MAP.get(facility.lower(), 1)
        sev_num = SEVERITY_MAP.get(severity.lower(), 6)
        return (fac_num * 8) + sev_num

    @staticmethod
    def format_message(facility: str, severity: str, hostname: str, app_name: str, pid: int, msg: str) -> str:
        pri = SyslogRFC5424.calculate_pri(facility, severity)
        timestamp = "2026-11-27T02:00:00.000Z"
        # RFC 5424: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
        return f"<{pri}>1 {timestamp} {hostname} {app_name} {pid} ID42 - {msg}"


@dataclass
class SimulatedFileInode:
    inode_num: int
    data: bytearray = field(default_factory=bytearray)


class LogrotateSimulator:
    def __init__(self):
        self.next_inode = 1000
        self.active_file = SimulatedFileInode(self.next_inode)
        self.rotated_archive: Optional[SimulatedFileInode] = None

    def daemon_write(self, text: str):
        self.active_file.data.extend(text.encode('utf-8'))

    def rotate_sighup(self):
        """Standard rotation: rename active file, signal daemon (SIGHUP) to allocate new inode."""
        self.rotated_archive = self.active_file
        self.next_inode += 1
        # Daemon catches SIGHUP and opens fresh inode
        self.active_file = SimulatedFileInode(self.next_inode)

    def rotate_copytruncate(self, race_condition_write: Optional[str] = None) -> int:
        """Copytruncate rotation: copies bytes, truncates in-place. Returns bytes lost in race."""
        # 1. Copy data to archive
        self.rotated_archive = SimulatedFileInode(self.active_file.inode_num, bytearray(self.active_file.data))

        # 2. Race condition: Daemon writes data between copy and truncate!
        lost_bytes = 0
        if race_condition_write:
            self.active_file.data.extend(race_condition_write.encode('utf-8'))
            lost_bytes = len(race_condition_write.encode('utf-8'))

        # 3. Truncate active file to zero bytes
        self.active_file.data.clear()
        return lost_bytes


def main():
    print("====================================================")
    print("DAY 47: RFC 5424 SYSLOG & LOGROTATE SIMULATOR")
    print("====================================================")

    # 1. Test RFC 5424 PRI calculation
    # Facility: auth (4), Severity: crit (2) -> (4 * 8) + 2 = 34
    pri = SyslogRFC5424.calculate_pri("auth", "crit")
    assert pri == 34
    print(f"1. RFC 5424 PRI Calculation: auth.crit -> PRI={pri} (Correct)")

    syslog_msg = SyslogRFC5424.format_message("auth", "crit", "server01", "sshd", 1234, "Invalid password attempt")
    print(f"   Formatted Wire Message:\n   {syslog_msg}")
    assert syslog_msg.startswith("<34>1")

    # 2. Test Logrotate SIGHUP Atomic Rotation
    sim = LogrotateSimulator()
    sim.daemon_write("Log Line 1\nLog Line 2\n")
    initial_inode = sim.active_file.inode_num

    print("\n2. Executing SIGHUP Rotation...")
    sim.rotate_sighup()
    sim.daemon_write("Log Line 3\n")

    assert sim.rotated_archive.inode_num == initial_inode
    assert sim.active_file.inode_num != initial_inode
    assert b"Log Line 1" in sim.rotated_archive.data
    assert b"Log Line 3" in sim.active_file.data
    print(f"   [PASS] Active Inode changed from {initial_inode} to {sim.active_file.inode_num}. Zero data loss.")

    # 3. Test Copytruncate Race Condition Data Loss
    print("\n3. Demonstrating Copytruncate Race Condition...")
    sim2 = LogrotateSimulator()
    sim2.daemon_write("Transaction A\n")
    lost = sim2.rotate_copytruncate(race_condition_write="Transaction B (Mid-race)\n")

    print(f"   Bytes lost during copytruncate window: {lost} bytes!")
    assert lost > 0
    assert b"Transaction B" not in sim2.rotated_archive.data
    assert b"Transaction B" not in sim2.active_file.data
    print("   [PASS] Copytruncate race condition data-loss mathematically verified!")

    print("\n[VERIFIED] Syslog and Logrotate simulation passed all tests with 100% fidelity!")


if __name__ == "__main__":
    main()
