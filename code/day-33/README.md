# Hands-On Lab: Day 33 - Socket Telemetry Analyzer (`socket_telemetry_analyzer.py`)

## 1. What Are We Building & Why Does It Matter?
When a high-traffic production service (like a PostgreSQL database or Nginx web server) becomes sluggish, systems engineers inspect socket telemetry using `ss -tulpn`.
Many engineers misunderstand the `Recv-Q` and `Send-Q` columns:
- On **Listening sockets (`LISTEN`)**, `Send-Q` represents the maximum backlog size configured by `listen(backlog)`, and `Recv-Q` represents the number of clients currently waiting in the kernel queue for the application to call `accept()`.
- If `Recv-Q >= Send-Q`, the application cannot keep up, and the Linux kernel is actively **dropping incoming TCP connection requests**!

In this lab, we build `socket_telemetry_analyzer.py` to parse simulated `inet_diag` socket metrics and detect backlog overflows and stalled sender queues.

---

## 2. Python Concepts for Beginners
1. **Dictionary Unpacking (`**kwargs`)**:
   - `SocketEntry(**e)` takes a dictionary `{"protocol": "tcp", "state": "LISTEN"...}` and automatically unpacks key-value pairs as keyword arguments to the `SocketEntry` constructor.
2. **List Comprehensions with Filtering**:
   - `[s for s in self.sockets if s.is_backlog_saturated]` cleanly filters the list down to only items that satisfy the boolean condition.
3. **Format Alignment in F-Strings**:
   - `{s.local_address + ':' + str(s.local_port):<22}` left-aligns the combined host-port string within a 22-character column.

---

## 3. Step-by-Step Code Walkthrough

```python
@property
def is_backlog_saturated(self) -> bool:
    return self.state == "LISTEN" and self.recv_q >= self.send_q
```
- Identifies listening servers where pending connections exceed the kernel limit. When Postgres has `Recv-Q: 135` and `Send-Q: 128`, the queue is overflowing!

```python
def detect_stalled_senders(self, threshold_bytes: int = 50000) -> List[SocketEntry]:
    return [s for s in self.sockets if s.state == "ESTABLISHED" and s.send_q >= threshold_bytes]
```
- On established connections, `Send-Q` measures bytes sitting in the kernel send buffer waiting for acknowledgments. If this number is high, the remote receiver or network path is stalled!

---

## 4. How to Run the Script

```bash
cd code/day-33
python socket_telemetry_analyzer.py
```

### Expected Output
```
====================================================
DAY 33: LINUX SOCKET TELEMETRY AUDITOR (SS/INET_DIAG)
====================================================
State        | Local Socket           | Recv-Q   | Send-Q   | Process / Health
---------------------------------------------------------------------------
LISTEN       | 0.0.0.0:22             | 0        | 128      | sshd -> HEALTHY
LISTEN       | 127.0.0.1:5432         | 135      | 128      | postgres -> CRITICAL: Backlog Overflow! (Dropping SYNs)
ESTABLISHED  | 192.168.1.50:45120     | 0        | 65536    | backup_uploader -> WARNING: Stalled Send Buffer (65536 bytes)
---------------------------------------------------------------------------
[VERIFIED] Socket telemetry analyzer successfully diagnosed queue saturation!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`TypeError: __init__() got an unexpected keyword argument`**:
   - Occurs if dictionary keys do not match the dataclass field names. Ensure dictionary keys align exactly with `SocketEntry` attributes.
2. **Zero Division or Comparison Errors**:
   - Always ensure `send_q` is greater than 0 before calculating backlog percentage ratios `recv_q / send_q`.

---
### Additional Python Beginner Foundations
- **TCP Socket State Constants**:
  Instead of hardcoding raw numbers like `1` or `7`, Python scripts should define human-readable mappings: `TCP_ESTABLISHED = 1`, `TCP_CLOSE_WAIT = 7`. This drastically simplifies maintenance and prevents accidental logic bugs.
- **Parsing Columnar CLI Data**:
  When processing outputs from commands like `ss -tan` or `netstat`, string `.split()` without arguments splits on arbitrary contiguous whitespace, safely absorbing varied spacing between columns.

### Extended Debugging Guide
1. **Address-Port Splitting**: IPv6 addresses contain colons (e.g. `[::1]:8080`). Splitting strictly on `:` breaks IPv6. Use `.rsplit(':', 1)` to split only on the *last* colon separating the port.
2. **Resource Leaks**: Sockets stuck in `CLOSE_WAIT` indicate application bugs where the remote closed the stream but the local app forgot to call `socket.close()`.

## 6. Beginner Exercises & Challenges
1. **Add TIME-WAIT Counter**: Add a method `count_timewait_sockets()` to audit how many sockets are lingering in `TIME_WAIT` state.
2. **Calculate Backlog Percentage**: Enhance the output table to show percentage backlog utilization `(recv_q / send_q) * 100` for all listening sockets.
