#!/usr/bin/env python3
"""
Day 36 Lab: Bidirectional Stream Relay Simulator (mini-socat)
Simulates connecting two arbitrary endpoints (UNIX socket <-> TCP socket)
and relaying full-duplex byte streams via a non-blocking event loop.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple


@dataclass
class MockDuplexStream:
    name: str
    endpoint_type: str  # 'UNIX_SOCKET' or 'TCP_SOCKET'
    outgoing_buffer: bytearray = field(default_factory=bytearray)
    incoming_buffer: bytearray = field(default_factory=bytearray)
    is_closed: bool = False

    def send(self, data: bytes):
        """Application writes data to this endpoint to be transmitted."""
        if not self.is_closed:
            self.outgoing_buffer.extend(data)

    def recv(self, max_bytes: int = 4096) -> bytes:
        """Application reads data that has arrived at this endpoint."""
        if not self.incoming_buffer:
            return b""
        chunk = bytes(self.incoming_buffer[:max_bytes])
        del self.incoming_buffer[:max_bytes]
        return chunk


class SocatRelayEngine:
    def __init__(self, left: MockDuplexStream, right: MockDuplexStream):
        self.left = left
        self.right = right
        self.total_bytes_relayed = 0

    def step_relay(self) -> int:
        """Executes one pass of the event loop relaying data bidirectionally."""
        bytes_moved = 0

        # Left Outgoing -> Right Incoming
        if self.left.outgoing_buffer:
            chunk = bytes(self.left.outgoing_buffer)
            self.left.outgoing_buffer.clear()
            self.right.incoming_buffer.extend(chunk)
            bytes_moved += len(chunk)

        # Right Outgoing -> Left Incoming
        if self.right.outgoing_buffer:
            chunk = bytes(self.right.outgoing_buffer)
            self.right.outgoing_buffer.clear()
            self.left.incoming_buffer.extend(chunk)
            bytes_moved += len(chunk)

        self.total_bytes_relayed += bytes_moved
        return bytes_moved


def main():
    print("====================================================")
    print("DAY 36: BIDIRECTIONAL STREAM RELAY (MINI-SOCAT)")
    print("====================================================")

    unix_sock = MockDuplexStream("/var/run/docker.sock", "UNIX_SOCKET")
    tcp_sock = MockDuplexStream("127.0.0.1:2375", "TCP_SOCKET")

    relay = SocatRelayEngine(unix_sock, tcp_sock)

    print(f"Relay bridged: {unix_sock.name} <===> {tcp_sock.name}\n")

    # Step 1: TCP Client sends Docker API HTTP GET
    client_request = b"GET /v1.41/containers/json HTTP/1.1\r\nHost: localhost\r\n\r\n"
    tcp_sock.send(client_request)
    print(f"1. TCP Client writes {len(client_request)} bytes to {tcp_sock.name}")

    # Relay forwards TCP -> UNIX
    moved1 = relay.step_relay()
    print(f"2. Socat relay moved {moved1} bytes to {unix_sock.name}")
    received_by_unix = unix_sock.recv()
    assert received_by_unix == client_request, "UNIX socket should receive client request"

    # Step 2: Daemon replies with JSON payload over UNIX socket
    daemon_response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n[]"
    unix_sock.send(daemon_response)
    print(f"3. Docker daemon writes {len(daemon_response)} bytes to {unix_sock.name}")

    # Relay forwards UNIX -> TCP
    moved2 = relay.step_relay()
    print(f"4. Socat relay moved {moved2} bytes back to {tcp_sock.name}")
    received_by_tcp = tcp_sock.recv()
    assert received_by_tcp == daemon_response, "TCP client should receive daemon response"

    print("-" * 55)
    print(f"Total Traffic Relayed : {relay.total_bytes_relayed} bytes")
    assert relay.total_bytes_relayed == len(client_request) + len(daemon_response)
    print("[VERIFIED] Full-duplex stream relay operational at 100% fidelity!")


if __name__ == "__main__":
    main()
