#!/usr/bin/env python3
"""
Day 43 Lab: Service Lifecycle Finite State Machine (FSM) Simulator
Models systemd's service lifecycle state machine:
DEAD -> START_PRE -> RUNNING -> STOP_SIGTERM -> DEAD.
Includes exponential backoff restart rate-limiting (StartLimitBurst).
Uses Python standard library only.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ServiceState(Enum):
    DEAD = "inactive (dead)"
    START_PRE = "activating (start-pre)"
    RUNNING = "active (running)"
    STOPPING = "deactivating (stop-sigterm)"
    FAILED = "failed (Result: exit-code)"
    AUTO_RESTART = "activating (auto-restart)"


@dataclass
class ServiceController:
    name: str
    restart_policy: str = "on-failure"  # 'no', 'always', 'on-failure'
    start_limit_burst: int = 3          # Max restarts within interval
    restart_sec: float = 1.0            # Initial delay
    current_state: ServiceState = ServiceState.DEAD
    consecutive_crashes: int = 0
    state_history: List[ServiceState] = field(default_factory=list)

    def transition_to(self, new_state: ServiceState):
        self.current_state = new_state
        self.state_history.append(new_state)

    def start(self) -> bool:
        if self.current_state != ServiceState.DEAD:
            return False
        self.transition_to(ServiceState.START_PRE)
        # Execute ExecStartPre
        self.transition_to(ServiceState.RUNNING)
        return True

    def stop(self) -> bool:
        if self.current_state not in (ServiceState.RUNNING, ServiceState.FAILED):
            return False
        self.transition_to(ServiceState.STOPPING)
        # Send SIGTERM and await exit
        self.transition_to(ServiceState.DEAD)
        self.consecutive_crashes = 0
        return True

    def crash(self, exit_code: int = 1):
        """Simulates daemon unexpected termination."""
        print(f"  [ALERT] Daemon {self.name} crashed with exit code {exit_code}!")
        self.consecutive_crashes += 1

        if self.restart_policy in ("always", "on-failure") and exit_code != 0:
            if self.consecutive_crashes > self.start_limit_burst:
                print(f"  [THROTTLED] StartLimitBurst ({self.start_limit_burst}) exceeded! Refusing restart.")
                self.transition_to(ServiceState.FAILED)
            else:
                backoff_delay = self.restart_sec * (2 ** (self.consecutive_crashes - 1))
                print(f"  [RESTART] Scheduling auto-restart in {backoff_delay:.1f}s (Attempt {self.consecutive_crashes})...")
                self.transition_to(ServiceState.AUTO_RESTART)
                self.transition_to(ServiceState.RUNNING)
        else:
            self.transition_to(ServiceState.FAILED)

    def reset_failed(self):
        """Emulates `systemctl reset-failed`."""
        self.consecutive_crashes = 0
        self.transition_to(ServiceState.DEAD)


def main():
    print("====================================================")
    print("DAY 43: SERVICE LIFECYCLE FSM & RATE LIMITING")
    print("====================================================")

    svc = ServiceController(name="worker.service", restart_policy="on-failure", start_limit_burst=2)

    # 1. Normal clean startup
    print("1. Starting service via systemctl start...")
    svc.start()
    assert svc.current_state == ServiceState.RUNNING
    print(f"   State: {svc.current_state.value}")

    # 2. Crash 1: Should auto-restart (Attempt 1 of 2)
    print("\n2. Triggering Crash 1:")
    svc.crash(exit_code=1)
    assert svc.current_state == ServiceState.RUNNING
    print(f"   State: {svc.current_state.value}")

    # 3. Crash 2: Should auto-restart (Attempt 2 of 2)
    print("\n3. Triggering Crash 2:")
    svc.crash(exit_code=137)  # OOM Kill
    assert svc.current_state == ServiceState.RUNNING
    print(f"   State: {svc.current_state.value}")

    # 4. Crash 3: Exceeds burst limit! Must enter FAILED state
    print("\n4. Triggering Crash 3 (Exceeds StartLimitBurst=2):")
    svc.crash(exit_code=1)
    assert svc.current_state == ServiceState.FAILED
    print(f"   State: {svc.current_state.value}")

    # 5. Admin intervention: systemctl reset-failed
    print("\n5. Executing systemctl reset-failed...")
    svc.reset_failed()
    assert svc.current_state == ServiceState.DEAD
    print(f"   State: {svc.current_state.value}")

    svc.start()
    assert svc.current_state == ServiceState.RUNNING
    print(f"   Service cleanly restarted after reset: {svc.current_state.value}")

    print("\n[VERIFIED] Service Lifecycle State Machine passed all assertions!")


if __name__ == "__main__":
    main()
