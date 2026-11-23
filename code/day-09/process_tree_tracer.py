"""
Day 09: Linux Process Lifecycle, Hierarchy & Zombie State Machine
Zero-Knowledge-Gap Implementation of kernel task management and process lifecycle.

Demonstrates:
1. `struct task_struct` representation in memory (PID, TGID, State, Lineage).
2. The Fork -> Exec -> Exit -> Wait state machine.
3. Creation, detection, and lifecycle of a Zombie process.
4. Adoption of an Orphan process by PID 1 (init / systemd).
"""

import enum
from typing import Dict, List, Optional


class ProcessState(enum.Enum):
    RUNNING = "R"               # TASK_RUNNING
    SLEEP_INTERRUPTIBLE = "S"   # TASK_INTERRUPTIBLE
    SLEEP_UNINTERRUPTIBLE = "D" # TASK_UNINTERRUPTIBLE
    STOPPED = "T"               # TASK_STOPPED
    ZOMBIE = "Z"                # EXIT_ZOMBIE
    DEAD = "X"                  # Reaped from process table


class TaskStruct:
    """Simulates the Linux kernel struct task_struct."""
    def __init__(self, pid: int, tgid: int, name: str, parent_pid: int = 1):
        self.pid = pid
        self.tgid = tgid
        self.name = name
        self.parent_pid = parent_pid
        self.state = ProcessState.RUNNING
        self.exit_code: Optional[int] = None
        self.open_fds = [0, 1, 2] # stdin, stdout, stderr

    def __repr__(self):
        return f"<PID {self.pid} ({self.name}) | TGID {self.tgid} | State: {self.state.value} | Parent: {self.parent_pid}>"


class KernelProcessManager:
    """Simulates the Linux scheduler process table and lifecycle syscalls."""
    def __init__(self):
        self.table: Dict[int, TaskStruct] = {}
        self.next_pid = 1

        # Bootstrap PID 1 (systemd / init)
        init_task = TaskStruct(pid=1, tgid=1, name="systemd", parent_pid=0)
        self.table[1] = init_task
        self.next_pid = 2

    def fork(self, parent_pid: int, child_name: str) -> int:
        """Simulates fork(): duplicates task into process table."""
        if parent_pid not in self.table:
            raise ValueError(f"Parent PID {parent_pid} does not exist.")

        new_pid = self.next_pid
        self.next_pid += 1

        child = TaskStruct(pid=new_pid, tgid=new_pid, name=child_name, parent_pid=parent_pid)
        self.table[new_pid] = child
        return new_pid

    def exit(self, pid: int, exit_code: int = 0):
        """
        Simulates exit(): closes descriptors, releases memory,
        and transitions task to EXIT_ZOMBIE until parent reaps it.
        """
        if pid not in self.table:
            raise ValueError(f"PID {pid} does not exist.")

        task = self.table[pid]
        task.exit_code = exit_code
        task.open_fds.clear() # Memory & descriptors freed!
        task.state = ProcessState.ZOMBIE

    def waitpid(self, parent_pid: int, child_pid: int) -> int:
        """
        Simulates waitpid(): Parent reaps zombie child, reading exit status
        and removing the task_struct from the kernel table.
        """
        if child_pid not in self.table:
            raise ValueError(f"Child PID {child_pid} not in process table.")

        child = self.table[child_pid]
        if child.parent_pid != parent_pid:
            raise PermissionError(f"PID {parent_pid} is not parent of {child_pid}")

        if child.state != ProcessState.ZOMBIE:
            raise RuntimeError(f"Child PID {child_pid} has not yet exited!")

        exit_code = child.exit_code
        # Fully deallocate task_struct from kernel table
        del self.table[child_pid]
        return exit_code

    def terminate_parent_and_reparent_orphans(self, parent_pid: int):
        """
        When a parent dies before its children, Linux kernel reparents
        all children to PID 1 (systemd).
        """
        if parent_pid <= 1:
            raise ValueError("Cannot terminate systemd (PID 1)!")

        # Find all children of this parent
        for pid, task in list(self.table.items()):
            if task.parent_pid == parent_pid:
                task.parent_pid = 1  # Reparent to PID 1!

        # Terminate the parent itself
        if parent_pid in self.table:
            del self.table[parent_pid]


# --- SELF-CONTAINED VERIFICATION LAB ---
if __name__ == "__main__":
    print("=" * 60)
    print("DAY 09 LAB: PROCESS LIFECYCLE & ZOMBIE/ORPHAN STATE MACHINE")
    print("=" * 60)

    mgr = KernelProcessManager()
    print(f"\n[1] Kernel Bootstrapped: PID 1 active -> {mgr.table[1]}")

    # 1. Spawn a parent server process (e.g. nginx worker master)
    nginx_pid = mgr.fork(parent_pid=1, child_name="nginx-master")
    print(f"[2] Spawned Parent: PID {nginx_pid} -> {mgr.table[nginx_pid]}")

    # 2. Parent spawns a short-lived worker child
    worker_pid = mgr.fork(parent_pid=nginx_pid, child_name="nginx-worker-1")
    print(f"[3] Spawned Worker Child: PID {worker_pid} -> {mgr.table[worker_pid]}")

    # 3. Worker finishes work and exits without parent waiting
    mgr.exit(worker_pid, exit_code=0)
    print(f"\n[4] Worker Exited! Checking State:")
    print(f"    Worker: {mgr.table[worker_pid]}")
    assert mgr.table[worker_pid].state == ProcessState.ZOMBIE, "Process should be in ZOMBIE state!"
    print("    [PASS] Worker is now EXIT_ZOMBIE (memory freed, awaiting parent waitpid).")

    # 4. Parent reaps child
    exit_status = mgr.waitpid(parent_pid=nginx_pid, child_pid=worker_pid)
    print(f"\n[5] Parent executed waitpid({worker_pid}): Collected exit code {exit_status}")
    assert worker_pid not in mgr.table, "Worker task_struct should be completely purged from process table!"
    print("    [PASS] Zombie successfully reaped and cleared from process table.")

    # 5. Simulate Orphan scenario
    api_pid = mgr.fork(parent_pid=1, child_name="python-api")
    bg_job_pid = mgr.fork(parent_pid=api_pid, child_name="background-worker")
    print(f"\n[6] Created API (PID {api_pid}) and Background Job (PID {bg_job_pid})")
    print(f"    Background Job Parent before crash: {mgr.table[bg_job_pid].parent_pid}")

    # API crashes unexpectedly
    mgr.terminate_parent_and_reparent_orphans(parent_pid=api_pid)
    print(f"[7] Parent (PID {api_pid}) crashed! Inspecting orphaned Background Job:")
    print(f"    Background Job: {mgr.table[bg_job_pid]}")
    assert mgr.table[bg_job_pid].parent_pid == 1, "Orphaned process MUST be adopted by PID 1 (systemd)!"
    print("    [PASS] Orphan successfully re-parented to PID 1.")

    print("\n" + "=" * 60)
    print("ALL DAY 09 VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 60)
