"""
Day 10: Production-Grade Graceful Shutdown & POSIX Signal Engine
Zero-Knowledge-Gap Implementation of robust container & server shutdown traps.

Demonstrates:
1. Signal interception (SIGINT, SIGTERM, SIGHUP).
2. Atomic shutdown flag pattern (async-signal-safe decoupling).
3. In-flight request draining and resource cleanup before process exit.
4. Programmatic simulation of signal dispatch to verify lifecycle behavior.
"""

import signal
import sys
import time
import os
from typing import List, Dict, Any


class GracefulServiceDaemon:
    """
    Demonstrates how enterprise microservices safely intercept SIGTERM/SIGINT
    to prevent data corruption during Kubernetes pod evacuations or system shutdowns.
    """
    def __init__(self, service_name: str = "payment-gateway"):
        self.service_name = service_name
        self.is_running = False
        self.shutdown_requested = False
        self.reload_requested = False
        self.in_flight_tasks: List[str] = []
        self.config_version = 1

    def register_signal_handlers(self):
        """Registers handlers for SIGINT, SIGTERM, and SIGHUP (where available)."""
        # SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, self._handle_termination_signal)
        # SIGTERM (Polite shutdown from Docker/K8s/systemd)
        signal.signal(signal.SIGTERM, self._handle_termination_signal)

        # SIGHUP (Configuration reload - POSIX only)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._handle_reload_signal)

    def _handle_termination_signal(self, signum: int, frame):
        """
        Async-signal-safe handler: Does not perform heavy I/O or locking.
        Only sets atomic flag to instruct the main loop to initiate drain.
        """
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        # Using sys.stderr.write as a low-level immediate write
        sys.stderr.write(f"\n[INTERCEPTED {sig_name} ({signum})] Setting shutdown flag...\n")
        self.shutdown_requested = True

    def _handle_reload_signal(self, signum: int, frame):
        """SIGHUP handler for reloading configurations dynamically."""
        sys.stderr.write(f"\n[INTERCEPTED SIGHUP ({signum})] Scheduling config reload...\n")
        self.reload_requested = True

    def drain_and_shutdown(self) -> Dict[str, Any]:
        """
        Flushes and completes all in-flight work before releasing system resources.
        """
        print(f"[{self.service_name}] Initiating graceful drain...")
        completed_tasks = []

        while self.in_flight_tasks:
            task = self.in_flight_tasks.pop(0)
            print(f"[{self.service_name}] Draining in-flight task: '{task}' -> SUCCESS")
            completed_tasks.append(task)

        print(f"[{self.service_name}] All in-flight requests settled. Releasing DB connection pools.")
        self.is_running = False
        return {
            "status": "CLEAN_SHUTDOWN",
            "drained_count": len(completed_tasks),
            "remaining_tasks": len(self.in_flight_tasks)
        }

    def reload_configuration(self):
        self.config_version += 1
        self.reload_requested = False
        print(f"[{self.service_name}] Configuration reloaded live to v{self.config_version} without downtime!")


# --- SELF-CONTAINED VERIFICATION LAB ---
if __name__ == "__main__":
    print("=" * 60)
    print("DAY 10 LAB: POSIX SIGNAL HANDLING & GRACEFUL SHUTDOWN")
    print("=" * 60)

    daemon = GracefulServiceDaemon(service_name="payment-processor")
    daemon.register_signal_handlers()

    # 1. Enqueue simulated active payment transactions
    daemon.in_flight_tasks = [
        "TX-1001: Auth $45.00",
        "TX-1002: Capture $120.50",
        "TX-1003: Settle $89.00"
    ]
    print(f"\n[1] Daemon started with {len(daemon.in_flight_tasks)} in-flight transactions:")
    for t in daemon.in_flight_tasks:
        print(f"    - {t}")

    # 2. Simulate SIGHUP configuration reload if available
    if hasattr(signal, "SIGHUP"):
        print("\n[2] Dispatching simulated SIGHUP (Signal 1)...")
        daemon._handle_reload_signal(signal.SIGHUP, None)
        assert daemon.reload_requested is True, "Reload flag should be set!"
        daemon.reload_configuration()
        assert daemon.config_version == 2, "Config version should have incremented!"
        print("    [PASS] SIGHUP dynamic reload verified.")
    else:
        print("\n[2] (SIGHUP skipped on Windows platform)")

    # 3. Simulate SIGTERM reception (like Kubernetes pod termination)
    print("\n[3] Dispatching simulated SIGTERM (Signal 15)...")
    daemon._handle_termination_signal(signal.SIGTERM, None)
    assert daemon.shutdown_requested is True, "Shutdown flag MUST be set!"
    print("    [PASS] Signal caught safely; shutdown flag armed.")

    # 4. Perform graceful drain
    print("\n[4] Executing orderly drain of in-flight work...")
    result = daemon.drain_and_shutdown()

    assert result["status"] == "CLEAN_SHUTDOWN", "Shutdown status failed!"
    assert result["drained_count"] == 3, f"Expected 3 tasks drained, got {result['drained_count']}"
    assert result["remaining_tasks"] == 0, "No pending tasks should remain!"
    print(f"\n[5] Drain Result: {result}")
    print("    [PASS] All transactions safely settled before exit with zero data loss.")

    print("\n" + "=" * 60)
    print("ALL DAY 10 VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 60)
