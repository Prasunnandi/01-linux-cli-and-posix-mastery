"""
Day 53: PAM Stack Evaluator & Control Flag Finite State Machine
100% pure Python standard library implementation of RFC 86.0 Pluggable Authentication
Modules stack traversal, required/requisite/sufficient/optional logic, and state engine.
"""

from dataclasses import dataclass
import enum
from typing import Callable, Dict, List, Optional, Tuple


class PAMControlFlag(enum.Enum):
    REQUIRED = "required"
    REQUISITE = "requisite"
    SUFFICIENT = "sufficient"
    OPTIONAL = "optional"


class PAMStatus(enum.Enum):
    SUCCESS = 0
    AUTH_ERR = 1
    USER_UNKNOWN = 2
    PERM_DENIED = 3
    ABORT = 4


@dataclass
class PAMModuleRule:
    group: str                     # auth, account, password, session
    flag: PAMControlFlag           # required, requisite, sufficient, optional
    module_name: str               # e.g., pam_unix, pam_google_authenticator
    handler: Callable[[str, Dict], PAMStatus]  # Execution function


class PAMStackEngine:
    """Evaluates PAM stacks implementing strict RFC 86.0 state machine semantics."""

    def __init__(self):
        self.services: Dict[str, List[PAMModuleRule]] = {}

    def register_service_rule(self, service: str, rule: PAMModuleRule):
        if service not in self.services:
            self.services[service] = []
        self.services[service].append(rule)

    def evaluate_stack(self, service: str, target_group: str, username: str, context: Dict) -> Tuple[bool, List[str]]:
        """
        Evaluates a service stack for a specific management group.
        Returns (success: bool, audit_trail: List[str]).
        """
        audit_trail: List[str] = []
        if service not in self.services:
            audit_trail.append(f"Service '{service}' not defined")
            return False, audit_trail

        rules = [r for r in self.services[service] if r.group == target_group]
        if not rules:
            audit_trail.append(f"No rules for group '{target_group}' in service '{service}'")
            return False, audit_trail

        required_failed = False
        sufficient_success = False

        for rule in rules:
            status = rule.handler(username, context)
            audit_trail.append(f"Executed {rule.module_name} ({rule.flag.value}) -> {status.name}")

            if rule.flag == PAMControlFlag.REQUIRED:
                if status != PAMStatus.SUCCESS:
                    required_failed = True

            elif rule.flag == PAMControlFlag.REQUISITE:
                if status != PAMStatus.SUCCESS:
                    audit_trail.append(f"REQUISITE FAILURE in {rule.module_name}: Aborting stack immediately")
                    return False, audit_trail

            elif rule.flag == PAMControlFlag.SUFFICIENT:
                if status == PAMStatus.SUCCESS and not required_failed:
                    sufficient_success = True
                    audit_trail.append(f"SUFFICIENT SUCCESS in {rule.module_name}: Terminating stack with SUCCESS")
                    return True, audit_trail

            elif rule.flag == PAMControlFlag.OPTIONAL:
                pass  # Optional does not impact outcome unless sole module

        if sufficient_success:
            return True, audit_trail

        final_verdict = not required_failed
        audit_trail.append(f"Stack completed: Final Verdict = {'SUCCESS' if final_verdict else 'FAILURE'}")
        return final_verdict, audit_trail


# Simulated PAM Modules
def mock_pam_unix(username: str, ctx: Dict) -> PAMStatus:
    if ctx.get("password") == "secret123":
        return PAMStatus.SUCCESS
    return PAMStatus.AUTH_ERR


def mock_pam_totp(username: str, ctx: Dict) -> PAMStatus:
    if ctx.get("totp_token") == "123456":
        return PAMStatus.SUCCESS
    return PAMStatus.AUTH_ERR


def mock_pam_biometric(username: str, ctx: Dict) -> PAMStatus:
    if ctx.get("fingerprint_valid") is True:
        return PAMStatus.SUCCESS
    return PAMStatus.PERM_DENIED


def main():
    print("=== Day 53: PAM Stack Evaluator & Control Flag Finite State Machine ===")

    engine = PAMStackEngine()

    # Configure Multi-Factor SSH Service:
    # 1. pam_unix (requisite): password check. If failed, abort immediately!
    # 2. pam_totp (required): secondary factor.
    engine.register_service_rule("sshd", PAMModuleRule("auth", PAMControlFlag.REQUISITE, "pam_unix", mock_pam_unix))
    engine.register_service_rule("sshd", PAMModuleRule("auth", PAMControlFlag.REQUIRED, "pam_totp", mock_pam_totp))

    # Test 1: Full multi-factor success
    ctx1 = {"password": "secret123", "totp_token": "123456"}
    ok, trail = engine.evaluate_stack("sshd", "auth", "alice", ctx1)
    assert ok is True
    print(f"[*] Test 1 Passed: Multi-factor authenticated successfully: {trail[-1]}")

    # Test 2: Requisite failure aborts stack before evaluating TOTP
    ctx2 = {"password": "wrong_password", "totp_token": "123456"}
    ok, trail = engine.evaluate_stack("sshd", "auth", "alice", ctx2)
    assert ok is False
    assert any("Aborting stack immediately" in msg for msg in trail)
    assert not any("pam_totp" in msg for msg in trail)
    print(f"[*] Test 2 Passed: Requisite failure immediately aborted evaluation without evaluating TOTP")

    # Configure Biometric Login with Sufficient fallback:
    # 1. pam_biometric (sufficient): if fingerprint valid, success!
    # 2. pam_unix (required): password fallback.
    engine.register_service_rule("gui_login", PAMModuleRule("auth", PAMControlFlag.SUFFICIENT, "pam_biometric", mock_pam_biometric))
    engine.register_service_rule("gui_login", PAMModuleRule("auth", PAMControlFlag.REQUIRED, "pam_unix", mock_pam_unix))

    # Test 3: Sufficient module succeeds, skipping password check
    ctx3 = {"fingerprint_valid": True, "password": "wrong"}
    ok, trail = engine.evaluate_stack("gui_login", "auth", "alice", ctx3)
    assert ok is True
    assert any("SUFFICIENT SUCCESS" in msg for msg in trail)
    assert not any("pam_unix" in msg for msg in trail)
    print(f"[*] Test 3 Passed: Sufficient module succeeded, bypassing password prompt cleanly")

    # Test 4: Sufficient module fails, falls back to password check
    ctx4 = {"fingerprint_valid": False, "password": "secret123"}
    ok, trail = engine.evaluate_stack("gui_login", "auth", "alice", ctx4)
    assert ok is True
    assert any("pam_unix" in msg for msg in trail)
    print(f"[*] Test 4 Passed: Sufficient module failed, fallback to required password succeeded")

    print("All PAM Stack Evaluator assertions passed successfully!")


if __name__ == "__main__":
    main()
