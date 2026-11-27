#!/usr/bin/env python3
"""
Day 50 Lab: POSIX chroot Isolation & Security Boundary Engine
Simulates:
1. Virtual chroot environment path resolution anchor (/ -> /jail).
2. Bind-mount setup for essential virtual pseudo-filesystems (/proc, /sys, /dev).
3. Demonstration of the classic root chroot-escape exploit vector (CWD leak).
Uses Python standard library only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SimulatedVFS:
    root_anchor: str = "/"
    cwd: str = "/"
    mounts: Dict[str, str] = field(default_factory=dict)

    def resolve_path(self, path: str) -> str:
        """Resolves an absolute path relative to the active root anchor."""
        if path.startswith("/"):
            # Anchor path within root_anchor
            if self.root_anchor == "/":
                return path
            return (self.root_anchor.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/")
        return (self.cwd.rstrip("/") + "/" + path).replace("//", "/")

    def chroot(self, new_root: str):
        """Changes the root directory anchor."""
        self.root_anchor = new_root
        # In a secure implementation, cwd must be updated to '/'
        # We model both secure and leaky behaviors

    def bind_mount(self, source: str, target: str):
        self.mounts[target] = source


class ChrootEscapeSimulator:
    """Demonstrates why chroot is not a security boundary against UID 0 (root)."""

    @staticmethod
    def simulate_fchdir_escape() -> List[str]:
        steps = []
        vfs = SimulatedVFS()

        # Setup jail directory
        jail_path = "/tmp/guest_jail"
        steps.append(f"1. Host establishes chroot jail at: {jail_path}")

        # VFS bind-mounts essential virtual filesystems
        vfs.bind_mount("/dev", f"{jail_path}/dev")
        vfs.bind_mount("/proc", f"{jail_path}/proc")
        steps.append("2. Bind-mounted essential pseudo-filesystems: /dev, /proc")

        # Step 3: Enter chroot jail, but simulate holding an unconfined file descriptor (CWD leak)
        vfs.chroot(jail_path)
        vfs.cwd = "/outside_leak"  # CWD remained outside jail!
        steps.append("3. Process entered chroot jail, but CWD remained pointing outside the jail anchor!")

        # Step 4: Attacker traverses upward from CWD
        attacker_resolved = vfs.resolve_path("../etc/shadow")
        steps.append(f"4. Attacker resolved path: '../etc/shadow' -> '{attacker_resolved}'")

        assert "guest_jail" not in attacker_resolved, "Attacker broke out of jail anchor!"
        steps.append("5. [EXPLOIT SUCCESS] Attacker accessed host filesystem outside chroot jail!")

        return steps


def main():
    print("====================================================")
    print("DAY 50: POSIX chroot ISOLATION & ESCAPE SIMULATOR")
    print("====================================================")

    vfs = SimulatedVFS()

    # 1. Normal chroot path resolution
    jail_dir = "/srv/chroot/web"
    vfs.chroot(jail_dir)
    resolved = vfs.resolve_path("/etc/nginx/nginx.conf")
    print(f"1. Path Resolution inside Jail:")
    print(f"   Requested Path : /etc/nginx/nginx.conf")
    print(f"   Resolved Path  : {resolved}")
    assert resolved == "/srv/chroot/web/etc/nginx/nginx.conf"
    print("   [PASS] Path successfully anchored inside chroot directory.")

    # 2. Virtual Bind Mounts
    vfs.bind_mount("/dev", f"{jail_dir}/dev")
    vfs.bind_mount("/proc", f"{jail_dir}/proc")
    print(f"\n2. Active Bind Mounts inside Jail:")
    for tgt, src in vfs.mounts.items():
        print(f"   {src} -> {tgt}")
    assert f"{jail_dir}/proc" in vfs.mounts
    print("   [PASS] Pseudo-filesystems (/proc, /dev) virtually bind-mounted.")

    # 3. Simulate chroot escape vector
    print(f"\n3. Simulating Classic chroot Escape Vector:")
    escape_steps = ChrootEscapeSimulator.simulate_fchdir_escape()
    for s in escape_steps:
        print(f"   {s}")

    print("\n[VERIFIED] chroot isolation and security boundary simulation passed 100%!")


if __name__ == "__main__":
    main()
