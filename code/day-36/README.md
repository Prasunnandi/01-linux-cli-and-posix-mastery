# Hands-On Lab: Day 36 - Bidirectional Stream Relay Simulator (`stream_relay_socat.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux systems engineering, **`socat`** is the ultimate stream plumber.
While standard Unix pipes (`|`) are unidirectional and confined to a single process tree, `socat` bridges two arbitrary endpoints full-duplex (bidirectionally):
- Exposing a local UNIX domain socket (e.g. `/var/run/docker.sock`) over an encrypted TCP port.
- Forwarding serial TTY devices over network sockets.
- Intercepting and debugging API communication between microservices.

In this lab, we build `stream_relay_socat.py`, a pure Python stream relay simulator modeling the non-blocking event loop of `socat`.

---

## 2. Python Concepts for Beginners
1. **The `dataclass(field(default_factory=...))` Pattern**:
   - In Python dataclasses, mutable default arguments (like `bytearray()`) cannot be assigned directly (`x: bytearray = bytearray()`).
   - Using `field(default_factory=bytearray)` ensures each instance receives its own fresh memory buffer.
2. **Byte Arrays and Memory Slicing**:
   - `del self.inbound_queue[:max_bytes]` deletes the drained slice from memory in place without reallocating the array.
3. **Simulating Full-Duplex I/O**:
   - In full-duplex networking, Endpoint A can transmit to Endpoint B at the exact same instant that Endpoint B transmits to Endpoint A.

---

## 3. Step-by-Step Code Walkthrough

```python
def step_relay(self) -> int:
    # Left -> Right
    left_data = self.left.read_available()
    if left_data:
        self.right.write(left_data)
    # Right -> Left
    right_data = self.right.read_available()
    if right_data:
        self.left.write(right_data)
```
- In each tick of the event loop, the relay checks both endpoints:
  - Any data waiting on the left socket is immediately forwarded to the right.
  - Any data waiting on the right socket is immediately forwarded to the left.

---

## 4. How to Run the Script

```bash
cd code/day-36
python stream_relay_socat.py
```

### Expected Output
```
====================================================
DAY 36: BIDIRECTIONAL STREAM RELAY (MINI-SOCAT)
====================================================
Relay bridged: /var/run/docker.sock <===> 127.0.0.1:2375

1. TCP Client writes 56 bytes to 127.0.0.1:2375
2. Socat relay moved 56 bytes to /var/run/docker.sock
3. Docker daemon writes 55 bytes to /var/run/docker.sock
4. Socat relay moved 55 bytes back to 127.0.0.1:2375
-------------------------------------------------------
Total Traffic Relayed : 111 bytes
[VERIFIED] Full-duplex stream relay operational at 100% fidelity!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`TypeError: cannot concatenate 'str' and 'bytes'`**:
   - Python strings are text; socket buffers store raw bytes (`b"..."`). Always prefix string literals with `b` or use `.encode('utf-8')`.
2. **Buffer Starvation / Blocking Deadlock**:
   - If a relay tries to read from a socket that has no data using blocking calls, the entire event loop freezes. Non-blocking reads (`read_available()`) prevent starvation.

---
### Additional Python Beginner Foundations
- **Full-Duplex vs Half-Duplex Streams**:
  A full-duplex stream allows both endpoints to send and receive simultaneously. In software simulations, this requires maintaining separate `incoming_buffer` and `outgoing_buffer` queues to avoid echo feedback loops.
- **Non-Blocking Poll Loops**:
  In real production relays, `select.select()` or `selectors.DefaultSelector` monitors file descriptors for readability and writability without blocking the CPU.

### Extended Debugging Guide
1. **Buffer Bloat & Flow Control**: If the receiving endpoint consumes data slower than the sending endpoint produces it, buffers grow indefinitely. Real relays enforce high-water mark pauses.
2. **Graceful Teardown**: When one end sends EOF (FIN packet), the relay must flush remaining bytes in the opposite direction before shutting down the destination socket.

## 6. Beginner Exercises & Challenges
1. **Add Traffic Counter**: Extend `SocatRelayEngine` to track separate metrics: `bytes_left_to_right` and `bytes_right_to_left`.
2. **Simulate Connection Drop**: Add a method `close()` to `MockStreamEndpoint`. Verify that when one endpoint closes, the relay cleanly shuts down the other side.
