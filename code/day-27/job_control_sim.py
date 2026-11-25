#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
job_control_sim.py - POSIX Job Control & SIGHUP Simulator
Demonstrates Process Groups, Sessions, Background Job execution (&),
and how nohup/disown protect processes when a terminal disconnects.
"""

class Job:
    def __init__(self, job_id: int, pid: int, command: str, ignore_sighup: bool, in_job_table: bool):
        self.job_id = job_id
        self.pid = pid
        self.command = command
        self.ignore_sighup = ignore_sighup
        self.in_job_table = in_job_table
        self.alive = True

    def receive_signal(self, sig_name: str) -> bool:
        if sig_name == "SIGHUP" and self.ignore_sighup:
            return True # Survived SIGHUP!
        self.alive = False
        return False

class ShellSession:
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.jobs = {}
        self.next_job_id = 1

    def spawn_job(self, command: str, use_nohup: bool = False) -> Job:
        job = Job(
            job_id=self.next_job_id,
            pid=2000 + self.next_job_id,
            command=command,
            ignore_sighup=use_nohup,
            in_job_table=True
        )
        self.jobs[self.next_job_id] = job
        self.next_job_id += 1
        return job

    def disown_job(self, job_id: int):
        if job_id in self.jobs:
            self.jobs[job_id].in_job_table = False

    def terminal_hangup(self) -> dict:
        """Simulates SSH disconnection: shell sends SIGHUP to all tracked jobs."""
        survived = []
        killed = []
        for j_id, job in list(self.jobs.items()):
            if job.in_job_table:
                # Dispatches SIGHUP
                if job.receive_signal("SIGHUP"):
                    survived.append(job.command)
                else:
                    killed.append(job.command)
            else:
                # Disowned jobs receive NO signal from shell!
                survived.append(job.command)
        return {"survived": survived, "killed": killed}

if __name__ == "__main__":
    print("====================================================")
    print("POSIX JOB CONTROL & SIGHUP DISCONNECTION SIMULATOR")
    print("====================================================")

    session = ShellSession(session_id=500)

    # Job 1: Standard background command (no protection)
    j1 = session.spawn_job("python standard_worker.py &", use_nohup=False)

    # Job 2: nohup command
    j2 = session.spawn_job("nohup python resilient_worker.py &", use_nohup=True)

    # Job 3: disowned command
    j3 = session.spawn_job("python disowned_worker.py &", use_nohup=False)
    session.disown_job(j3.job_id)

    print("[+] Spawned 3 background processes in session.")
    print("  Job 1: Standard background job (In table, nohup=False)")
    print("  Job 2: nohup background job    (In table, nohup=True)")
    print("  Job 3: Disowned background job (Removed from job table)")

    print("\n[!] SIMULATING TERMINAL CARRIER LOSS (SSH Disconnection)...")
    outcome = session.terminal_hangup()

    print("\nProcesses Killed by SIGHUP:")
    for k in outcome["killed"]:
        print(f"  [-] KILLED: {k}")

    print("\nProcesses Survived Disconnection:")
    for s in outcome["survived"]:
        print(f"  [+] SURVIVED: {s}")

    assert "python standard_worker.py &" in outcome["killed"]
    assert "nohup python resilient_worker.py &" in outcome["survived"]
    assert "python disowned_worker.py &" in outcome["survived"]
    print("\n[SUCCESS] Job control SIGHUP immunity verified!")
