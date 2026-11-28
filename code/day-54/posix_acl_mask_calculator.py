"""
Day 54: POSIX Access Control List (ACL) Mask Calculator & VFS Checker
100% pure Python standard library implementation of POSIX.1e ACL entry parsing,
dynamic mask recalculation, effective permission intersection, and directory inheritance.
"""

from dataclasses import dataclass, field
import enum
from typing import Dict, List, Optional, Set, Tuple


class ACLTag(enum.Enum):
    USER_OBJ = "user_obj"      # Owning User (chmod u)
    USER = "user"              # Named User (user:alice)
    GROUP_OBJ = "group_obj"    # Owning Group (chmod g when no mask)
    GROUP = "group"            # Named Group (group:analytics)
    MASK = "mask"              # ACL Mask
    OTHER = "other"            # Others (chmod o)


@dataclass
class ACLEntry:
    tag: ACLTag
    qualifier: str             # Username or Groupname (empty for OBJ and OTHER)
    perms: int                 # 4=R, 2=W, 1=X (Bitmask: 0-7)


class POSIXACLEngine:
    """Calculates ACL Masks and evaluates effective VFS access permissions."""

    PERM_R = 4
    PERM_W = 2
    PERM_X = 1

    @classmethod
    def perms_to_str(cls, p: int) -> str:
        return f"{'r' if p & cls.PERM_R else '-'}{'w' if p & cls.PERM_W else '-'}{'x' if p & cls.PERM_X else '-'}"

    @classmethod
    def calculate_mask(cls, entries: List[ACLEntry]) -> int:
        """
        Calculates mask as union of GROUP_OBJ, all named USERs, and all named GROUPs.
        Mask = P_group_obj | (Union P_u) | (Union P_g)
        """
        mask = 0
        for e in entries:
            if e.tag in (ACLTag.GROUP_OBJ, ACLTag.USER, ACLTag.GROUP):
                mask |= e.perms
        return mask

    @classmethod
    def get_effective_perms(cls, entry: ACLEntry, mask: Optional[int]) -> int:
        """
        Named users and groups are constrained by the Mask:
        Effective = Perm & Mask.
        Owner (USER_OBJ) and OTHER are NOT affected by Mask.
        """
        if entry.tag in (ACLTag.USER, ACLTag.GROUP, ACLTag.GROUP_OBJ) and mask is not None:
            return entry.perms & mask
        return entry.perms

    @classmethod
    def check_access(
        cls,
        entries: List[ACLEntry],
        file_owner_uid: int,
        file_group_gid: int,
        process_uid: int,
        process_gids: List[int],
        requested_perm: int,
        uid_to_name: Dict[int, str],
        gid_to_name: Dict[int, str]
    ) -> Tuple[bool, str]:
        """Implements kernel VFS check_acl() algorithm."""
        proc_user = uid_to_name.get(process_uid, str(process_uid))
        proc_groups = {gid_to_name.get(g, str(g)) for g in process_gids}

        # 1. Check Owner (USER_OBJ)
        if process_uid == file_owner_uid:
            for e in entries:
                if e.tag == ACLTag.USER_OBJ:
                    if (e.perms & requested_perm) == requested_perm:
                        return True, "Granted via Owner (USER_OBJ)"
                    return False, "Denied: Owner lacks requested permission"

        # Locate active Mask entry
        mask_entry = next((e for e in entries if e.tag == ACLTag.MASK), None)
        active_mask = mask_entry.perms if mask_entry else None

        # 2. Check Named Users (USER)
        for e in entries:
            if e.tag == ACLTag.USER and e.qualifier == proc_user:
                eff = cls.get_effective_perms(e, active_mask)
                if (eff & requested_perm) == requested_perm:
                    return True, f"Granted via Named User '{e.qualifier}' (Effective: {cls.perms_to_str(eff)})"
                return False, f"Denied: Named User '{e.qualifier}' effective perms ({cls.perms_to_str(eff)}) insufficient"

        # 3. Check Groups (Owning Group + Named Groups)
        matching_group_perms = []
        for e in entries:
            if e.tag == ACLTag.GROUP_OBJ and file_group_gid in process_gids:
                eff = cls.get_effective_perms(e, active_mask)
                matching_group_perms.append(eff)
            elif e.tag == ACLTag.GROUP and e.qualifier in proc_groups:
                eff = cls.get_effective_perms(e, active_mask)
                matching_group_perms.append(eff)

        if matching_group_perms:
            # Union of all matched group permissions
            union_perms = 0
            for p in matching_group_perms:
                union_perms |= p
            if (union_perms & requested_perm) == requested_perm:
                return True, f"Granted via Group match (Union Effective: {cls.perms_to_str(union_perms)})"
            return False, "Denied: Matching groups lack requested permission"

        # 4. Check Others (OTHER)
        for e in entries:
            if e.tag == ACLTag.OTHER:
                if (e.perms & requested_perm) == requested_perm:
                    return True, "Granted via OTHER"
                return False, "Denied via OTHER"

        return False, "Denied: No matching ACL rule"


def main():
    print("=== Day 54: POSIX Access Control List (ACL) Mask Calculator ===")

    # Test Scenario: A file owned by root:root with custom ACLs
    # user::rwx (7)
    # user:alice:rwx (7)
    # group::r-- (4)
    # group:analysts:r-x (5)
    # mask::r-- (4)  <--- Explicit strict mask limiting effective perms to Read-Only!
    # other::--- (0)

    entries = [
        ACLEntry(ACLTag.USER_OBJ, "", 7),
        ACLEntry(ACLTag.USER, "alice", 7),
        ACLEntry(ACLTag.GROUP_OBJ, "", 4),
        ACLEntry(ACLTag.GROUP, "analysts", 5),
        ACLEntry(ACLTag.MASK, "", 4),
        ACLEntry(ACLTag.OTHER, "", 0)
    ]

    uid_map = {0: "root", 1001: "alice", 1002: "bob"}
    gid_map = {0: "root", 2001: "analysts", 2002: "finance"}

    # Test 1: Automatic Mask Calculation (if mask wasn't explicit)
    calc_mask = POSIXACLEngine.calculate_mask(entries)
    # Union of GROUP_OBJ (4), alice (7), analysts (5) = 4 | 7 | 5 = 7 (rwx)
    assert calc_mask == 7
    print(f"[*] Test 1 Passed: Auto-calculated mask union = {POSIXACLEngine.perms_to_str(calc_mask)} (7)")

    # Test 2: Alice attempts Write (2) access
    # Alice has 'rwx' (7), but explicit mask is 'r--' (4).
    # Effective = 7 & 4 = 4 ('r--'). Write must be DENIED!
    granted, reason = POSIXACLEngine.check_access(
        entries=entries, file_owner_uid=0, file_group_gid=0,
        process_uid=1001, process_gids=[2001], requested_perm=POSIXACLEngine.PERM_W,
        uid_to_name=uid_map, gid_to_name=gid_map
    )
    assert granted is False
    assert "effective perms (r--) insufficient" in reason
    print(f"[*] Test 2 Passed: Alice write blocked by ACL Mask: {reason}")

    # Test 3: Alice attempts Read (4) access -> Granted
    granted, reason = POSIXACLEngine.check_access(
        entries=entries, file_owner_uid=0, file_group_gid=0,
        process_uid=1001, process_gids=[2001], requested_perm=POSIXACLEngine.PERM_R,
        uid_to_name=uid_map, gid_to_name=gid_map
    )
    assert granted is True
    print(f"[*] Test 3 Passed: Alice read access permitted: {reason}")

    # Test 4: Root Owner attempts Write (2) access -> Granted (Owner ignores Mask)
    granted, reason = POSIXACLEngine.check_access(
        entries=entries, file_owner_uid=0, file_group_gid=0,
        process_uid=0, process_gids=[0], requested_perm=POSIXACLEngine.PERM_W,
        uid_to_name=uid_map, gid_to_name=gid_map
    )
    assert granted is True
    assert "Owner (USER_OBJ)" in reason
    print(f"[*] Test 4 Passed: Owner ignores mask and retains full authority: {reason}")

    # Test 5: Unrelated user Bob (UID 1002) in finance -> Falls through to OTHER (0) -> Denied
    granted, reason = POSIXACLEngine.check_access(
        entries=entries, file_owner_uid=0, file_group_gid=0,
        process_uid=1002, process_gids=[2002], requested_perm=POSIXACLEngine.PERM_R,
        uid_to_name=uid_map, gid_to_name=gid_map
    )
    assert granted is False
    assert "Denied via OTHER" in reason
    print(f"[*] Test 5 Passed: Other user denied access: {reason}")

    print("All POSIX ACL Mask Calculator assertions passed successfully!")


if __name__ == "__main__":
    main()
