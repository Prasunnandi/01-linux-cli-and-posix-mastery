"""
Day 56: Linux Capabilities Transformation Engine
100% pure Python standard library implementation of the 5 capability sets
(Permitted, Effective, Inheritable, Bounding, Ambient) and execve() transformation math.
"""

from dataclasses import dataclass
import enum
from typing import Optional, Set, Tuple


class Capability(enum.IntEnum):
    CAP_CHOWN = 0
    CAP_DAC_OVERRIDE = 1
    CAP_DAC_READ_SEARCH = 2
    CAP_FOWNER = 3
    CAP_SETGID = 6
    CAP_SETUID = 7
    CAP_NET_BIND_SERVICE = 10
    CAP_NET_RAW = 13
    CAP_SYS_PTRACE = 19
    CAP_SYS_ADMIN = 21


@dataclass
class ProcessCreds:
    uid: int
    euid: int
    cap_permitted: Set[Capability]
    cap_effective: Set[Capability]
    cap_inheritable: Set[Capability]
    cap_bounding: Set[Capability]
    cap_ambient: Set[Capability]


@dataclass
class FileCaps:
    permitted: Set[Capability]
    inheritable: Set[Capability]
    effective_flag: bool  # 1 bit flag (F_E)


class CapabilityTransitionEngine:
    """Implements mathematical capability transformation formulas across execve()."""

    @staticmethod
    def execve_transition(caller: ProcessCreds, file_caps: Optional[FileCaps], is_suid_root: bool = False) -> ProcessCreds:
        """
        Calculates new capability sets upon executing a new binary:
        P_P' = P_A | (P_B & F_P) | (P_I & F_I)
        P_E' = P_P' (if F_E) else P_A
        P_I' = P_I
        P_A' = P_A (if no file caps and not SUID) else empty
        """
        p_a = set(caller.cap_ambient)
        p_b = set(caller.cap_bounding)
        p_i = set(caller.cap_inheritable)

        if is_suid_root:
            # Traditional SUID root sets all bounding capabilities into Permitted & Effective
            new_permitted = set(p_b)
            new_effective = set(p_b)
            new_ambient = set()
            return ProcessCreds(
                uid=caller.uid, euid=0,
                cap_permitted=new_permitted, cap_effective=new_effective,
                cap_inheritable=p_i, cap_bounding=p_b, cap_ambient=new_ambient
            )

        f_p = set(file_caps.permitted) if file_caps else set()
        f_i = set(file_caps.inheritable) if file_caps else set()
        f_e = file_caps.effective_flag if file_caps else False

        # Transform Permitted: P_P' = P_A | (P_B & F_P) | (P_I & F_I)
        new_permitted = p_a | (p_b & f_p) | (p_i & f_i)

        # Transform Effective: P_E' = P_P' if F_E else P_A
        new_effective = set(new_permitted) if f_e else set(p_a)

        # Transform Ambient: cleared if binary has file capabilities
        if file_caps is not None and (f_p or f_i):
            new_ambient = set()
        else:
            new_ambient = set(p_a)

        return ProcessCreds(
            uid=caller.uid, euid=caller.euid,
            cap_permitted=new_permitted, cap_effective=new_effective,
            cap_inheritable=p_i, cap_bounding=p_b, cap_ambient=new_ambient
        )

    @staticmethod
    def drop_bounding_capability(creds: ProcessCreds, cap: Capability):
        """Prunes capability from bounding set (irreversible system ceiling)."""
        creds.cap_bounding.discard(cap)
        creds.cap_permitted.discard(cap)
        creds.cap_effective.discard(cap)
        creds.cap_ambient.discard(cap)


def main():
    print("=== Day 56: Linux Capabilities Transformation Engine ===")

    all_caps = set(Capability)

    # Initial state: Unprivileged user (UID 1000) with empty capabilities
    user_proc = ProcessCreds(
        uid=1000, euid=1000,
        cap_permitted=set(), cap_effective=set(),
        cap_inheritable=set(), cap_bounding=set(all_caps), cap_ambient=set()
    )

    # Test 1: User runs unprivileged binary without file capabilities -> Stays empty
    res1 = CapabilityTransitionEngine.execve_transition(user_proc, None)
    assert len(res1.cap_effective) == 0
    print("[*] Test 1 Passed: Executing unconfined binary retains zero capabilities")

    # Test 2: User runs ping binary with file capability CAP_NET_RAW (F_P=RAW, F_E=True)
    ping_caps = FileCaps(permitted={Capability.CAP_NET_RAW}, inheritable=set(), effective_flag=True)
    res2 = CapabilityTransitionEngine.execve_transition(user_proc, ping_caps)
    assert Capability.CAP_NET_RAW in res2.cap_effective
    assert Capability.CAP_NET_RAW in res2.cap_permitted
    assert Capability.CAP_SYS_ADMIN not in res2.cap_effective
    print("[*] Test 2 Passed: File capability granted scoped CAP_NET_RAW without granting full root")

    # Test 3: Systemd service with Ambient capability (CAP_NET_BIND_SERVICE) runs unprivileged child
    daemon_proc = ProcessCreds(
        uid=1000, euid=1000,
        cap_permitted={Capability.CAP_NET_BIND_SERVICE},
        cap_effective={Capability.CAP_NET_BIND_SERVICE},
        cap_inheritable={Capability.CAP_NET_BIND_SERVICE},
        cap_bounding=set(all_caps),
        cap_ambient={Capability.CAP_NET_BIND_SERVICE}
    )
    # Child binary has NO file capabilities
    res3 = CapabilityTransitionEngine.execve_transition(daemon_proc, None)
    assert Capability.CAP_NET_BIND_SERVICE in res3.cap_effective
    assert Capability.CAP_NET_BIND_SERVICE in res3.cap_ambient
    print("[*] Test 3 Passed: Ambient capability successfully preserved across unprivileged execve()")

    # Test 4: Container bounding set pruning blocks SUID root elevation
    container_proc = ProcessCreds(
        uid=1000, euid=1000,
        cap_permitted=set(), cap_effective=set(), cap_inheritable=set(),
        cap_bounding=set(all_caps), cap_ambient=set()
    )
    # Prune CAP_SYS_ADMIN from container bounding set
    CapabilityTransitionEngine.drop_bounding_capability(container_proc, Capability.CAP_SYS_ADMIN)
    assert Capability.CAP_SYS_ADMIN not in container_proc.cap_bounding

    # Attacker tries to execute SUID binary or binary with CAP_SYS_ADMIN file cap
    admin_binary = FileCaps(permitted={Capability.CAP_SYS_ADMIN}, inheritable=set(), effective_flag=True)
    res4 = CapabilityTransitionEngine.execve_transition(container_proc, admin_binary)
    assert Capability.CAP_SYS_ADMIN not in res4.cap_effective
    assert Capability.CAP_SYS_ADMIN not in res4.cap_permitted
    print("[*] Test 4 Passed: Pruned Bounding Set successfully defeated privilege escalation attempt")

    print("All Linux Capabilities Transformation Engine assertions passed successfully!")


if __name__ == "__main__":
    main()
