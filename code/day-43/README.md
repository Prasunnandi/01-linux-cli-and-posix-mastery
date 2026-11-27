# Day 43: Service Lifecycle Finite State Machine Simulator

## 1. What Are We Building & Why Does It Matter?
In Linux, when you manage a service via `systemctl`, it moves through an intricate state machine.
If a service crashes repeatedly (e.g. database password is wrong), blindly restarting it millions of times per second will burn 100% CPU and flood log storage.
systemd protects against this through **Rate-Limiting Throttling (`StartLimitBurst`)** and **Exponential Backoff (`RestartSec=`)**.
In this lab, we build a **Service Lifecycle State Machine** in pure Python that models startup, graceful shutdown, crash recovery, and restart throttling.

---

## 2. Python Concepts for Beginners

### A. Python Enums (`enum.Enum`)
An `Enum` restricts a variable to a predefined set of symbolic names, eliminating spelling mistakes:
```python
from enum import Enum

class ServiceState(Enum):
    DEAD = "inactive (dead)"
    RUNNING = "active (running)"
```

### B. Mathematical Exponentiation in Python (`**`)
To calculate exponential backoff where delay doubles on each attempt ($1, 2, 4, 8$ seconds):
```python
delay = base_delay * (2 ** (attempt - 1))
```

### C. Finite State Machine (FSM) Transitions
An FSM enforces valid paths between states: a service cannot go directly from `DEAD` to `STOPPING` without first being `RUNNING`.

---

## 3. Step-by-Step Code Walkthrough

1. **`ServiceState` Enum**: Maps systemd's internal states (`DEAD`, `START_PRE`, `RUNNING`, `STOPPING`, `FAILED`, `AUTO_RESTART`).
2. **`ServiceController`**:
   - `start()`: Moves service from `DEAD` to `START_PRE` to `RUNNING`.
   - `stop()`: Performs graceful `STOPPING` to `DEAD`.
   - `crash(exit_code)`: Tracks consecutive failures; triggers exponential backoff if within limits, or locks into `FAILED` if `StartLimitBurst` is exceeded.
   - `reset_failed()`: Emulates `systemctl reset-failed`, clearing error counters.
3. **`main()` Function**: Executes an automated scenario testing normal boots, crash loops, throttling lockouts, and administrative resets.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-43/service_lifecycle_fsm.py
```

Expected output:
```text
====================================================
DAY 43: SERVICE LIFECYCLE FSM & RATE LIMITING
====================================================
1. Starting service via systemctl start...
   State: active (running)

2. Triggering Crash 1:
  [ALERT] Daemon worker.service crashed with exit code 1!
  [RESTART] Scheduling auto-restart in 1.0s (Attempt 1)...
   State: active (running)
...
4. Triggering Crash 3 (Exceeds StartLimitBurst=2):
  [THROTTLED] StartLimitBurst (2) exceeded! Refusing restart.
   State: failed (Result: exit-code)

[VERIFIED] Service Lifecycle State Machine passed all assertions!
```

---

## 5. Common Python Errors & Troubleshooting

- **`AttributeError: 'ServiceState' object has no attribute 'value'`**: When printing an enum, access `.name` for the identifier or `.value` for the assigned string.
- **Off-By-One in Backoff Exponent**: Ensure `(attempt - 1)` is used so the first restart uses $2^0 = 1 	imes 	ext{delay}$, rather than immediately quadrupling.

---

## 6. Beginner Exercises & Challenges

1. **Time-Window Expiration**: Add a timer that resets `consecutive_crashes = 0` if the service runs stably without crashing for 30 continuous seconds.
2. **Watchdog Heartbeat**: Add a `heartbeat()` method. If 5 seconds elapse without a heartbeat, trigger a watchdog failure (`exit_code = 143`).
3. **Restart Policies**: Implement `Restart=on-success` where normal exits (`exit_code == 0`) trigger restarts while errors do not.
