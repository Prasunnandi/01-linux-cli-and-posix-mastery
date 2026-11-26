#!/usr/bin/env python3
"""
Day 32 Lab: Kernel Routing Table Longest Prefix Match (LPM)
Implements the core Linux Forwarding Information Base (FIB) algorithm
using 32-bit integer bitmasks to select the most specific route.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


def ip_to_int(ip_str: str) -> int:
    """Converts dotted-decimal IPv4 string (e.g. '192.168.1.1') to 32-bit unsigned integer."""
    octets = [int(o) for o in ip_str.split(".")]
    return (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]


def int_to_ip(ip_int: int) -> str:
    """Converts 32-bit integer back to dotted-decimal IPv4 string."""
    return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"


@dataclass
class RouteEntry:
    destination_cidr: str
    gateway: Optional[str]
    interface: str
    metric: int
    net_int: int
    mask_int: int
    prefix_len: int


class LinuxFIB:
    def __init__(self):
        self.routes: List[RouteEntry] = []

    def add_route(self, cidr: str, gateway: Optional[str], interface: str, metric: int = 100):
        if cidr == "default" or cidr == "0.0.0.0/0":
            net_str, prefix_len = "0.0.0.0", 0
        else:
            net_str, prefix_len_str = cidr.split("/")
            prefix_len = int(prefix_len_str)

        net_int = ip_to_int(net_str)
        # Compute 32-bit netmask
        mask_int = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF if prefix_len > 0 else 0

        route = RouteEntry(
            destination_cidr=cidr,
            gateway=gateway,
            interface=interface,
            metric=metric,
            net_int=net_int & mask_int,
            mask_int=mask_int,
            prefix_len=prefix_len
        )
        self.routes.append(route)

    def lookup(self, dst_ip_str: str) -> Optional[RouteEntry]:
        """
        Executes Longest Prefix Match (LPM):
        1. Finds all routes where (dst_ip & mask) == route_network.
        2. Selects the route with the highest prefix_len (longest prefix).
        3. Breaks ties using the lowest metric.
        """
        dst_int = ip_to_int(dst_ip_str)
        best_match: Optional[RouteEntry] = None

        for route in self.routes:
            if (dst_int & route.mask_int) == route.net_int:
                if best_match is None:
                    best_match = route
                elif route.prefix_len > best_match.prefix_len:
                    best_match = route
                elif route.prefix_len == best_match.prefix_len and route.metric < best_match.metric:
                    best_match = route

        return best_match


def main():
    print("====================================================")
    print("DAY 32: KERNEL ROUTING LONGEST PREFIX MATCH (LPM)")
    print("====================================================")

    fib = LinuxFIB()
    # Configure routing table
    fib.add_route("0.0.0.0/0", "192.168.1.1", "eth0", metric=200)      # Default Gateway
    fib.add_route("10.0.0.0/8", "172.16.0.1", "tun0", metric=100)      # Corporate VPN
    fib.add_route("10.1.2.0/24", "10.1.2.1", "eth1", metric=50)        # Specific Subnet
    fib.add_route("10.1.2.45/32", None, "eth2", metric=10)             # Direct Host Route

    test_queries = [
        ("8.8.8.8", "0.0.0.0/0", "eth0"),        # Falls back to default gateway
        ("10.5.0.1", "10.0.0.0/8", "tun0"),      # Matches /8 VPN route
        ("10.1.2.99", "10.1.2.0/24", "eth1"),    # Matches /24 over /8 (LPM!)
        ("10.1.2.45", "10.1.2.45/32", "eth2")    # Matches exact /32 host route
    ]

    print(f"{"Destination IP":<16} | {"Selected Route":<14} | {"Outgoing Dev":<12} | {"Gateway"}")
    print("-" * 65)

    for dst_ip, expected_cidr, expected_dev in test_queries:
        match = fib.lookup(dst_ip)
        assert match is not None, f"Route lookup failed for {dst_ip}"
        print(f"{dst_ip:<16} | {match.destination_cidr:<14} | {match.interface:<12} | {match.gateway or 'DIRECT'}")
        assert match.destination_cidr == expected_cidr, f"Expected {expected_cidr}, got {match.destination_cidr}"
        assert match.interface == expected_dev, f"Expected {expected_dev}, got {match.interface}"

    print("-" * 65)
    print("[VERIFIED] Linux FIB Longest Prefix Matching logic confirmed 100% accurate!")


if __name__ == "__main__":
    main()
