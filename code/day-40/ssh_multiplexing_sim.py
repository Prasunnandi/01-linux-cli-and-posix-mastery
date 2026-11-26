#!/usr/bin/env python3
"""
Day 40 Lab: OpenSSH ControlMaster & Multiplexing Simulator
Simulates the lifecycle of SSH connection multiplexing:
- Master connection establishment and UNIX domain socket creation
- Multiplexing subsequent sessions over the active master (zero handshake delay!)
- ControlPersist daemonization and idle timeout cleanup
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MultiplexedSession:
    session_id: int
    command: str
    created_at: float
    handshake_latency_ms: float


class OpenSSHControlMaster:
    def __init__(self, host: str, control_path: str, persist_timeout_s: float = 2.0):
        self.host = host
        self.control_path = control_path
        self.persist_timeout_s = persist_timeout_s
        self.is_master_active = False
        self.last_activity = 0.0
        self.active_sessions: Dict[int, MultiplexedSession] = {}
        self.session_counter = 0

    def start_master(self):
        """Establishes master TCP connection (pays full 500ms handshake cost once)."""
        self.is_master_active = True
        self.last_activity = time.time()

    def execute_command(self, cmd: str) -> MultiplexedSession:
        """
        Executes a remote command:
        - If master is active, joins over existing socket (latency: ~2ms).
        - If master is dead, spawns new master (latency: ~500ms).
        """
        self.session_counter += 1
        now = time.time()

        # Check for ControlPersist timeout
        if self.is_master_active and not self.active_sessions:
            if (now - self.last_activity) > self.persist_timeout_s:
                # Master timed out and exited!
                self.is_master_active = False

        if not self.is_master_active:
            # Cold connection: Full TCP + KEX + Auth handshake!
            self.start_master()
            latency = 500.0  # Simulated 500ms cold handshake
        else:
            # Warm multiplexed connection: Instant local UNIX socket attach!
            latency = 2.0    # Simulated 2ms multiplexed attach

        session = MultiplexedSession(
            session_id=self.session_counter,
            command=cmd,
            created_at=now,
            handshake_latency_ms=latency
        )
        self.active_sessions[session.session_id] = session
        self.last_activity = now
        return session

    def close_session(self, session_id: int):
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            self.last_activity = time.time()


def main():
    print("====================================================")
    print("DAY 40: OPENSSH CONTROLMASTER MULTIPLEXING SIMULATOR")
    print("====================================================")

    master = OpenSSHControlMaster(
        host="prod-web01.corp.internal",
        control_path="/tmp/ssh-ctrl-admin@prod-web01:22",
        persist_timeout_s=1.0  # 1-second timeout for quick testing
    )

    print(f"Target Host  : {master.host}")
    print(f"ControlPath  : {master.control_path}\n")

    # Command 1: Cold start (spawns master)
    s1 = master.execute_command("uptime")
    print(f"Command 1 ('{s1.command}') -> Handshake Latency: {s1.handshake_latency_ms} ms (COLD MASTER)")
    assert s1.handshake_latency_ms == 500.0
    master.close_session(s1.session_id)

    # Command 2: Warm multiplexed (reuses active master!)
    s2 = master.execute_command("df -h")
    print(f"Command 2 ('{s2.command}')   -> Handshake Latency: {s2.handshake_latency_ms} ms (MULTIPLEXED REUSE!)")
    assert s2.handshake_latency_ms == 2.0
    master.close_session(s2.session_id)

    # Command 3: Warm multiplexed
    s3 = master.execute_command("free -m")
    print(f"Command 3 ('{s3.command}') -> Handshake Latency: {s3.handshake_latency_ms} ms (MULTIPLEXED REUSE!)")
    assert s3.handshake_latency_ms == 2.0
    master.close_session(s3.session_id)

    # Let ControlPersist timeout expire (sleep 1.2s > 1.0s)
    print("\nSimulating 1.2s idle gap (ControlPersist timeout)...")
    time.sleep(1.2)

    # Command 4: Cold start again (master had expired!)
    s4 = master.execute_command("whoami")
    print(f"Command 4 ('{s4.command}') -> Handshake Latency: {s4.handshake_latency_ms} ms (MASTER EXPIRED -> RE-SPAWN)")
    assert s4.handshake_latency_ms == 500.0
    master.close_session(s4.session_id)

    print("-" * 55)
    print("[VERIFIED] OpenSSH ControlMaster connection reuse and ControlPersist lifecycle validated!")


if __name__ == "__main__":
    main()
