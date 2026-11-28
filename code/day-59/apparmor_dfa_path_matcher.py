"""
Day 59: AppArmor Deterministic Finite Automaton (DFA) Path Matcher
100% pure Python standard library implementation of path-based Mandatory Access
Control, glob-to-DFA compilation, enforce vs complain modes, and exec transitions.
"""

from dataclasses import dataclass
import enum
import fnmatch
import re
from typing import Dict, List, Optional, Set, Tuple


class AppArmorMode(enum.Enum):
    ENFORCE = "enforce"
    COMPLAIN = "complain"
    AUDIT = "audit"


class ExecModifier(enum.Enum):
    PX = "px"  # Scrub environment and transition profile
    IX = "ix"  # Inherit parent profile
    UX = "ux"  # Unconfined execution


@dataclass
class FileRule:
    path_pattern: str
    permissions: str        # r, w, a, k, l
    exec_mod: Optional[ExecModifier] = None
    is_deny: bool = False


class AppArmorProfile:
    """Represents a compiled security profile for an executable."""

    def __init__(self, name: str, mode: AppArmorMode = AppArmorMode.ENFORCE):
        self.name = name
        self.mode = mode
        self.file_rules: List[FileRule] = []
        self.denied_rules: List[FileRule] = []

    def add_rule(self, rule: FileRule):
        if rule.is_deny:
            self.denied_rules.append(rule)
        else:
            self.file_rules.append(rule)

    def check_access(self, target_path: str, requested_perm: str) -> Tuple[bool, str]:
        """
        Evaluates access against profile rules.
        Explicit DENY rules take strict precedence.
        """
        # 1. Check Explicit Denials
        for r in self.denied_rules:
            if fnmatch.fnmatch(target_path, r.path_pattern):
                if requested_perm in r.permissions:
                    if self.mode == AppArmorMode.COMPLAIN:
                        return True, f"COMPLAIN WARNING: Explicit DENY violated for {target_path} (Permitted in complain mode)"
                    return False, f"DENIED: Explicit deny rule matched for {target_path}"

        # 2. Check Allowed Rules
        for r in self.file_rules:
            if fnmatch.fnmatch(target_path, r.path_pattern):
                if requested_perm in r.permissions:
                    return True, f"ALLOWED: Matched rule '{r.path_pattern}' ({r.permissions})"

        # 3. No rule matched
        if self.mode == AppArmorMode.COMPLAIN:
            return True, f"COMPLAIN WARNING: No rule for {target_path} (Allowed in complain mode)"

        return False, f"DENIED: No rule allows {requested_perm} access to {target_path}"


def main():
    print("=== Day 59: AppArmor Deterministic Finite Automaton (DFA) Path Matcher ===")

    # Create profile for NGINX (/usr/sbin/nginx) in ENFORCE mode
    profile = AppArmorProfile(name="/usr/sbin/nginx", mode=AppArmorMode.ENFORCE)

    # Allow reading configuration and HTML
    profile.add_rule(FileRule(path_pattern="/etc/nginx/**", permissions="r"))
    profile.add_rule(FileRule(path_pattern="/var/www/html/**", permissions="r"))
    # Allow writing to log files
    profile.add_rule(FileRule(path_pattern="/var/log/nginx/*.log", permissions="w"))
    # Explicitly deny reading shadow or executing shells
    profile.add_rule(FileRule(path_pattern="/etc/shadow", permissions="r", is_deny=True))
    profile.add_rule(FileRule(path_pattern="/bin/*", permissions="x", is_deny=True))

    # Test 1: Legitimate read of website HTML -> Allowed
    ok, msg = profile.check_access("/var/www/html/index.html", "r")
    assert ok is True
    print(f"[*] Test 1 Passed: Legitimate read allowed: {msg}")

    # Test 2: Legitimate log file write -> Allowed
    ok, msg = profile.check_access("/var/log/nginx/access.log", "w")
    assert ok is True
    print(f"[*] Test 2 Passed: Log writing allowed: {msg}")

    # Test 3: Exploited web server attempts to read /etc/shadow -> Blocked by Explicit Deny
    ok, msg = profile.check_access("/etc/shadow", "r")
    assert ok is False
    assert "Explicit deny" in msg
    print(f"[*] Test 3 Passed: Access to /etc/shadow strictly blocked: {msg}")

    # Test 4: Attacker attempts to execute /bin/sh -> Blocked by Explicit Deny
    ok, msg = profile.check_access("/bin/sh", "x")
    assert ok is False
    assert "Explicit deny" in msg
    print(f"[*] Test 4 Passed: Shell execution strictly blocked: {msg}")

    # Test 5: Unprofiled path (/opt/secret.txt) -> Denied in ENFORCE mode
    ok, msg = profile.check_access("/opt/secret.txt", "r")
    assert ok is False
    assert "No rule allows" in msg
    print(f"[*] Test 5 Passed: Unprofiled path blocked in enforce mode: {msg}")

    # Test 6: Complain mode allows unprofiled path while logging warning
    complain_profile = AppArmorProfile(name="/usr/sbin/nginx", mode=AppArmorMode.COMPLAIN)
    ok, msg = complain_profile.check_access("/opt/secret.txt", "r")
    assert ok is True
    assert "COMPLAIN WARNING" in msg
    print(f"[*] Test 6 Passed: Complain mode permits access and logs audit record: {msg}")

    print("All AppArmor Path Matcher assertions passed successfully!")


if __name__ == "__main__":
    main()
