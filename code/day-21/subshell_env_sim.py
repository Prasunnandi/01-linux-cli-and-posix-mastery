#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
subshell_env_sim.py - Process Environment & Subshell Memory Isolation Simulator
Demonstrates how child processes receive copies of parent environments and how
mutations in subshells cannot leak into parent address space.
"""
import copy

class ProcessContext:
    def __init__(self, pid: int, ppid: int, name: str, env: dict = None, local_vars: dict = None):
        self.pid = pid
        self.ppid = ppid
        self.name = name
        self.env = env if env is not None else {}
        self.local_vars = local_vars if local_vars is not None else {}

    def fork_subshell(self, child_pid: int) -> 'ProcessContext':
        """Simulates fork(): child receives exact copy of parent variables and env."""
        return ProcessContext(
            pid=child_pid,
            ppid=self.pid,
            name=f"{self.name}_child",
            env=copy.deepcopy(self.env),
            local_vars=copy.deepcopy(self.local_vars)
        )

    def set_env(self, key: str, value: str):
        self.env[key] = value

    def set_local(self, key: str, value: str):
        self.local_vars[key] = value

    def dump(self) -> dict:
        return {
            "pid": self.pid,
            "ppid": self.ppid,
            "name": self.name,
            "env": self.env,
            "local_vars": self.local_vars
        }

def test_subshell_isolation():
    parent = ProcessContext(pid=1000, ppid=1, name="parent_shell")
    parent.set_env("PATH", "/usr/bin:/bin")
    parent.set_env("APP_CONFIG", "production.yaml")
    parent.set_local("loop_counter", "0")

    # Fork subshell
    child = parent.fork_subshell(child_pid=1001)

    # Mutate in child
    child.set_env("APP_CONFIG", "child_mutated.yaml")
    child.set_local("loop_counter", "999")

    # Parent remains untouched
    assert parent.env["APP_CONFIG"] == "production.yaml", "Parent env was corrupted!"
    assert parent.local_vars["loop_counter"] == "0", "Parent local variable was corrupted!"
    return parent.dump(), child.dump()

if __name__ == "__main__":
    print("====================================================")
    print("BASH PROCESS ENVIRONMENT & SUBSHELL ISOLATION")
    print("====================================================")
    p_state, c_state = test_subshell_isolation()
    print("Parent State (PID: %d):" % p_state["pid"])
    print("  APP_CONFIG   :", p_state["env"]["APP_CONFIG"])
    print("  loop_counter :", p_state["local_vars"]["loop_counter"])
    print("\nChild Subshell State (PID: %d):" % c_state["pid"])
    print("  APP_CONFIG   :", c_state["env"]["APP_CONFIG"])
    print("  loop_counter :", c_state["local_vars"]["loop_counter"])
    print("\n[VERIFIED] Memory isolation 100% operational: Child mutations did not leak!")
