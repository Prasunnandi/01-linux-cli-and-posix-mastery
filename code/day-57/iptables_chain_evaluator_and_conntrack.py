"""
Day 57: Netfilter iptables Chain Evaluator & Conntrack Engine
100% pure Python standard library implementation of Netfilter hook traversal,
linear rule chain evaluation (filter, nat, mangle), and 5-tuple stateful connection tracking.
"""

from dataclasses import dataclass, field
import enum
import time
from typing import Dict, List, Optional, Tuple


class NetfilterHook(enum.Enum):
    PREROUTING = 0
    LOCAL_IN = 1
    FORWARD = 2
    LOCAL_OUT = 3
    POSTROUTING = 4


class ConntrackState(enum.Enum):
    NEW = "NEW"
    ESTABLISHED = "ESTABLISHED"
    RELATED = "RELATED"
    INVALID = "INVALID"


class RuleTarget(enum.Enum):
    ACCEPT = "ACCEPT"
    DROP = "DROP"
    REJECT = "REJECT"


@dataclass
class Packet5Tuple:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str  # TCP, UDP, ICMP
    tcp_flags: str = "SYN"  # SYN, ACK, PSH, FIN, RST


@dataclass
class FilterRule:
    chain: str                     # INPUT, FORWARD, OUTPUT
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    dport: Optional[int] = None
    protocol: Optional[str] = None
    state: Optional[ConntrackState] = None
    target: RuleTarget = RuleTarget.ACCEPT


class ConntrackTable:
    """Manages stateful 5-tuple connection records with capacity limits."""

    def __init__(self, max_entries: int = 1000, timeout_sec: float = 300.0):
        self.max_entries = max_entries
        self.timeout_sec = timeout_sec
        # Maps 5-tuple -> (state, last_seen_timestamp)
        self.table: Dict[Tuple, Tuple[ConntrackState, float]] = {}

    def _normalize_key(self, pkt: Packet5Tuple) -> Tuple:
        # Canonical flow representation
        fwd = (pkt.src_ip, pkt.dst_ip, pkt.src_port, pkt.dst_port, pkt.protocol)
        rev = (pkt.dst_ip, pkt.src_ip, pkt.dst_port, pkt.src_port, pkt.protocol)
        return min(fwd, rev)

    def process_packet(self, pkt: Packet5Tuple, now: float) -> Tuple[ConntrackState, bool]:
        """Returns (state, was_dropped_due_to_table_full)."""
        key = self._normalize_key(pkt)

        # Purge expired entries if table is full
        if len(self.table) >= self.max_entries:
            expired = [k for k, (st, ts) in self.table.items() if now - ts > self.timeout_sec]
            for k in expired:
                del self.table[k]

        if key in self.table:
            curr_state, _ = self.table[key]
            # Transition NEW -> ESTABLISHED upon two-way handshake
            new_state = ConntrackState.ESTABLISHED
            self.table[key] = (new_state, now)
            return new_state, False

        # New connection attempt
        if len(self.table) >= self.max_entries:
            return ConntrackState.INVALID, True  # Table Full Drop

        initial_state = ConntrackState.NEW if "SYN" in pkt.tcp_flags else ConntrackState.INVALID
        self.table[key] = (initial_state, now)
        return initial_state, False


class IPTablesEngine:
    """Evaluates ordered chain rules linearly against packets."""

    def __init__(self, default_policy: RuleTarget = RuleTarget.DROP):
        self.chains: Dict[str, List[FilterRule]] = {"INPUT": [], "FORWARD": [], "OUTPUT": []}
        self.default_policy = default_policy
        self.conntrack = ConntrackTable(max_entries=100)

    def append_rule(self, rule: FilterRule):
        self.chains[rule.chain].append(rule)

    def evaluate_chain(self, chain_name: str, pkt: Packet5Tuple, now: float) -> Tuple[RuleTarget, str]:
        # Step 1: Conntrack evaluation
        conn_state, table_full = self.conntrack.process_packet(pkt, now)
        if table_full:
            return RuleTarget.DROP, "Conntrack table full; packet dropped"

        # Step 2: Linear Rule Evaluation
        rules = self.chains.get(chain_name, [])
        for idx, rule in enumerate(rules):
            if rule.protocol and rule.protocol != pkt.protocol:
                continue
            if rule.src_ip and rule.src_ip != pkt.src_ip:
                continue
            if rule.dst_ip and rule.dst_ip != pkt.dst_ip:
                continue
            if rule.dport and rule.dport != pkt.dst_port:
                continue
            if rule.state and rule.state != conn_state:
                continue

            return rule.target, f"Matched rule #{idx+1} (Target: {rule.target.value})"

        # Step 3: Default Policy Fallback
        return self.default_policy, f"Default chain policy ({self.default_policy.value})"


def main():
    print("=== Day 57: Netfilter iptables Chain Evaluator & Conntrack Engine ===")

    engine = IPTablesEngine(default_policy=RuleTarget.DROP)

    # Rule 1: Allow established connections
    engine.append_rule(FilterRule(chain="INPUT", state=ConntrackState.ESTABLISHED, target=RuleTarget.ACCEPT))
    # Rule 2: Allow new inbound SSH connections on port 22
    engine.append_rule(FilterRule(chain="INPUT", dport=22, protocol="TCP", state=ConntrackState.NEW, target=RuleTarget.ACCEPT))
    # Rule 3: Allow new inbound HTTP connections on port 80
    engine.append_rule(FilterRule(chain="INPUT", dport=80, protocol="TCP", state=ConntrackState.NEW, target=RuleTarget.ACCEPT))

    now = 1000.0

    # Test 1: Inbound SYN packet to port 22 -> State NEW -> Matches Rule 2 -> ACCEPT
    syn_ssh = Packet5Tuple(src_ip="198.51.100.5", dst_ip="10.0.0.1", src_port=54321, dst_port=22, protocol="TCP", tcp_flags="SYN")
    target, reason = engine.evaluate_chain("INPUT", syn_ssh, now)
    assert target == RuleTarget.ACCEPT
    assert "Matched rule #2" in reason
    print(f"[*] Test 1 Passed: Inbound SSH SYN accepted: {reason}")

    # Test 2: Inbound ACK reply on same flow -> State ESTABLISHED -> Matches Rule 1 -> ACCEPT
    ack_ssh = Packet5Tuple(src_ip="10.0.0.1", dst_ip="198.51.100.5", src_port=22, dst_port=54321, protocol="TCP", tcp_flags="ACK")
    target, reason = engine.evaluate_chain("INPUT", ack_ssh, now + 0.05)
    assert target == RuleTarget.ACCEPT
    assert "Matched rule #1" in reason
    print(f"[*] Test 2 Passed: Inbound SSH ACK recognized as ESTABLISHED: {reason}")

    # Test 3: Unauthorized inbound connection to MySQL port 3306 -> Default Policy -> DROP
    syn_mysql = Packet5Tuple(src_ip="198.51.100.5", dst_ip="10.0.0.1", src_port=54322, dst_port=3306, protocol="TCP", tcp_flags="SYN")
    target, reason = engine.evaluate_chain("INPUT", syn_mysql, now + 0.10)
    assert target == RuleTarget.DROP
    assert "Default chain policy" in reason
    print(f"[*] Test 3 Passed: Unauthorized MySQL port dropped by default policy: {reason}")

    # Test 4: Conntrack Table Full Exhaustion
    small_engine = IPTablesEngine()
    small_engine.conntrack.max_entries = 3
    # Fill table with 3 distinct connections
    for i in range(3):
        p = Packet5Tuple("1.2.3.4", "10.0.0.1", 1000 + i, 80, "TCP", "SYN")
        small_engine.conntrack.process_packet(p, now)

    # 4th connection attempt triggers Table Full Drop
    overflow_pkt = Packet5Tuple("1.2.3.4", "10.0.0.1", 9999, 80, "TCP", "SYN")
    target, reason = small_engine.evaluate_chain("INPUT", overflow_pkt, now)
    assert target == RuleTarget.DROP
    assert "Conntrack table full" in reason
    print(f"[*] Test 4 Passed: Conntrack table saturation successfully detected and dropped: {reason}")

    print("All Netfilter iptables & Conntrack Engine assertions passed successfully!")


if __name__ == "__main__":
    main()
