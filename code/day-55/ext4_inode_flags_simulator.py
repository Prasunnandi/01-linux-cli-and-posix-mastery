"""
Day 55: ext4 Inode Immutable & Append-Only Flags Simulator
100% pure Python standard library implementation of on-disk ext4 inode flags,
VFS inode_permission() pre-check, chattr/lsattr mutation, and CAP_LINUX_IMMUTABLE enforcement.
"""

from dataclasses import dataclass, field
import enum
import time
from typing import Dict, Optional, Set, Tuple


class InodeFlag(enum.IntFlag):
    SECRM = 0x00000001        # Secure deletion (+s)
    UNRM = 0x00000002         # Undelete (+u)
    COMPR = 0x00000004        # Compress (+c)
    SYNC = 0x00000008         # Synchronous updates (+S)
    IMMUTABLE = 0x00000010    # Immutable (+i)
    APPEND = 0x00000020       # Append-only (+a)
    NODUMP = 0x00000040       # Do not dump (+d)
    NOATIME = 0x00000080      # Do not update atime (+A)


@dataclass
class SimulatedExt4Inode:
    inode_num: int
    mode: int                 # Standard permissions (e.g. 0o644)
    uid: int                  # Owner UID
    gid: int                  # Owner GID
    size: int                 # File size in bytes
    flags: InodeFlag          # 32-bit ext4 inode flags
    content: bytearray = field(default_factory=bytearray)


class VFSInodeManager:
    """Simulates kernel VFS permission checks against on-disk inode flags."""

    CAP_LINUX_IMMUTABLE = 9   # Capability required to set/clear +i and +a

    def __init__(self):
        self.inodes: Dict[int, SimulatedExt4Inode] = {}
        self.next_inode = 1000

    def create_file(self, uid: int, gid: int, mode: int = 0o644) -> SimulatedExt4Inode:
        inode = SimulatedExt4Inode(
            inode_num=self.next_inode,
            mode=mode,
            uid=uid,
            gid=gid,
            size=0,
            flags=InodeFlag(0)
        )
        self.inodes[self.next_inode] = inode
        self.next_inode += 1
        return inode

    def chattr(self, inode_num: int, add_flags: int, remove_flags: int, caller_caps: Set[int]) -> Tuple[bool, str]:
        """Simulates ioctl(fd, FS_IOC_SETFLAGS) mutating on-disk inode flags."""
        if inode_num not in self.inodes:
            return False, "Inode not found"

        inode = self.inodes[inode_num]

        # Mutating IMMUTABLE or APPEND requires CAP_LINUX_IMMUTABLE
        protected_flags = InodeFlag.IMMUTABLE | InodeFlag.APPEND
        if (add_flags & protected_flags) or (remove_flags & protected_flags):
            if self.CAP_LINUX_IMMUTABLE not in caller_caps:
                return False, "Operation not permitted: CAP_LINUX_IMMUTABLE required"

        # Apply bitwise modifications
        inode.flags = InodeFlag((inode.flags | add_flags) & ~remove_flags)
        return True, f"Updated flags: 0x{inode.flags:08X}"

    def vfs_write(self, inode_num: int, data: bytes, is_append: bool, caller_uid: int) -> Tuple[bool, str]:
        """Simulates VFS write pre-check verifying IMMUTABLE and APPEND bits."""
        if inode_num not in self.inodes:
            return False, "Inode not found"
        inode = self.inodes[inode_num]

        # 1. IMMUTABLE blocks ALL writes, even by root (UID 0)
        if inode.flags & InodeFlag.IMMUTABLE:
            return False, "EPERM (Operation not permitted): Inode is IMMUTABLE (+i)"

        # 2. APPEND-ONLY allows writes ONLY if opened with O_APPEND
        if inode.flags & InodeFlag.APPEND:
            if not is_append:
                return False, "EPERM (Operation not permitted): Inode is APPEND-ONLY (+a); non-append write/truncation rejected"

        # Perform write
        if is_append:
            inode.content.extend(data)
        else:
            inode.content = bytearray(data)
        inode.size = len(inode.content)
        return True, f"Successfully wrote {len(data)} bytes (New size: {inode.size})"

    def vfs_unlink(self, inode_num: int, caller_uid: int) -> Tuple[bool, str]:
        """Simulates VFS unlink() (deletion) pre-check."""
        if inode_num not in self.inodes:
            return False, "Inode not found"
        inode = self.inodes[inode_num]

        # IMMUTABLE and APPEND both prevent deletion
        if inode.flags & InodeFlag.IMMUTABLE:
            return False, "EPERM: Cannot delete IMMUTABLE (+i) file"
        if inode.flags & InodeFlag.APPEND:
            return False, "EPERM: Cannot delete APPEND-ONLY (+a) file"

        del self.inodes[inode_num]
        return True, "File unlinked successfully"


def main():
    print("=== Day 55: ext4 Inode Immutable & Append-Only Flags Simulator ===")

    mgr = VFSInodeManager()
    file_inode = mgr.create_file(uid=0, gid=0)

    # Test 1: Normal root write succeeds
    ok, msg = mgr.vfs_write(file_inode.inode_num, b"Initial log data\n", is_append=True, caller_uid=0)
    assert ok is True
    print(f"[*] Test 1 Passed: Initial write successful: {msg}")

    # Test 2: Unprivileged process without CAP_LINUX_IMMUTABLE fails to set +i
    ok, msg = mgr.chattr(file_inode.inode_num, add_flags=InodeFlag.IMMUTABLE, remove_flags=0, caller_caps=set())
    assert ok is False
    assert "CAP_LINUX_IMMUTABLE required" in msg
    print(f"[*] Test 2 Passed: Unprivileged chattr rejected: {msg}")

    # Test 3: Root with CAP_LINUX_IMMUTABLE enables +i
    ok, msg = mgr.chattr(file_inode.inode_num, add_flags=InodeFlag.IMMUTABLE, remove_flags=0, caller_caps={mgr.CAP_LINUX_IMMUTABLE})
    assert ok is True
    assert file_inode.flags & InodeFlag.IMMUTABLE
    print(f"[*] Test 3 Passed: Applied IMMUTABLE flag (+i): {msg}")

    # Test 4: Root write rejected on IMMUTABLE file
    ok, msg = mgr.vfs_write(file_inode.inode_num, b"Attacker payload", is_append=True, caller_uid=0)
    assert ok is False
    assert "EPERM" in msg
    print(f"[*] Test 4 Passed: Root write blocked by IMMUTABLE flag: {msg}")

    # Test 5: Root deletion rejected on IMMUTABLE file
    ok, msg = mgr.vfs_unlink(file_inode.inode_num, caller_uid=0)
    assert ok is False
    assert "Cannot delete IMMUTABLE" in msg
    print(f"[*] Test 5 Passed: Root deletion blocked by IMMUTABLE flag: {msg}")

    # Test 6: Switch from IMMUTABLE to APPEND-ONLY (+a)
    mgr.chattr(file_inode.inode_num, add_flags=InodeFlag.APPEND, remove_flags=InodeFlag.IMMUTABLE, caller_caps={mgr.CAP_LINUX_IMMUTABLE})
    # Overwrite/Truncate fails
    ok, msg = mgr.vfs_write(file_inode.inode_num, b"Truncate write", is_append=False, caller_uid=0)
    assert ok is False
    # Append succeeds
    ok, msg = mgr.vfs_write(file_inode.inode_num, b"New append line\n", is_append=True, caller_uid=0)
    assert ok is True
    assert file_inode.size > 15
    print(f"[*] Test 6 Passed: Append-only mode permits appending while rejecting truncation: {msg}")

    print("All ext4 Inode Flags Simulator assertions passed successfully!")


if __name__ == "__main__":
    main()
