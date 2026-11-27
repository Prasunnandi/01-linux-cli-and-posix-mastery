#!/usr/bin/env python3
"""
Day 44 Lab: systemd High-Resolution Timer & Calendar Scheduler
Simulates systemd timer mechanics:
- Monotonic timers (OnBootSec, OnUnitActiveSec)
- Real-time calendar events (OnCalendar)
- De-synchronization jitter (RandomizedDelaySec)
- Catch-up scheduling for missed executions (Persistent=true)
Uses Python standard library only.
"""

import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TimerJob:
    name: str
    on_calendar_interval: int          # Trigger interval in seconds
    randomized_delay_sec: int = 0      # Jitter ceiling
    persistent: bool = False           # Catch-up missed runs?
    last_trigger_timestamp: float = 0.0
    execution_history: List[float] = None

    def __post_init__(self):
        if self.execution_history is None:
            self.execution_history = []


class SystemdTimerEngine:
    def __init__(self, boot_timestamp: float = 1000.0):
        self.current_time = boot_timestamp
        self.timers: List[TimerJob] = []

    def register_timer(self, timer: TimerJob):
        if timer.last_trigger_timestamp == 0.0:
            timer.last_trigger_timestamp = self.current_time
        self.timers.append(timer)

    def advance_time(self, seconds: float) -> List[str]:
        """Advances simulated clock and triggers due timers."""
        self.current_time += seconds
        triggered = []

        for t in self.timers:
            # Check elapsed time since last run
            elapsed = self.current_time - t.last_trigger_timestamp
            effective_deadline = t.on_calendar_interval

            if elapsed >= effective_deadline:
                # Calculate randomized jitter
                jitter = random.uniform(0, t.randomized_delay_sec) if t.randomized_delay_sec > 0 else 0
                actual_run_time = self.current_time + jitter
                t.last_trigger_timestamp = self.current_time
                t.execution_history.append(actual_run_time)
                triggered.append(t.name)

        return triggered

    def simulate_reboot(self, offline_duration: float) -> List[str]:
        """Simulates machine power-off. Persistent timers must fire immediately upon boot."""
        self.current_time += offline_duration
        catch_up_triggered = []

        for t in self.timers:
            if t.persistent:
                elapsed = self.current_time - t.last_trigger_timestamp
                if elapsed >= t.on_calendar_interval:
                    t.last_trigger_timestamp = self.current_time
                    t.execution_history.append(self.current_time)
                    catch_up_triggered.append(t.name)

        return catch_up_triggered


def main():
    print("====================================================")
    print("DAY 44: systemd TIMER & CALENDAR SCHEDULER")
    print("====================================================")

    engine = SystemdTimerEngine(boot_timestamp=10000.0)

    # Timer 1: Hourly log rotation with 10-minute jitter
    timer_rotate = TimerJob(
        name="logrotate.timer",
        on_calendar_interval=3600,
        randomized_delay_sec=600,
        persistent=True
    )

    # Timer 2: Quick heartbeat every 60 seconds
    timer_heartbeat = TimerJob(
        name="heartbeat.timer",
        on_calendar_interval=60,
        randomized_delay_sec=0,
        persistent=False
    )

    engine.register_timer(timer_rotate)
    engine.register_timer(timer_heartbeat)

    print("1. Advancing clock by 65 seconds...")
    runs = engine.advance_time(65)
    assert "heartbeat.timer" in runs
    assert "logrotate.timer" not in runs
    print(f"   Triggered: {runs} (Correct: heartbeat fired, rotate did not)")

    print("\n2. Advancing clock to 3650 seconds (1 hour mark)...")
    runs2 = engine.advance_time(3600)
    assert "logrotate.timer" in runs2
    print(f"   Triggered: {runs2} (logrotate fired)")

    print("\n3. Simulating 24-hour machine power-off with Persistent=true...")
    catchup = engine.simulate_reboot(offline_duration=86400)
    assert "logrotate.timer" in catchup
    assert "heartbeat.timer" not in catchup  # Non-persistent timers are discarded
    print(f"   Catch-up executions on boot: {catchup}")
    print("   [PASS] Persistent timer executed missed run immediately upon boot!")

    print("\n[VERIFIED] systemd timer scheduler passed all temporal assertions!")


if __name__ == "__main__":
    main()
