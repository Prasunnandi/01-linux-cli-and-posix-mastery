"""
Day 51: Linux User & Shadow Password Database Engine
100% pure Python standard library implementation of /etc/passwd and /etc/shadow
parsing, PBKDF2/HMAC-SHA512 cryptographic verification, expiration checking, and UID auditing.
"""

from dataclasses import dataclass, field
import hashlib
import hmac
import os
import time
from typing import Dict, List, Optional, Tuple


@dataclass
class PasswdEntry:
    username: str
    password_placeholder: str  # Usually 'x'
    uid: int
    gid: int
    gecos: str
    home_dir: str
    shell: str


@dataclass
class ShadowEntry:
    username: str
    password_hash: str        # Format: $id$salt$hash or locked (!/*)
    last_changed_days: int    # Days since Jan 1, 1970
    min_days: int             # Min days before change allowed
    max_days: int             # Max days before change required
    warn_days: int            # Days warning before expiration
    inact_days: int           # Days inactive before account disabled
    expire_days: int          # Absolute expiration date in days since epoch
    flag: int = 0


class UserDatabaseEngine:
    """Simulates POSIX identity resolution and cryptographic shadow validation."""

    def __init__(self):
        self.passwd_db: Dict[str, PasswdEntry] = {}
        self.shadow_db: Dict[str, ShadowEntry] = {}
        self.uid_map: Dict[int, List[str]] = {}

    @staticmethod
    def hash_password(plaintext: str, salt: str) -> str:
        """Simulates $6$ (SHA-512 crypt) using PBKDF2-HMAC-SHA512 with 5000 rounds."""
        digest = hashlib.pbkdf2_hmac("sha512", plaintext.encode("utf-8"), salt.encode("utf-8"), 5000)
        return f"$6${salt}${digest.hex()[:32]}"

    def add_user(
        self,
        username: str,
        plaintext_password: str,
        uid: int,
        gid: int,
        gecos: str = "User",
        home: str = "/home/user",
        shell: str = "/bin/bash",
        max_days: int = 90,
        expire_days: int = -1
    ):
        salt = os.urandom(8).hex()
        pw_hash = self.hash_password(plaintext_password, salt)
        current_days = int(time.time() // 86400)

        p_entry = PasswdEntry(username, "x", uid, gid, gecos, home, shell)
        s_entry = ShadowEntry(username, pw_hash, current_days, 0, max_days, 7, -1, expire_days)

        self.passwd_db[username] = p_entry
        self.shadow_db[username] = s_entry

        if uid not in self.uid_map:
            self.uid_map[uid] = []
        self.uid_map[uid].append(username)

    def authenticate(self, username: str, plaintext_password: str, current_timestamp: Optional[float] = None) -> Tuple[bool, str]:
        """Authenticates user against shadow entry, validating hash, locks, and expiration."""
        if username not in self.shadow_db or username not in self.passwd_db:
            return False, "User not found"

        s_entry = self.shadow_db[username]
        now_sec = current_timestamp if current_timestamp is not None else time.time()
        current_days = int(now_sec // 86400)

        # 1. Check account lock
        if s_entry.password_hash.startswith("!") or s_entry.password_hash.startswith("*"):
            return False, "Account is locked"

        # 2. Check absolute expiration
        if s_entry.expire_days > 0 and current_days >= s_entry.expire_days:
            return False, "Account has expired"

        # 3. Check password max age expiration
        if s_entry.max_days > 0 and current_days >= (s_entry.last_changed_days + s_entry.max_days):
            return False, "Password expired; change required"

        # 4. Parse salt and verify hash using constant-time comparison
        parts = s_entry.password_hash.split("$")
        if len(parts) < 4:
            return False, "Malformed shadow hash"

        salt = parts[2]
        computed = self.hash_password(plaintext_password, salt)
        if hmac.compare_digest(computed, s_entry.password_hash):
            return True, "Authentication successful"
        else:
            return False, "Invalid password"

    def audit_uid_zero_collisions(self) -> List[str]:
        """Identifies unauthorized UID 0 accounts representing security risks."""
        return [user for user in self.uid_map.get(0, []) if user != "root"]


def main():
    print("=== Day 51: Linux User & Shadow Password Database Engine ===")

    engine = UserDatabaseEngine()

    # Add standard root user
    engine.add_user("root", "MasterSecret123!", uid=0, gid=0, home="/root")

    # Add regular developer user
    engine.add_user("devops", "DevPass2026!", uid=1001, gid=1001, home="/home/devops", max_days=30)

    # Add rogue account duplicating UID 0
    engine.add_user("backdoor_admin", "HackerPass123!", uid=0, gid=0, home="/root")

    # Test 1: Successful authentication
    ok, msg = engine.authenticate("devops", "DevPass2026!")
    assert ok is True
    print(f"[*] Test 1 Passed: Valid credentials accepted ({msg})")

    # Test 2: Invalid password rejection
    ok, msg = engine.authenticate("devops", "WrongPassword!")
    assert ok is False
    assert msg == "Invalid password"
    print(f"[*] Test 2 Passed: Invalid credentials rejected ({msg})")

    # Test 3: Account expiration check
    # Simulate time jumping 45 days into the future (exceeding 30-day max_days)
    future_time = time.time() + (45 * 86400)
    ok, msg = engine.authenticate("devops", "DevPass2026!", current_timestamp=future_time)
    assert ok is False
    assert "Password expired" in msg
    print(f"[*] Test 3 Passed: Password aging expiration enforced ({msg})")

    # Test 4: Account lock check
    engine.shadow_db["devops"].password_hash = "!" + engine.shadow_db["devops"].password_hash
    ok, msg = engine.authenticate("devops", "DevPass2026!")
    assert ok is False
    assert msg == "Account is locked"
    print(f"[*] Test 4 Passed: Account locking flag (!) enforced ({msg})")

    # Test 5: Audit UID 0 collision detection
    collisions = engine.audit_uid_zero_collisions()
    assert len(collisions) == 1
    assert "backdoor_admin" in collisions
    print(f"[*] Test 5 Passed: Security audit successfully detected UID 0 collision: {collisions}")

    print("All User & Shadow Database Engine assertions passed successfully!")


if __name__ == "__main__":
    main()
