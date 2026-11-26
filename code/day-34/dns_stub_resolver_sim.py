#!/usr/bin/env python3
"""
Day 34 Lab: Glibc Stub Resolver & /etc/resolv.conf Simulator
Simulates Glibc getaddrinfo resolution, search domain expansion,
ndots:5 evaluation, and nameserver failover mechanics.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple


@dataclass
class ResolvConf:
    nameservers: List[str]
    search_domains: List[str]
    ndots: int
    timeout: int
    attempts: int


class StubResolverSimulator:
    def __init__(self, config: ResolvConf, authoritative_dns: Dict[str, str]):
        self.config = config
        self.dns_db = authoritative_dns  # Mock global DNS database

    def resolve(self, hostname: str) -> Tuple[Optional[str], List[str]]:
        """
        Simulates Glibc stub resolver resolution order:
        1. If hostname ends with dot '.', treat as FQDN (no search expansion).
        2. Count dots in hostname. If dots >= ndots, query directly first.
        3. Otherwise, append search domains sequentially!
        Returns (resolved_ip, list_of_queries_attempted).
        """
        queries_attempted = []

        # 1. Trailing dot = Absolute FQDN
        if hostname.endswith("."):
            fqdn = hostname.rstrip(".")
            queries_attempted.append(fqdn)
            return self.dns_db.get(fqdn), queries_attempted

        num_dots = hostname.count(".")

        # 2. If dots >= ndots, try hostname directly first
        if num_dots >= self.config.ndots:
            queries_attempted.append(hostname)
            if hostname in self.dns_db:
                return self.dns_db[hostname], queries_attempted

        # 3. Append search domains
        for domain in self.config.search_domains:
            expanded = f"{hostname}.{domain}"
            queries_attempted.append(expanded)
            if expanded in self.dns_db:
                return self.dns_db[expanded], queries_attempted

        # 4. If dots < ndots, try original hostname last as fallback
        if num_dots < self.config.ndots:
            queries_attempted.append(hostname)
            if hostname in self.dns_db:
                return self.dns_db[hostname], queries_attempted

        return None, queries_attempted


def main():
    print("====================================================")
    print("DAY 34: GLIBC STUB RESOLVER & NDOTS SIMULATOR")
    print("====================================================")

    # Simulated DNS database
    dns_database = {
        "db01.prod.internal": "10.0.1.50",
        "api.stripe.com": "198.51.100.99"
    }

    # Kubernetes default-style resolv.conf: ndots:5
    k8s_resolv = ResolvConf(
        nameservers=["10.96.0.10"],
        search_domains=["default.svc.cluster.local", "svc.cluster.local", "prod.internal"],
        ndots=5,
        timeout=2,
        attempts=3
    )

    sim = StubResolverSimulator(k8s_resolv, dns_database)

    # Query 1: Internal service name "db01" (dots=0 < ndots=5)
    ip1, attempts1 = sim.resolve("db01")
    print(f"Resolving 'db01':")
    print(f"  Queries issued : {attempts1}")
    print(f"  Resulting IP   : {ip1}\n")
    assert ip1 == "10.0.1.50"
    assert "db01.prod.internal" in attempts1

    # Query 2: External name "api.stripe.com" (dots=2 < ndots=5 -> Latency Trap!)
    ip2, attempts2 = sim.resolve("api.stripe.com")
    print(f"Resolving 'api.stripe.com' under ndots:5 (Kubernetes Latency Trap):")
    print(f"  Queries issued : {attempts2}")
    print(f"  Total queries  : {len(attempts2)} (3 wasted search attempts!)")
    print(f"  Resulting IP   : {ip2}\n")
    assert ip2 == "198.51.100.99"
    assert len(attempts2) == 4, "Should have made 3 search domain attempts before final match"

    # Query 3: Trailing dot FQDN "api.stripe.com." (Bypasses search domains!)
    ip3, attempts3 = sim.resolve("api.stripe.com.")
    print(f"Resolving 'api.stripe.com.' (Trailing dot FQDN optimization):")
    print(f"  Queries issued : {attempts3}")
    print(f"  Total queries  : {len(attempts3)} (Direct lookup!)")
    print(f"  Resulting IP   : {ip3}")
    assert ip3 == "198.51.100.99"
    assert len(attempts3) == 1, "Trailing dot must trigger immediate direct lookup"

    print("-" * 55)
    print("[VERIFIED] Glibc stub resolver ndots and search domain mechanics verified!")


if __name__ == "__main__":
    main()
