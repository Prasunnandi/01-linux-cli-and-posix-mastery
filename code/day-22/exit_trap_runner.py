#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exit_trap_runner.py - Shell Exit Status & EXIT Trap Engine
Simulates command exit codes (0=Success, 1-255=Error) and guarantees cleanup
trap handlers execute deterministically regardless of how a script exits.
"""
import sys

class ScriptExecutionEngine:
    def __init__(self):
        self.trap_handlers = []
        self.execution_log = []

    def register_trap(self, handler_fn):
        """Registers a function to run when the script terminates (trap ... EXIT)."""
        self.trap_handlers.append(handler_fn)

    def execute_command(self, cmd_name: str, should_succeed: bool) -> int:
        if should_succeed:
            self.execution_log.append(f"EXEC: {cmd_name} -> SUCCESS (0)")
            return 0
        else:
            self.execution_log.append(f"EXEC: {cmd_name} -> FAILED (1)")
            return 1

    def run_script_safely(self, abort_on_error: bool = True) -> int:
        exit_code = 0
        try:
            # Step 1: Create temp lockfile
            self.execution_log.append("STEP 1: Created temporary lock /var/run/app.lock")

            # Step 2: Run a failing command
            code = self.execute_command("fetch_remote_payload", should_succeed=False)
            if code != 0 and abort_on_error:
                exit_code = code
                raise RuntimeError("Command failed under set -e strict mode!")

            # Step 3: Normal execution
            self.execute_command("write_database", should_succeed=True)

        except Exception as e:
            self.execution_log.append(f"ABORT: {e}")
        finally:
            # Deterministic EXIT Trap execution
            for handler in self.trap_handlers:
                handler(self.execution_log)

        return exit_code

def mock_cleanup_handler(log_target: list):
    log_target.append("TRAP TRIGGERED: rm -f /var/run/app.lock (Cleanup completed cleanly)")

if __name__ == "__main__":
    print("====================================================")
    print("SHELL EXIT STATUS & EXIT TRAP EXECUTION ENGINE")
    print("====================================================")

    engine = ScriptExecutionEngine()
    engine.register_trap(mock_cleanup_handler)
    final_exit = engine.run_script_safely(abort_on_error=True)

    print("\nExecution Trace:")
    for entry in engine.execution_log:
        print("  |--", entry)

    print(f"\nFinal Script Exit Status: {final_exit}")
    assert final_exit == 1
    assert any("TRAP TRIGGERED" in entry for entry in engine.execution_log)
    print("[SUCCESS] EXIT Trap executed deterministically despite script crash!")
