#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
param_expansion_engine.py - Pure Python Parameter Expansion Engine
Emulates native Bash parameter expansions in memory:
  - Default values (${VAR:-default})
  - Longest prefix strip (${VAR##*/})
  - Shortest suffix strip (${VAR%/*})
  - Global replacement (${VAR//pattern/replacement})
"""

def expand_default(val: str, default: str) -> str:
    """Simulates ${VAR:-default}"""
    return default if not val else val

def strip_longest_prefix(val: str, delim: str) -> str:
    """Simulates ${VAR##*delim} (like basename)"""
    idx = val.rfind(delim)
    return val[idx + len(delim):] if idx != -1 else val

def strip_shortest_suffix(val: str, delim: str) -> str:
    """Simulates ${VAR%delim*} (like dirname)"""
    idx = val.rfind(delim)
    return val[:idx] if idx != -1 else val

def replace_all(val: str, pattern: str, replacement: str) -> str:
    """Simulates ${VAR//pattern/replacement}"""
    return val.replace(pattern, replacement)

def run_parameter_expansion_tests():
    path = "/var/log/nginx/access.2026.log.gz"

    base = strip_longest_prefix(path, "/")
    dirpath = strip_shortest_suffix(path, "/")
    clean = replace_all(base, ".", "_")
    fallback = expand_default("", "fallback_service")

    assert base == "access.2026.log.gz"
    assert dirpath == "/var/log/nginx"
    assert clean == "access_2026_log_gz"
    assert fallback == "fallback_service"

    return {
        "original": path,
        "basename": base,
        "dirname": dirpath,
        "normalized": clean,
        "default_val": fallback
    }

if __name__ == "__main__":
    print("====================================================")
    print("BASH IN-MEMORY PARAMETER EXPANSION ENGINE")
    print("====================================================")
    results = run_parameter_expansion_tests()
    print("Original Path :", results["original"])
    print("  ${VAR##*/}   -> Basename   :", results["basename"])
    print("  ${VAR%/*}    -> Dirname    :", results["dirname"])
    print("  ${VAR//./_}  -> Replaced   :", results["normalized"])
    print("  ${VAR:-def}  -> Fallback   :", results["default_val"])
    print("\n[SUCCESS] In-memory expansions verified 100% correct!")
