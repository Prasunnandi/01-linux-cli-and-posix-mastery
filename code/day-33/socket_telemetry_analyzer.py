#!/usr/bin/env python3
"""
Day 33 Lab: Socket Telemetry & Backlog Analyzer
Simulates Linux kernel inet_diag socket statistics (ss -tulpn)
to detect listen backlog saturation and stalled TCP send buffers.
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class SocketEntry:
    protocol: str
    state: str       # 'LISTEN', 'ESTABLISHED', 'TIME_WAIT', 'CLOSE_WAIT'
    recv_q: int      # For LISTEN: pending accept connections. For ESTABLISHED: unread bytes in buffer.
    send_q: int      # For LISTEN: max backlog capacity. For ESTABLISHED: unacked bytes in flight.
    local_address: str
    local_port: int
    peer_address: str
    peer_port: int
    process_name: str
    pid: int

    @property
    def is_backlog_saturated(self) -> bool:
        """On a listening socket, backlog is saturated if Recv-Q exceeds Send-Q."""
        return self.state == "LISTEN" and self.recv_q >= self.send_q


class SocketAuditor:
    def __init__(self):
        self.sockets: List[SocketEntry] = []

    def load_telemetry(self, raw_entries: List[Dict]):
        for e in raw_entries:
            self.sockets.append(SocketEntry(**e))

    def detect_overloaded_servers(self) -> List[SocketEntry]:
        """Detects servers dropping connections due to saturated listen queues."""
        return [s for s in self.sockets if s.is_backlog_saturated]

    def detect_stalled_senders(self, threshold_bytes: int = 50000) -> List[SocketEntry]:
        """Detects established connections where send buffer is bloated (receiver not acking)."""
        return [s for s in self.sockets if s.state == "ESTABLISHED" and s.send_q >= threshold_bytes]


def main():
    print("====================================================")
    print("DAY 33: LINUX SOCKET TELEMETRY AUDITOR (SS/INET_DIAG)")
    print("====================================================")

    sample_sockets = [
        {
            "protocol": "tcp", "state": "LISTEN", "recv_q": 0, "send_q": 128,
            "local_address": "0.0.0.0", "local_port": 22,
            "peer_address": "0.0.0.0", "peer_port": 0,
            "process_name": "sshd", "pid": 945
        },
        {
            "protocol": "tcp", "state": "LISTEN", "recv_q": 135, "send_q": 128,  # OVERFLOW!
            "local_address": "127.0.0.1", "local_port": 5432,
            "peer_address": "0.0.0.0", "peer_port": 0,
            "process_name": "postgres", "pid": 1240
        },
        {
            "protocol": "tcp", "state": "ESTABLISHED", "recv_q": 0, "send_q": 65536,  # STALLED SENDER!
            "local_address": "192.168.1.50", "local_port": 45120,
            "peer_address": "203.0.113.1", "peer_port": 443,
            "process_name": "backup_uploader", "pid": 3410
        }
    ]

    auditor = SocketAuditor()
    auditor.load_telemetry(sample_sockets)

    overloaded = auditor.detect_overloaded_servers()
    stalled = auditor.detect_stalled_senders(50000)

    print(f"{"State":<12} | {"Local Socket":<22} | {"Recv-Q":<8} | {"Send-Q":<8} | {"Process / Health"}")
    print("-" * 75)

    for s in auditor.sockets:
        local = f"{s.local_address}:{s.local_port}"
        health = "HEALTHY"
        if s in overloaded:
            health = "CRITICAL: Backlog Overflow! (Dropping SYNs)"
        elif s in stalled:
            health = f"WARNING: Stalled Send Buffer ({s.send_q} bytes)"
        print(f"{s.state:<12} | {local:<22} | {s.recv_q:<8} | {s.send_q:<8} | {s.process_name} -> {health}")

    assert len(overloaded) == 1, "Should detect exactly 1 overloaded server (postgres)"
    assert overloaded[0].process_name == "postgres"
    assert len(stalled) == 1, "Should detect 1 stalled sender (backup_uploader)"

    print("-" * 75)
    print("[VERIFIED] Socket telemetry analyzer successfully diagnosed queue saturation!")


if __name__ == "__main__":
    main()
