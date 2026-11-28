"""
Day 58: nftables Virtual Machine Bytecode & Set Lookup Simulator
100% pure Python standard library implementation of nftables register-based VM,
O(1) set lookups, dictionary verdict maps, and atomic ruleset commits.
"""

from dataclasses import dataclass, field
import enum
from typing import Any, Dict, List, Optional, Set, Tuple


class VMVerdict(enum.Enum):
    CONTINUE = "CONTINUE"
    ACCEPT = "ACCEPT"
    DROP = "DROP"
    REJECT = "REJECT"
    JUMP = "JUMP"


class OpCode(enum.Enum):
    LOAD_PAYLOAD = "LOAD_PAYLOAD"    # Load field into register
    CMP_EQ = "CMP_EQ"                # Compare register == value
    SET_LOOKUP = "SET_LOOKUP"        # O(1) set membership check
    VERDICT_MAP = "VERDICT_MAP"      # Dictionary lookup mapping key -> verdict
    IMMEDIATE = "IMMEDIATE"          # Set verdict register directly


@dataclass
class VMInstruction:
    op: OpCode
    reg_dest: int = 1
    field_name: Optional[str] = None
    value: Any = None
    target_set: Optional[Set[Any]] = None
    target_map: Optional[Dict[Any, VMVerdict]] = None


@dataclass
class Packet:
    src_ip: str
    dst_ip: str
    dport: int
    protocol: str


class NFTablesVM:
    """Executes compiled nftables bytecode instructions against packets."""

    def __init__(self):
        # 4 Data registers + 1 Verdict register
        self.regs: List[Any] = [None, None, None, None, None]
        self.verdict: VMVerdict = VMVerdict.CONTINUE

    def execute_rule(self, instructions: List[VMInstruction], pkt: Packet) -> VMVerdict:
        self.verdict = VMVerdict.CONTINUE

        for inst in instructions:
            if inst.op == OpCode.LOAD_PAYLOAD:
                val = getattr(pkt, inst.field_name, None)
                self.regs[inst.reg_dest] = val

            elif inst.op == OpCode.CMP_EQ:
                reg_val = self.regs[inst.reg_dest]
                if reg_val != inst.value:
                    # Mismatch: abort this rule and continue to next rule
                    return VMVerdict.CONTINUE

            elif inst.op == OpCode.SET_LOOKUP:
                reg_val = self.regs[inst.reg_dest]
                if reg_val not in inst.target_set:
                    return VMVerdict.CONTINUE

            elif inst.op == OpCode.VERDICT_MAP:
                reg_val = self.regs[inst.reg_dest]
                if reg_val in inst.target_map:
                    return inst.target_map[reg_val]
                return VMVerdict.CONTINUE

            elif inst.op == OpCode.IMMEDIATE:
                return inst.value

        return self.verdict


class NFTablesEngine:
    """Manages transactional rulesets and atomic generation commits."""

    def __init__(self):
        self.generation = 1
        # Ruleset maps chain_name -> List[List[VMInstruction]]
        self.active_ruleset: Dict[str, List[List[VMInstruction]]] = {"input": []}
        self.vm = NFTablesVM()

    def commit_transaction(self, new_ruleset: Dict[str, List[List[VMInstruction]]]):
        """Atomically swaps ruleset and increments generation counter."""
        self.active_ruleset = new_ruleset
        self.generation += 1

    def evaluate(self, chain_name: str, pkt: Packet) -> Tuple[VMVerdict, str]:
        rules = self.active_ruleset.get(chain_name, [])
        for idx, rule_bytecode in enumerate(rules):
            verdict = self.vm.execute_rule(rule_bytecode, pkt)
            if verdict != VMVerdict.CONTINUE:
                return verdict, f"Matched rule #{idx+1} in generation {self.generation}"

        return VMVerdict.DROP, "Default table policy (DROP)"


def main():
    print("=== Day 58: nftables Virtual Machine Bytecode & Set Lookup Simulator ===")

    engine = NFTablesEngine()

    # Rule 1 Bytecode: ip saddr in @blackhole drop
    # Inst 1: Load src_ip into Reg 1
    # Inst 2: Set lookup in blackhole set -> If match, drop!
    blackhole_set = {"198.51.100.25", "203.0.113.99"}
    rule_blackhole = [
        VMInstruction(OpCode.LOAD_PAYLOAD, reg_dest=1, field_name="src_ip"),
        VMInstruction(OpCode.SET_LOOKUP, reg_dest=1, target_set=blackhole_set),
        VMInstruction(OpCode.IMMEDIATE, value=VMVerdict.DROP)
    ]

    # Rule 2 Bytecode: tcp dport vmap { 22: accept, 80: accept, 443: accept, 3306: drop }
    port_vmap = {22: VMVerdict.ACCEPT, 80: VMVerdict.ACCEPT, 443: VMVerdict.ACCEPT, 3306: VMVerdict.DROP}
    rule_vmap = [
        VMInstruction(OpCode.LOAD_PAYLOAD, reg_dest=1, field_name="dport"),
        VMInstruction(OpCode.VERDICT_MAP, reg_dest=1, target_map=port_vmap)
    ]

    # Atomically commit ruleset to Generation 2
    new_rules = {"input": [rule_blackhole, rule_vmap]}
    engine.commit_transaction(new_rules)
    assert engine.generation == 2
    print(f"[*] Committed atomic transaction: Ruleset active in Generation {engine.generation}")

    # Test 1: Blacklisted IP packet -> Triggers Set Lookup -> Dropped
    bad_pkt = Packet(src_ip="198.51.100.25", dst_ip="10.0.0.1", dport=80, protocol="TCP")
    verdict, reason = engine.evaluate("input", bad_pkt)
    assert verdict == VMVerdict.DROP
    assert "Matched rule #1" in reason
    print(f"[*] Test 1 Passed: Blackhole set match successfully dropped: {reason}")

    # Test 2: Legitimate traffic to port 80 -> Triggers Dictionary VMap -> Accepted
    web_pkt = Packet(src_ip="192.168.1.50", dst_ip="10.0.0.1", dport=80, protocol="TCP")
    verdict, reason = engine.evaluate("input", web_pkt)
    assert verdict == VMVerdict.ACCEPT
    assert "Matched rule #2" in reason
    print(f"[*] Test 2 Passed: Dictionary VMap port 80 accepted: {reason}")

    # Test 3: Traffic to port 3306 (MySQL) -> Dictionary VMap -> Explicitly Dropped
    mysql_pkt = Packet(src_ip="192.168.1.50", dst_ip="10.0.0.1", dport=3306, protocol="TCP")
    verdict, reason = engine.evaluate("input", mysql_pkt)
    assert verdict == VMVerdict.DROP
    print(f"[*] Test 3 Passed: Dictionary VMap port 3306 explicitly dropped: {reason}")

    # Test 4: Unmapped port 8080 -> Falls through to default DROP
    other_pkt = Packet(src_ip="192.168.1.50", dst_ip="10.0.0.1", dport=8080, protocol="TCP")
    verdict, reason = engine.evaluate("input", other_pkt)
    assert verdict == VMVerdict.DROP
    assert "Default table policy" in reason
    print(f"[*] Test 4 Passed: Unmapped port 8080 dropped by default policy: {reason}")

    print("All nftables VM Bytecode Simulator assertions passed successfully!")


if __name__ == "__main__":
    main()
