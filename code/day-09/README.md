# Day 09 Lab: Process Lifecycle, Zombie States & PID 1 in Python

> **Welcome to Day 9!** In this lab, we build a complete software simulation of the Linux operating system process table and scheduler state machine, modeling `fork()`, `exec()`, `exit()`, and `waitpid()`.

---

## 🎯 What Does This Lab Do?
`process_tree_tracer.py` simulates:
1. **The Life of a Process**: Spawning a child process (`fork`), having the child do work, and cleanly terminating (`exit`).
2. **The Mystery of Zombie Processes (`Z` state)**: Proving why dead processes stay in the process table until their parent calls `waitpid()` to read their exit code.
3. **The Orphan Process Rescue**: Proving that when a parent process crashes, the Linux kernel automatically re-parents all abandoned children to **PID 1 (`systemd`)**, preventing permanent zombie leaks!

---

## 🚀 How to Run the Code
Run the script in your terminal:
```bash
python process_tree_tracer.py
```

---

## 💡 Python Concepts Used in This Script (For Beginners)

### 1. Enumerations (`import enum`)
* In Python, an `Enum` is a way to define a fixed list of allowed choices with friendly names:
  ```python
  class ProcessState(enum.Enum):
      RUNNING = "R"
      SLEEP_INTERRUPTIBLE = "S"
      SLEEP_UNINTERRUPTIBLE = "D"
      ZOMBIE = "Z"
  ```
* This prevents typos (e.g. typing `"Runing"` by mistake).

### 2. Python Classes & `__init__`
* A class is like a blueprint for an object.
* `TaskStruct` models the Linux kernel's internal `struct task_struct`:
  ```python
  class TaskStruct:
      def __init__(self, pid: int, tgid: int, name: str, parent_pid: int = 1):
          self.pid = pid
          self.tgid = tgid
          self.name = name
          self.parent_pid = parent_pid
          self.state = ProcessState.RUNNING
  ```

### 3. Custom String Printing with `__repr__`
* When you write `print(task)`, Python calls `task.__repr__()` behind the scenes.
* By defining `__repr__`, we can format our process nicely:
  ```python
  def __repr__(self):
      return f"<PID {self.pid} ({self.name}) | State: {self.state.value} | Parent: {self.parent_pid}>"
  ```

### 4. Deleting Dictionary Entries with `del`
* In Python, `del my_dict[key]` completely deletes an entry from the dictionary.
* This is exactly how `waitpid()` reaps a dead zombie from the kernel's memory!

---

## 🔍 Code Walkthrough

```python
# 1. Spawning a process:
worker_pid = mgr.fork(parent_pid=nginx_pid, child_name="nginx-worker-1")

# 2. Worker completes work and exits:
# Notice: descriptors and memory are freed, but task enters ZOMBIE state!
mgr.exit(worker_pid, exit_code=0)
print(f"State: {mgr.table[worker_pid].state}") # Output: ProcessState.ZOMBIE

# 3. Parent calls waitpid() to collect exit status and reap:
mgr.waitpid(parent_pid=nginx_pid, child_pid=worker_pid)
# Now the PID is completely freed and removed from the table!

# 4. Orphan handling:
# If parent dies first, loop through children and set child.parent_pid = 1 (systemd)!
for pid, task in mgr.table.items():
    if task.parent_pid == crashed_parent_pid:
        task.parent_pid = 1
```

---

## 📋 Expected Terminal Output
```text
============================================================
DAY 09 LAB: PROCESS LIFECYCLE & ZOMBIE/ORPHAN STATE MACHINE
============================================================

[1] Kernel Bootstrapped: PID 1 active -> <PID 1 (systemd) | TGID 1 | State: R | Parent: 0>
[2] Spawned Parent: PID 2 -> <PID 2 (nginx-master) | TGID 2 | State: R | Parent: 1>
[3] Spawned Worker Child: PID 3 -> <PID 3 (nginx-worker-1) | TGID 3 | State: R | Parent: 2>

[4] Worker Exited! Checking State:
    Worker: <PID 3 (nginx-worker-1) | TGID 3 | State: Z | Parent: 2>
    [PASS] Worker is now EXIT_ZOMBIE (memory freed, awaiting parent waitpid).

[5] Parent executed waitpid(3): Collected exit code 0
    [PASS] Zombie successfully reaped and cleared from process table.

[6] Created API (PID 4) and Background Job (PID 5)
    Background Job Parent before crash: 4
[7] Parent (PID 4) crashed! Inspecting orphaned Background Job:
    Background Job: <PID 5 (background-worker) | TGID 5 | State: R | Parent: 1>
    [PASS] Orphan successfully re-parented to PID 1.
============================================================
```

---

## 🧪 Beginner Practice Challenges
1. **Challenge 1**: Look at step [4]. Why does a zombie process consume 0% CPU and 0 bytes of RAM, but still show up in `ps`?
2. **Challenge 2**: What would happen if a parent spawned 50,000 children in an infinite loop without ever calling `waitpid()`? (Answer: You hit `pid_max` and the server cannot spawn any new processes!).
