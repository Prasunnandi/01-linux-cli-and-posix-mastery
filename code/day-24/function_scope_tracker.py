#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
function_scope_tracker.py - Shell Function Scoping & Nameref Simulator
Models variable scope stack frames, dynamic scoping rules, and demonstrates
why omitting 'local' in shell functions pollutes the global environment.
"""

class ScopeManager:
    def __init__(self):
        # List of scope dictionaries: index 0 is global
        self.scopes = [{}]

    def enter_function(self):
        """Pushes a new local scope frame onto the stack."""
        self.scopes.append({})

    def exit_function(self):
        """Pops the innermost scope frame."""
        if len(self.scopes) > 1:
            self.scopes.pop()

    def set_variable(self, name: str, value: str, is_local: bool):
        if is_local:
            # Set in current innermost scope frame
            self.scopes[-1][name] = value
        else:
            # DANGER: Global mutation (omitted 'local')
            self.scopes[0][name] = value

    def get_variable(self, name: str) -> str:
        # Search from innermost scope outwards to global
        for frame in reversed(self.scopes):
            if name in frame:
                return frame[name]
        return "(undefined)"

def test_scoping():
    sm = ScopeManager()
    sm.set_variable("i", "100", is_local=False) # Global i = 100

    # Enter helper function
    sm.enter_function()
    sm.set_variable("local_var", "secret", is_local=True)
    sm.set_variable("i", "5", is_local=False) # BUG: Omitted local! Modifies global i!

    inside_i = sm.get_variable("i")
    inside_local = sm.get_variable("local_var")

    # Exit function
    sm.exit_function()

    outside_i = sm.get_variable("i")
    outside_local = sm.get_variable("local_var")

    assert inside_i == "5"
    assert inside_local == "secret"
    assert outside_i == "5", "Global i should be mutated to 5 due to omitted local!"
    assert outside_local == "(undefined)", "Local var should have died upon function exit!"

    return {
        "inside": {"i": inside_i, "local_var": inside_local},
        "outside": {"i": outside_i, "local_var": outside_local}
    }

if __name__ == "__main__":
    print("====================================================")
    print("BASH FUNCTION SCOPE STACK & LOCAL VARIABLE SIMULATOR")
    print("====================================================")
    res = test_scoping()
    print("Inside Function Scope:")
    print("  i         :", res["inside"]["i"])
    print("  local_var :", res["inside"]["local_var"])
    print("\nOutside (Global Scope Post-Call):")
    print("  i         :", res["outside"]["i"], "(Accidentally mutated by helper!)")
    print("  local_var :", res["outside"]["local_var"], "(Cleanly destroyed)")
    print("\n[VERIFIED] Scoping mechanics and global leakage verified!")
