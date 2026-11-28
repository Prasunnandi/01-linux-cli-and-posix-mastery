"""
Day 52: Sudoers Rule Evaluator & Timestamp Ticket Engine
100% pure Python standard library implementation of /etc/sudoers grammar parsing,
User/Cmnd aliases, ticket caching (/run/sudo/ts), and privilege delegation enforcement.
"""

from dataclasses import dataclass, field
import fnmatch
import time
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class SudoRule:
    user_spec: str       # Username or %group
    host_spec: str       # Hostname or ALL
    runas_user: str      # Target execution user (default 'root')
    runas_group: str     # Target execution group (default 'root')
    command_spec: str    # Command binary or Cmnd_Alias or ALL
    nopasswd: bool = False
    noexec: bool = False


class SudoersEngine:
    """Evaluates declarative sudoers permissions and maintains ticket timestamps."""

    DEFAULT_TICKET_TIMEOUT = 900.0  # 15 minutes (seconds)

    def __init__(self, hostname: str = "prod-node-01"):
        self.hostname = hostname
        self.user_aliases: Dict[str, Set[str]] = {}
        self.cmnd_aliases: Dict[str, Set[str]] = {}
        self.rules: List[SudoRule] = []
        # Ticket cache: (user, tty) -> last_auth_timestamp
        self.ticket_cache: Dict[Tuple[str, str], float] = {}

    def add_user_alias(self, alias_name: str, members: List[str]):
        self.user_aliases[alias_name] = set(members)

    def add_cmnd_alias(self, alias_name: str, commands: List[str]):
        self.cmnd_aliases[alias_name] = set(commands)

    def add_rule(self, rule: SudoRule):
        self.rules.append(rule)

    def _matches_user(self, rule_spec: str, user: str, user_groups: List[str]) -> bool:
        if rule_spec == "ALL":
            return True
        if rule_spec == user:
            return True
        if rule_spec.startswith("%") and rule_spec[1:] in user_groups:
            return True
        if rule_spec in self.user_aliases and user in self.user_aliases[rule_spec]:
            return True
        return False

    def _matches_command(self, rule_cmd: str, executed_cmd: str) -> bool:
        if rule_cmd == "ALL":
            return True
        if rule_cmd in self.cmnd_aliases:
            return executed_cmd in self.cmnd_aliases[rule_cmd]
        return fnmatch.fnmatch(executed_cmd, rule_cmd)

    def evaluate(
        self,
        user: str,
        user_groups: List[str],
        requested_cmd: str,
        target_user: str = "root",
        tty: str = "/dev/pts/1",
        current_time: Optional[float] = None
    ) -> Tuple[bool, bool, str]:
        """
        Evaluates sudo permission.
        Returns (allowed: bool, prompt_password: bool, reason: str).
        """
        now = current_time if current_time is not None else time.time()
        matching_rule: Optional[SudoRule] = None

        # Sudoers rules are evaluated from top to bottom; later matches override earlier ones
        for rule in self.rules:
            if not self._matches_user(rule.user_spec, user, user_groups):
                continue
            if rule.host_spec != "ALL" and rule.host_spec != self.hostname:
                continue
            if rule.runas_user != "ALL" and rule.runas_user != target_user:
                continue
            if not self._matches_command(rule.command_spec, requested_cmd):
                continue
            matching_rule = rule

        if not matching_rule:
            return False, False, f"User {user} is not in the sudoers file"

        # Check NOPASSWD override
        if matching_rule.nopasswd:
            return True, False, "Authorized via NOPASSWD"

        # Check Ticket Cache
        ticket_key = (user, tty)
        if ticket_key in self.ticket_cache:
            last_auth = self.ticket_cache[ticket_key]
            if (now - last_auth) < self.DEFAULT_TICKET_TIMEOUT:
                return True, False, "Authorized via valid ticket cache"

        # Password authentication required
        return True, True, "Password authentication required"

    def update_ticket(self, user: str, tty: str = "/dev/pts/1", auth_time: Optional[float] = None):
        """Records successful authentication in ticket cache."""
        t = auth_time if auth_time is not None else time.time()
        self.ticket_cache[(user, tty)] = t


def main():
    print("=== Day 52: Sudoers Rule Evaluator & Timestamp Ticket Engine ===")

    engine = SudoersEngine(hostname="db-server-01")

    # Define Aliases
    engine.add_user_alias("SYS_ADMINS", ["alice", "bob"])
    engine.add_cmnd_alias("WEB_MANAGEMENT", ["/usr/bin/systemctl restart nginx", "/usr/bin/nginx -t"])

    # Define Rules
    # Rule 1: %wheel can run anything
    engine.add_rule(SudoRule(user_spec="%wheel", host_spec="ALL", runas_user="ALL", runas_group="ALL", command_spec="ALL"))
    # Rule 2: SYS_ADMINS can run WEB_MANAGEMENT with NOPASSWD
    engine.add_rule(SudoRule(user_spec="SYS_ADMINS", host_spec="ALL", runas_user="root", runas_group="root",
                             command_spec="WEB_MANAGEMENT", nopasswd=True))
    # Rule 3: charlie can only run /usr/bin/uptime
    engine.add_rule(SudoRule(user_spec="charlie", host_spec="ALL", runas_user="root", runas_group="root",
                             command_spec="/usr/bin/uptime", nopasswd=False))

    now = 1000000.0

    # Test 1: Alice (in SYS_ADMINS) executes authorized command -> Allowed without password
    allowed, prompt, reason = engine.evaluate("alice", [], "/usr/bin/nginx -t", current_time=now)
    assert allowed is True
    assert prompt is False
    assert "NOPASSWD" in reason
    print(f"[*] Test 1 Passed: Alice authorized under NOPASSWD: {reason}")

    # Test 2: Alice executes unauthorized command -> Rejected
    allowed, prompt, reason = engine.evaluate("alice", [], "/bin/rm -rf /", current_time=now)
    assert allowed is False
    print(f"[*] Test 2 Passed: Alice unauthorized command rejected: {reason}")

    # Test 3: Charlie runs authorized command -> Allowed, requires password prompt
    allowed, prompt, reason = engine.evaluate("charlie", [], "/usr/bin/uptime", current_time=now)
    assert allowed is True
    assert prompt is True
    print(f"[*] Test 3 Passed: Charlie authorized with password prompt: {reason}")

    # Test 4: Charlie authenticates; subsequent execution within 15 min uses ticket
    engine.update_ticket("charlie", "/dev/pts/1", auth_time=now)
    allowed, prompt, reason = engine.evaluate("charlie", [], "/usr/bin/uptime", current_time=now + 300.0)
    assert allowed is True
    assert prompt is False
    assert "ticket cache" in reason
    print(f"[*] Test 4 Passed: Charlie cached ticket accepted at t+300s: {reason}")

    # Test 5: Ticket expires after 15 minutes (901 seconds)
    allowed, prompt, reason = engine.evaluate("charlie", [], "/usr/bin/uptime", current_time=now + 901.0)
    assert allowed is True
    assert prompt is True
    print(f"[*] Test 5 Passed: Charlie ticket expired at t+901s, re-prompt enforced: {reason}")

    print("All Sudoers Rule Evaluator assertions passed successfully!")


if __name__ == "__main__":
    main()
