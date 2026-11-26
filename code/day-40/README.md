# Hands-On Lab: Day 40 - OpenSSH ControlMaster Multiplexing (`ssh_multiplexing_sim.py`)

## 1. What Are We Building & Why Does It Matter?
When automating remote servers with tools like **Ansible** or shell loops (`for host in $SERVERS; do ssh $host ...`), establishing an SSH connection over high-latency WAN connections takes 300ms to 600ms per command due to TCP handshakes, Diffie-Hellman key exchanges, and asymmetric crypto authentication.
A task running 50 sequential commands wastes over 25 seconds on handshakes alone!

**OpenSSH ControlMaster (Multiplexing)** eliminates this delay completely:
- The first connection creates a persistent master process and a local UNIX domain socket (`ControlPath`).
- All subsequent connections connect to the local socket and transmit commands over the **already authenticated master connection** in less than **2 milliseconds**!
- `ControlPersist` keeps the master connection alive in the background for a configurable period (e.g. 30 minutes).

In this lab, we build a simulator modeling the complete ControlMaster and ControlPersist lifecycle.

---

## 2. Python Concepts for Beginners
1. **Time Tracking with `time.time()`**:
   - `time.time()` returns the current Unix timestamp in floating-point seconds.
   - `now - self.last_activity` calculates elapsed idle time to evaluate `ControlPersist` expiration.
2. **Class State Machines**:
   - The `OpenSSHControlMaster` class encapsulates internal state (`is_master_active`, `active_sessions`) and enforces business rules on connection creation.
3. **`time.sleep()` for Testing Timeouts**:
   - Pauses execution for a specified duration to verify that timeouts expire as designed.

---

## 3. Step-by-Step Code Walkthrough

```python
if not self.is_master_active:
    self.start_master()
    latency = 500.0  # Cold connection (500ms)
else:
    latency = 2.0    # Warm multiplexed reuse (2ms!)
```
- The first command pays the full 500ms connection penalty.
- Subsequent commands reuse the existing master, executing in 2ms (250x faster!).

```python
if self.is_master_active and not self.active_sessions:
    if (now - self.last_activity) > self.persist_timeout_s:
        self.is_master_active = False  # Master timed out!
```
- If the session sits idle with no active commands for longer than `ControlPersist`, the master cleanly daemonizes and shuts down.

---

## 4. How to Run the Script

```bash
cd code/day-40
python ssh_multiplexing_sim.py
```

### Expected Output
```
====================================================
DAY 40: OPENSSH CONTROLMASTER MULTIPLEXING SIMULATOR
====================================================
Target Host  : prod-web01.corp.internal
ControlPath  : /tmp/ssh-ctrl-admin@prod-web01:22

Command 1 ('uptime')  -> Handshake Latency: 500.0 ms (COLD MASTER)
Command 2 ('df -h')   -> Handshake Latency: 2.0 ms (MULTIPLEXED REUSE!)
Command 3 ('free -m') -> Handshake Latency: 2.0 ms (MULTIPLEXED REUSE!)

Simulating 1.2s idle gap (ControlPersist timeout)...
Command 4 ('whoami')  -> Handshake Latency: 500.0 ms (MASTER EXPIRED -> RE-SPAWN)
-------------------------------------------------------
[VERIFIED] OpenSSH ControlMaster connection reuse and ControlPersist lifecycle validated!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`KeyError` when Closing Inactive Sessions**:
   - Calling `del self.active_sessions[session_id]` crashes if the session ID does not exist. Guard with `if session_id in self.active_sessions:`.
2. **Time Drift with Floating Points**:
   - Floating point subtraction `time.time() - last_time` can have minute floating point inaccuracies. Always use `>=` or `>` for timeout comparisons.

---

## 6. Beginner Exercises & Challenges
1. **Calculate Total Time Saved**: Track cumulative elapsed time with multiplexing versus what it would have taken without multiplexing ($500	ext{ms} 	imes N$). Display total seconds saved!
2. **Add Maximum Concurrent Sessions Limit**: OpenSSH has `MaxSessions 10` in `sshd_config`. Limit active concurrent sessions in the simulator and reject new requests if max sessions are reached.
