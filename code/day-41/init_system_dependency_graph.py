#!/usr/bin/env python3
"""
Day 41 Lab: Init System Dependency DAG & Concurrency Dispatcher
Simulates systemd's dependency engine: builds a Directed Acyclic Graph (DAG)
of system services, detects dependency/ordering cycles, and dispatches
independent units in concurrent topological waves.
Uses Python standard library only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple


@dataclass
class UnitNode:
    name: str
    requires: Set[str] = field(default_factory=set)
    after: Set[str] = field(default_factory=set)
    is_active: bool = False


class DependencyGraphEngine:
    def __init__(self):
        self.units: Dict[str, UnitNode] = {}

    def add_unit(self, name: str, requires: List[str] = None, after: List[str] = None):
        self.units[name] = UnitNode(
            name=name,
            requires=set(requires or []),
            after=set(after or [])
        )

    def detect_cycles(self) -> List[List[str]]:
        """Tarjan/DFS cycle detection on ordering edges (After=)."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.units[node].after:
                if neighbor not in self.units:
                    continue
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Cycle found
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            rec_stack.remove(node)

        for u in self.units:
            if u not in visited:
                dfs(u, [])

        return cycles

    def compute_dispatch_waves(self) -> List[List[str]]:
        """Computes parallel execution waves where units in each wave start concurrently."""
        cycles = self.detect_cycles()
        if cycles:
            raise RuntimeError(f"Ordering cycles detected in unit graph: {cycles}")

        # In-degree based on After= constraints
        in_degree = {name: 0 for name in self.units}
        reverse_graph = {name: [] for name in self.units}

        for name, unit in self.units.items():
            for dep in unit.after:
                if dep in self.units:
                    in_degree[name] += 1
                    reverse_graph[dep].append(name)

        waves = []
        current_wave = [u for u, deg in in_degree.items() if deg == 0]

        while current_wave:
            waves.append(sorted(current_wave))
            next_wave = []
            for u in current_wave:
                self.units[u].is_active = True
                for dependent in reverse_graph[u]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_wave.append(dependent)
            current_wave = next_wave

        return waves


def main():
    print("====================================================")
    print("DAY 41: INIT SYSTEM DEPENDENCY DAG & CONCURRENCY")
    print("====================================================")

    dag = DependencyGraphEngine()

    # Define standard systemd boot units
    dag.add_unit("syslog.socket", requires=[], after=[])
    dag.add_unit("dbus.socket", requires=[], after=[])
    dag.add_unit("syslog.service", requires=["syslog.socket"], after=["syslog.socket"])
    dag.add_unit("dbus.service", requires=["dbus.socket"], after=["dbus.socket"])
    dag.add_unit("network.target", requires=[], after=["syslog.service"])
    dag.add_unit("sshd.service", requires=["network.target"], after=["network.target", "dbus.service"])
    dag.add_unit("nginx.service", requires=["network.target"], after=["network.target", "syslog.service"])

    print("1. Inspecting Unit Dependency Graph for Cycles...")
    cycles = dag.detect_cycles()
    assert len(cycles) == 0, "Graph must be strictly acyclic"
    print("   [PASS] Zero dependency cycles detected in DAG.")

    print("\n2. Computing Parallel Dispatch Waves:")
    waves = dag.compute_dispatch_waves()
    for idx, wave in enumerate(waves):
        print(f"   Wave {idx + 1} (Concurrent): {wave}")

    # Wave 1 should contain independent roots (sockets)
    assert "dbus.socket" in waves[0] and "syslog.socket" in waves[0]
    # Sshd and Nginx should be in late waves after network
    assert "sshd.service" in waves[-1] or "nginx.service" in waves[-1]

    # Verify all units marked active
    assert all(u.is_active for u in dag.units.values())
    print("\n[VERIFIED] Topological concurrency dispatcher completed with 100% fidelity!")


if __name__ == "__main__":
    main()
