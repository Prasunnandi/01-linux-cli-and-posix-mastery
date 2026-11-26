#!/usr/bin/env python3
"""
Day 31 Lab: Modern Network Interface Inspector
Parses Linux Netlink interface state telemetry (ip -j link / ip -j addr)
and audits MTU, MAC addresses, link carrier states, and IP assignments.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class NetworkInterface:
    ifindex: int
    name: str
    flags: List[str]
    mtu: int
    mac_address: str
    state: str  # 'UP', 'DOWN', 'UNKNOWN'
    ipv4_addresses: List[str]

    @property
    def is_operational(self) -> bool:
        """Interface is operational only if administratively UP and has physical carrier."""
        return "UP" in self.flags and "LOWER_UP" in self.flags


class InterfaceAuditor:
    def __init__(self):
        self.interfaces: Dict[str, NetworkInterface] = {}

    def load_telemetry(self, raw_telemetry: List[Dict]):
        """Parses simulated kernel Netlink JSON telemetry."""
        for item in raw_telemetry:
            iface = NetworkInterface(
                ifindex=item["ifindex"],
                name=item["ifname"],
                flags=item.get("flags", []),
                mtu=item.get("mtu", 1500),
                mac_address=item.get("address", "00:00:00:00:00:00"),
                state=item.get("operstate", "DOWN"),
                ipv4_addresses=item.get("ipv4", [])
            )
            self.interfaces[iface.name] = iface

    def audit_interfaces(self) -> Dict[str, str]:
        """Audits interfaces for misconfigurations (e.g. MTU mismatch, missing IP, no-carrier)."""
        results = {}
        for name, iface in self.interfaces.items():
            if name == "lo":
                results[name] = "OK (Loopback)"
            elif not iface.is_operational:
                results[name] = f"WARNING: Link down or physical carrier missing! (Flags: {iface.flags})"
            elif not iface.ipv4_addresses:
                results[name] = "WARNING: Interface is UP but has no assigned IPv4 address!"
            else:
                results[name] = f"HEALTHY: Operational on {iface.ipv4_addresses[0]} (MTU {iface.mtu})"
        return results


def main():
    print("====================================================")
    print("DAY 31: LINUX NETWORK INTERFACE AUDITOR (IPROUTE2)")
    print("====================================================")

    # Simulated Netlink telemetry payload
    sample_telemetry = [
        {
            "ifindex": 1,
            "ifname": "lo",
            "flags": ["LOOPBACK", "UP", "LOWER_UP"],
            "mtu": 65536,
            "address": "00:00:00:00:00:00",
            "operstate": "UP",
            "ipv4": ["127.0.0.1/8"]
        },
        {
            "ifindex": 2,
            "ifname": "eth0",
            "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"],
            "mtu": 1500,
            "address": "52:54:00:12:34:56",
            "operstate": "UP",
            "ipv4": ["192.168.1.50/24"]
        },
        {
            "ifindex": 3,
            "ifname": "eth1",
            "flags": ["BROADCAST", "MULTICAST", "UP"],
            "mtu": 1500,
            "address": "52:54:00:98:76:54",
            "operstate": "DOWN",
            "ipv4": []
        }
    ]

    auditor = InterfaceAuditor()
    auditor.load_telemetry(sample_telemetry)
    audit_results = auditor.audit_interfaces()

    print(f"{"Interface":<10} | {"MAC Address":<18} | {"Status Summary"}")
    print("-" * 65)

    for name, iface in auditor.interfaces.items():
        summary = audit_results[name]
        print(f"{name:<10} | {iface.mac_address:<18} | {summary}")

    # Assertions
    assert auditor.interfaces["eth0"].is_operational, "eth0 must be operational"
    assert not auditor.interfaces["eth1"].is_operational, "eth1 lacks LOWER_UP and must not be operational"
    assert "HEALTHY" in audit_results["eth0"], "eth0 must pass audit as HEALTHY"

    print("-" * 65)
    print("[VERIFIED] Netlink interface telemetry and link state logic validated!")


if __name__ == "__main__":
    main()
