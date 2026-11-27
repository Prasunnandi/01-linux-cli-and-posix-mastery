# Day 44: systemd High-Resolution Timer & Calendar Scheduler

## 1. What Are We Building & Why Does It Matter?
For decades, UNIX scheduled recurring tasks using `cron`. However, cron has severe limitations:
- If 10,000 servers run a cron job at midnight, all 10,000 hit central storage at the exact same millisecond (**Thundering Herd**).
- If a laptop is closed or a server is powered off during the cron minute, the task is **lost forever**.

`systemd` timers solve both problems:
1. **`RandomizedDelaySec=`**: Adds random jitter to spread server load across a window.
2. **`Persistent=true`**: Records timestamps on disk; if a scheduled run was missed while powered off, systemd triggers it immediately upon boot!

In this lab, we build an **Event Scheduler Engine** in pure Python that models monotonic intervals, calendar triggers, jitter, and persistent catch-up.

---

## 2. Python Concepts for Beginners

### A. The `random.uniform()` Function
To generate floating-point jitter between 0 and `RandomizedDelaySec`:
```python
import random
jitter = random.uniform(0, 300)  # Random float between 0.0 and 300.0 seconds
```

### B. Post-Initialization with Dataclasses (`__post_init__`)
When a dataclass field needs default mutable objects (like a list):
```python
def __post_init__(self):
    if self.execution_history is None:
        self.execution_history = []
```

### C. Synthetic Time Simulation
Instead of waiting real minutes with `time.sleep()`, we increment a virtual clock variable (`self.current_time += 3600`). This allows testing 24-hour schedules in 5 milliseconds!

---

## 3. Step-by-Step Code Walkthrough

1. **`TimerJob`**: Stores timer parameters: interval, randomized delay ceiling, persistence flag, and execution history.
2. **`advance_time(seconds)`**: Advances the virtual clock, calculates elapsed time, applies random jitter, and triggers due timers.
3. **`simulate_reboot(offline_duration)`**: Advances virtual time by hours/days to simulate a machine shutdown, immediately firing any timer flagged with `persistent=True`.
4. **`main()` Function**: Verifies short-interval heartbeats, hourly rotations with jitter, and persistent catch-up behavior.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-44/monotonic_calendar_timer_sim.py
```

Expected output:
```text
====================================================
DAY 44: systemd TIMER & CALENDAR SCHEDULER
====================================================
1. Advancing clock by 65 seconds...
   Triggered: ['heartbeat.timer'] (Correct: heartbeat fired, rotate did not)

2. Advancing clock to 3650 seconds (1 hour mark)...
   Triggered: ['logrotate.timer', 'heartbeat.timer'] (logrotate fired)

3. Simulating 24-hour machine power-off with Persistent=true...
   Catch-up executions on boot: ['logrotate.timer']
   [PASS] Persistent timer executed missed run immediately upon boot!

[VERIFIED] systemd timer scheduler passed all temporal assertions!
```

---

## 5. Common Python Errors & Troubleshooting

- **`TypeError: unsupported operand type for +`**: Ensure timestamp variables are numbers (integers or floats), not string representations.
- **Mutable Default Arguments**: Never write `execution_history: List = []` directly in dataclass definitions. Always use `field(default_factory=list)` or `__post_init__`.

---

## 6. Beginner Exercises & Challenges

1. **OnBootSec Implementation**: Add an `on_boot_sec` parameter that schedules a task to run 15 seconds after `boot_timestamp`, regardless of calendar time.
2. **Execution Counter Limit**: Add a `max_runs` parameter that automatically disables the timer once it has executed a given number of times.
3. **Calendar Expression Parser**: Write a function that parses simple strings like `hourly` into 3600s, and `daily` into 86400s.
