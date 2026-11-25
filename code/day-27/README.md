# Hands-On Lab: Day 27 - Job Control & SIGHUP Simulator (`job_control_sim.py`)

## 1. What Are We Building & Why Does It Matter?
When you disconnect an SSH session, the Linux kernel detects that your terminal closed and broadcasts **`SIGHUP` (Signal 1 - Hangup)** to all running jobs.
Any normal background command started with `&` is immediately killed by the kernel!

To keep commands running after disconnection, engineers use:
- **`nohup command &`**: Tells the process to ignore `SIGHUP`.
- **`disown`**: Removes the job from the shell's active tracking table so no `SIGHUP` is delivered to it.

In this lab, we build `job_control_sim.py` to model the shell job table and verify how `nohup` and `disown` prevent process termination.

---

## 2. Python Concepts for Beginners
1. **Dictionaries as Registries**:
   - `self.jobs[job_id] = job` maintains the active job list.
2. **Simulating Operating System Signals**:
   - `job.receive_signal("SIGHUP")` evaluates whether the process ignores the signal.

---

## 3. Step-by-Step Code Walkthrough

```python
def terminal_hangup(self) -> dict:
    for j_id, job in list(self.jobs.items()):
        if job.in_job_table:
            job.receive_signal("SIGHUP") # Killed unless nohup active!
        else:
            # Disowned jobs bypass signal entirely!
```
- Standard jobs are killed when `SIGHUP` arrives.
- `nohup` jobs catch and ignore `SIGHUP`.
- `disowned` jobs are never sent the signal because they were delisted from the shell's tracking table.

---

## 4. How to Run the Script

```bash
cd code/day-27
python job_control_sim.py
```

### Expected Output
```
====================================================
POSIX JOB CONTROL & SIGHUP DISCONNECTION SIMULATOR
====================================================
[+] Spawned 3 background processes in session.
  Job 1: Standard background job (In table, nohup=False)
  Job 2: nohup background job    (In table, nohup=True)
  Job 3: Disowned background job (Removed from job table)

[!] SIMULATING TERMINAL CARRIER LOSS (SSH Disconnection)...

Processes Killed by SIGHUP:
  [-] KILLED: python standard_worker.py &

Processes Survived Disconnection:
  [+] SURVIVED: nohup python resilient_worker.py &
  [+] SURVIVED: python disowned_worker.py &

[SUCCESS] Job control SIGHUP immunity verified!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`ProcessLookupError: [Errno 3] No such process`**:
   - Happens if you send a signal via `os.kill(pid, sig)` to a process that has already terminated or exited. Always wrap signal dispatches in `try ... except ProcessLookupError:`.
2. **Zombie Process Accumulation**:
   - If a child process finishes but the parent never calls `os.waitpid()`, the child becomes a Zombie (`<defunct>`). Always reap terminated children.
3. **Signal Handler Restrictions**:
   - Python signal handlers run synchronously on the main interpreter thread. Heavy operations inside a signal handler can block other tasks.

---

## 6. Beginner Exercises & Challenges
1. **Simulate `kill -STOP` and `kill -CONT`**:
   - Add interactive methods to suspend a running job (`STOP`) and resume it in the background (`CONT`) or foreground (`fg`).
2. **Process Group Termination**:
   - When you press `Ctrl+C`, the kernel sends `SIGINT` to the entire process group, not just a single process. Enhance the simulator to send signals to all children sharing `pgid`.
3. **Daemonization with `disown`**:
   - Implement the `disown` command, removing a job from the shell's active job table so it survives when the parent shell terminates.
