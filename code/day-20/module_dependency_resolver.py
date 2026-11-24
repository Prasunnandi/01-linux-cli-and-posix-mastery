#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
module_dependency_resolver.py - Kernel Module Dependency Resolver
Simulates modprobe dependency resolution via topological sorting.
"""

def resolve_module_load_order(dependency_graph: dict, target_module: str) -> list:
    visited = set()
    order = []

    def dfs(mod):
        if mod not in visited:
            visited.add(mod)
            for dep in dependency_graph.get(mod, []):
                dfs(dep)
            order.append(mod)

    if target_module not in dependency_graph:
        return [target_module]
        
    dfs(target_module)
    return order

if __name__ == "__main__":
    # Simulated modules.dep graph:
    # br_netfilter depends on bridge; bridge depends on llc and stp
    deps = {
        "br_netfilter": ["bridge"],
        "bridge": ["llc", "stp"],
        "llc": [],
        "stp": []
    }
    
    target = "br_netfilter"
    load_sequence = resolve_module_load_order(deps, target)
    print("=== Linux modprobe Dependency Resolution ===")
    print(f"Target Module Requested: {target}")
    print(f"Calculated Safe Load Order: {' -> '.join(load_sequence)}")
