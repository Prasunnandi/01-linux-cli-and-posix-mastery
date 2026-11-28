"""
Day 60: SELinux Type Enforcement & Access Vector Cache (AVC) Engine
100% pure Python standard library implementation of Flask security contexts,
Type Enforcement policy rules, Access Vector Cache (AVC), and Multi-Category Security (MCS).
"""

from dataclasses import dataclass
import time
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class SecurityContext:
    user: str
    role: str
    type_domain: str
    mls_level: str  # e.g., s0 or s0:c12,c34

    def __str__(self) -> str:
        return f"{self.user}:{self.role}:{self.type_domain}:{self.mls_level}"

    def get_categories(self) -> Set[str]:
        if ":" not in self.mls_level:
            return set()
        parts = self.mls_level.split(":")
        if len(parts) > 1:
            return set(parts[1].split(","))
        return set()


@dataclass
class AVCDecision:
    allowed: bool
    audit_allow: bool = False
    audit_deny: bool = True


class SELinuxSecurityServer:
    """Evaluates Type Enforcement rules, Booleans, and MCS category lattice."""

    def __init__(self):
        # Policy Matrix: (subject_type, object_type, target_class) -> Set[allowed_permissions]
        self.policy_matrix: Dict[Tuple[str, str, str], Set[str]] = {}
        # Booleans: name -> bool
        self.booleans: Dict[str, bool] = {}
        # Conditional Rules: boolean_name -> (key, permission)
        self.conditional_rules: Dict[str, List[Tuple[Tuple[str, str, str], str]]] = {}

    def add_allow_rule(self, subject_type: str, object_type: str, target_class: str, permissions: List[str]):
        key = (subject_type, object_type, target_class)
        if key not in self.policy_matrix:
            self.policy_matrix[key] = set()
        self.policy_matrix[key].update(permissions)

    def set_boolean(self, name: str, state: bool):
        self.booleans[name] = state

    def check_mcs_dominance(self, subject: SecurityContext, target: SecurityContext) -> bool:
        """Bell-LaPadula: Subject categories must be a superset of target categories."""
        sub_cats = subject.get_categories()
        tar_cats = target.get_categories()
        return tar_cats.issubset(sub_cats)

    def compute_decision(self, sub: SecurityContext, obj: SecurityContext, tclass: str, perm: str) -> bool:
        # 1. Multi-Category Security (MCS) check
        if not self.check_mcs_dominance(sub, obj):
            return False

        # 2. Type Enforcement (TE) check
        key = (sub.type_domain, obj.type_domain, tclass)
        allowed_perms = self.policy_matrix.get(key, set())
        if perm in allowed_perms:
            return True

        # 3. Check Dynamic Booleans
        for bool_name, active in self.booleans.items():
            if active and bool_name in self.conditional_rules:
                for cond_key, cond_perm in self.conditional_rules[bool_name]:
                    if cond_key == key and cond_perm == perm:
                        return True

        return False


class AccessVectorCache:
    """High-speed LRU kernel cache for SELinux security decisions."""

    def __init__(self, security_server: SELinuxSecurityServer, max_entries: int = 1000):
        self.server = security_server
        self.max_entries = max_entries
        # Cache key: (sub_type, obj_type, tclass, perm, mcs_hash) -> AVCDecision
        self.cache: Dict[Tuple, AVCDecision] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def reset(self):
        """Invalidates entire cache upon policy or boolean mutation."""
        self.cache.clear()

    def query(self, sub: SecurityContext, obj: SecurityContext, tclass: str, perm: str) -> Tuple[bool, str]:
        cache_key = (sub.type_domain, obj.type_domain, tclass, perm, str(sub.get_categories()), str(obj.get_categories()))

        if cache_key in self.cache:
            self.cache_hits += 1
            decision = self.cache[cache_key]
            return decision.allowed, "AVC HIT (Sub-microsecond kernel cache)"

        # Cache Miss: consult Security Server
        self.cache_misses += 1
        allowed = self.server.compute_decision(sub, obj, tclass, perm)
        decision = AVCDecision(allowed=allowed)

        if len(self.cache) >= self.max_entries:
            # Pop oldest entry (FIFO / LRU simulation)
            self.cache.pop(next(iter(self.cache)))

        self.cache[cache_key] = decision
        return allowed, "AVC MISS (Consulted policy matrix & populated cache)"


def main():
    print("=== Day 60: SELinux Type Enforcement & Access Vector Cache (AVC) Engine ===")

    server = SELinuxSecurityServer()
    avc = AccessVectorCache(server)

    # Define Security Contexts
    web_ctx = SecurityContext("system_u", "system_r", "httpd_t", "s0")
    html_ctx = SecurityContext("system_u", "object_r", "httpd_sys_content_t", "s0")
    shadow_ctx = SecurityContext("system_u", "object_r", "shadow_t", "s0")

    # Policy Rule: allow httpd_t httpd_sys_content_t : file { read open getattr };
    server.add_allow_rule("httpd_t", "httpd_sys_content_t", "file", ["read", "open", "getattr"])

    # Test 1: First request triggers AVC MISS and ALLOWS access
    allowed, reason = avc.query(web_ctx, html_ctx, "file", "read")
    assert allowed is True
    assert "AVC MISS" in reason
    assert avc.cache_misses == 1
    print(f"[*] Test 1 Passed: Initial query populated cache: {reason}")

    # Test 2: Second identical request triggers AVC HIT
    allowed, reason = avc.query(web_ctx, html_ctx, "file", "read")
    assert allowed is True
    assert "AVC HIT" in reason
    assert avc.cache_hits == 1
    print(f"[*] Test 2 Passed: Repeated query resolved from cache: {reason}")

    # Test 3: Web server attempts to read shadow_t -> DENIED
    allowed, reason = avc.query(web_ctx, shadow_ctx, "file", "read")
    assert allowed is False
    print(f"[*] Test 3 Passed: Unauthorized read of shadow_t denied by Type Enforcement policy")

    # Test 4: Dynamic Boolean mutation (httpd_can_network_connect)
    db_ctx = SecurityContext("system_u", "object_r", "mysqld_port_t", "s0")
    cond_key = ("httpd_t", "mysqld_port_t", "tcp_socket")
    server.conditional_rules["httpd_can_network_connect"] = [(cond_key, "name_connect")]

    # Initially boolean is OFF -> Connection denied
    server.set_boolean("httpd_can_network_connect", False)
    allowed, _ = avc.query(web_ctx, db_ctx, "tcp_socket", "name_connect")
    assert allowed is False

    # Flip boolean ON -> Invalidates AVC cache -> Connection allowed!
    server.set_boolean("httpd_can_network_connect", True)
    avc.reset()
    allowed, reason = avc.query(web_ctx, db_ctx, "tcp_socket", "name_connect")
    assert allowed is True
    print(f"[*] Test 4 Passed: SELinux Boolean dynamically enabled database connection: {reason}")

    # Test 5: Multi-Category Security (MCS) Container Isolation
    c1_ctx = SecurityContext("system_u", "system_r", "container_t", "s0:c12,c34")
    c2_ctx = SecurityContext("system_u", "system_r", "container_t", "s0:c56,c78")
    vol1_ctx = SecurityContext("system_u", "object_r", "container_file_t", "s0:c12,c34")
    server.add_allow_rule("container_t", "container_file_t", "file", ["read"])

    # Container 1 matches categories (c12, c34) -> Allowed
    allowed, _ = avc.query(c1_ctx, vol1_ctx, "file", "read")
    assert allowed is True

    # Container 2 possesses different categories (c56, c78) -> Rejected by MCS dominance!
    allowed, _ = avc.query(c2_ctx, vol1_ctx, "file", "read")
    assert allowed is False
    print("[*] Test 5 Passed: MCS Category lattice successfully isolated container volumes")

    print("All SELinux Type Enforcement & AVC Engine assertions passed successfully!")


if __name__ == "__main__":
    main()
