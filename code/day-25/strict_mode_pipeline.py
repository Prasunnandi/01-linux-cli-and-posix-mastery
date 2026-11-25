#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strict_mode_pipeline.py - Strict Mode & Pipeline Status Evaluator
Simulates the behavior of Bash 'set -e', 'set -u', and 'set -o pipefail'.
"""

def evaluate_pipeline(command_exit_codes: list, pipefail: bool) -> int:
    """
    Simulates pipeline exit code determination.
    If pipefail is False: returns exit code of last command.
    If pipefail is True: returns rightmost non-zero exit code, or 0 if all succeed.
    """
    if not command_exit_codes:
        return 0

    if not pipefail:
        return command_exit_codes[-1]

    for code in reversed(command_exit_codes):
        if code != 0:
            return code
    return 0

def check_unbound_variable(env: dict, var_name: str, nounset: bool) -> str:
    """Simulates 'set -u' (nounset) behavior."""
    if var_name not in env or env[var_name] is None:
        if nounset:
            raise KeyError(f"bash: {var_name}: unbound variable (set -u aborted script!)")
        return "" # Default lax behavior: empty string
    return env[var_name]

if __name__ == "__main__":
    print("====================================================")
    print("BASH STRICT MODE & PIPELINE EXIT EVALUATOR")
    print("====================================================")

    # Scenario: mysqldump (fails with 2) | gzip (succeeds with 0)
    pipeline = [2, 0]

    code_lax = evaluate_pipeline(pipeline, pipefail=False)
    code_strict = evaluate_pipeline(pipeline, pipefail=True)

    print("Pipeline: [mysqldump (exit: 2)] | [gzip (exit: 0)]")
    print("  Lax Bash Mode (default)      : Exit Code %d (ERROR MASKED!)" % code_lax)
    print("  Strict Mode (set -o pipefail): Exit Code %d (FAILURE DETECTED)" % code_strict)

    assert code_lax == 0
    assert code_strict == 2

    print("\nTesting 'set -u' (nounset) Variable Safety:")
    env = {"USER": "admin"}

    # Reference unset variable under lax mode
    val_lax = check_unbound_variable(env, "DATABASE_DIR", nounset=False)
    print("  Lax mode on unset $DATABASE_DIR: '%s' (Dangerous empty string!)" % val_lax)

    # Reference unset variable under strict mode
    try:
        check_unbound_variable(env, "DATABASE_DIR", nounset=True)
    except KeyError as e:
        print("  Strict mode on unset $DATABASE_DIR: Caught %s" % e)

    print("\n[SUCCESS] Strict mode protections verified operational!")
