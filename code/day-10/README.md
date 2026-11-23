# Day 10 Lab: POSIX Signals & Graceful Shutdowns in Python

> **Welcome to Day 10!** When a container in Kubernetes or Docker is stopped, the operating system doesn't immediately pull the plug. It sends a polite signal: **`SIGTERM` (Signal 15)**.
> In this lab, you will learn how to trap signals in Python so your service finishes active user transactions before shutting down cleanly!

---

## 🎯 What Does This Lab Do?
`graceful_shutdown_daemon.py` demonstrates:
1. **Signal Interception**: Listening for `SIGINT` (`Ctrl+C`), `SIGTERM` (Kubernetes shutdown), and `SIGHUP` (configuration reload).
2. **The Atomic Flag Pattern**: Why a signal handler should never do heavy work directly (avoiding deadlocks), and should instead set a boolean flag like `shutdown_requested = True`.
3. **In-Flight Task Draining**: Allowing active payments or database queries to complete cleanly before closing connections and exiting with code 0.

---

## 🚀 How to Run the Code
Run the script in your terminal:
```bash
python graceful_shutdown_daemon.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. `import signal` (Handling Operating System Events)
* In Python, the `signal` library lets you intercept OS notifications.
* Registering a handler looks like this:
  ```python
  signal.signal(signal.SIGINT, my_handler_function)
  ```
  Whenever the user presses `Ctrl+C`, Python pauses normal execution and immediately calls `my_handler_function`.

### 2. Signal Handler Signature: `(signum, frame)`
* When Python calls your signal handler, it passes two arguments:
  - `signum`: The integer number of the signal (e.g. `15` for SIGTERM).
  - `frame`: The current execution stack frame (used for advanced debugging).

### 3. List Queue Draining with `.pop(0)`
* `self.in_flight_tasks.pop(0)` removes and returns the first task in the list (First-In, First-Out / FIFO queue).
* A `while self.in_flight_tasks:` loop continues until every single pending task has been processed!

### 4. Cross-Platform Portability: `hasattr(signal, "SIGHUP")`
* Linux and macOS support `SIGHUP` (Signal 1 - Hangup/Reload).
* Windows does not have `SIGHUP`.
* `hasattr(signal, "SIGHUP")` checks if the current operating system supports it, preventing `AttributeError` crashes on Windows!

---

## 🔍 Code Walkthrough

```python
import signal
import sys

class GracefulServiceDaemon:
    def __init__(self):
        self.shutdown_requested = False
        self.in_flight_tasks = []

    def register_signal_handlers(self):
        # Intercept Ctrl+C (SIGINT) and Docker shutdown (SIGTERM)
        signal.signal(signal.SIGINT, self._handle_termination)
        signal.signal(signal.SIGTERM, self._handle_termination)

    def _handle_termination(self, signum, frame):
        # Async-signal safe: ONLY set a flag!
        sys.stderr.write(f"\n[INTERCEPTED SIGNAL {signum}] Shutting down...\n")
        self.shutdown_requested = True

    def drain_and_shutdown(self):
        # Finish all active work before exiting
        while self.in_flight_tasks:
            task = self.in_flight_tasks.pop(0)
            print(f"Draining task: {task} -> SUCCESS")
        print("All tasks settled. Releasing DB connections.")
```

---

## 📋 Expected Terminal Output
```text
[INTERCEPTED SIGTERM (15)] Setting shutdown flag...
============================================================
DAY 10 LAB: POSIX SIGNAL HANDLING & GRACEFUL SHUTDOWN
============================================================

[1] Daemon started with 3 in-flight transactions:
    - TX-1001: Auth $45.00
    - TX-1002: Capture $120.50
    - TX-1003: Settle $89.00

[2] (SIGHUP skipped on Windows platform)

[3] Dispatching simulated SIGTERM (Signal 15)...
    [PASS] Signal caught safely; shutdown flag armed.

[4] Executing orderly drain of in-flight work...
[payment-processor] Initiating graceful drain...
[payment-processor] Draining in-flight task: 'TX-1001: Auth $45.00' -> SUCCESS
[payment-processor] Draining in-flight task: 'TX-1002: Capture $120.50' -> SUCCESS
[payment-processor] Draining in-flight task: 'TX-1003: Settle $89.00' -> SUCCESS
[payment-processor] All in-flight requests settled. Releasing DB connection pools.

[5] Drain Result: {'status': 'CLEAN_SHUTDOWN', 'drained_count': 3, 'remaining_tasks': 0}
    [PASS] All transactions safely settled before exit with zero data loss.
============================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: What is the difference between `SIGTERM` (15) and `SIGKILL` (9)? Can Python intercept `SIGKILL`? (Answer: No! `SIGKILL` destroys the process instantly in kernel space).
2. **Challenge 2**: Run `python graceful_shutdown_daemon.py` and observe how it guarantees zero data loss during microservice shutdowns.
