# Hands-On Lab: Day 31 - Modern Network Interface Inspector (`network_interface_inspector.py`)

## 1. What Are We Building & Why Does It Matter?
In modern Linux systems engineering, troubleshooting network connectivity starts with inspecting network interfaces.
Legacy tools like `ifconfig` are deprecated because they hide link carrier status and cannot report modern Netlink socket states.
When an Ethernet cable is disconnected or a cloud virtual switch drops a link, the interface may still be administratively `UP`, but its physical state is `NO-CARRIER` (missing `LOWER_UP`).

In this lab, we build `network_interface_inspector.py` to parse structured Netlink interface telemetry (equivalent to `ip -j link` and `ip -j addr`), auditing MAC addresses, MTU sizing, and operational health.

---

## 2. Python Concepts for Beginners
1. **The `@property` Decorator**:
   - Allows a method to be accessed like an attribute without parentheses `iface.is_operational` instead of `iface.is_operational()`.
   - Useful for calculating boolean status on the fly.
2. **Dictionary `.get()` Method**:
   - `item.get("mtu", 1500)` looks up `"mtu"`. If the key is missing from the dictionary, it returns the safe fallback `1500` instead of crashing with a `KeyError`.
3. **The `@dataclass` Decorator**:
   - Automatically generates the constructor `__init__`, string representation, and equality methods.

---

## 3. Step-by-Step Code Walkthrough

```python
@property
def is_operational(self) -> bool:
    return "UP" in self.flags and "LOWER_UP" in self.flags
```
- In Linux, an interface has two distinct flags:
  - `UP`: The administrator enabled the device (`ip link set eth0 up`).
  - `LOWER_UP`: The physical hardware detected a link carrier signal.
  - An interface is only operational if BOTH flags are active!

```python
def audit_interfaces(self) -> Dict[str, str]:
    if not iface.is_operational:
        results[name] = f"WARNING: Link down or physical carrier missing! (Flags: {iface.flags})"
```
- The auditor iterates through all discovered interfaces and flags missing IPv4 addresses or disconnected cables.

---

## 4. How to Run the Script

```bash
cd code/day-31
python network_interface_inspector.py
```

### Expected Output
```
====================================================
DAY 31: LINUX NETWORK INTERFACE AUDITOR (IPROUTE2)
====================================================
Interface  | MAC Address        | Status Summary
-----------------------------------------------------------------
lo         | 00:00:00:00:00:00  | OK (Loopback)
eth0       | 52:54:00:12:34:56  | HEALTHY: Operational on 192.168.1.50/24 (MTU 1500)
eth1       | 52:54:00:98:76:54  | WARNING: Link down or physical carrier missing! (Flags: ['BROADCAST', 'MULTICAST', 'UP'])
-----------------------------------------------------------------
[VERIFIED] Netlink interface telemetry and link state logic validated!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`KeyError: 'operstate'`**:
   - Happens if you access `item["operstate"]` directly when the key is omitted. Use `item.get("operstate", "DOWN")`.
2. **`TypeError: 'bool' object is not callable`**:
   - If you write `iface.is_operational()` when it is decorated with `@property`, Python raises this error. Remove the parentheses!

---
### Additional Python Beginner Foundations
- **Why use `re.finditer` over `re.split`?**
  When parsing system outputs like `ip -d link show`, delimiters can be variable spaces, tabs, or newlines. Regex `finditer` gives you iterator objects yielding matches with their span positions, preventing huge temporary list allocations in memory.
- **Type Annotations for Readability**:
  Writing `def parse_interfaces(raw_text: str) -> List[InterfaceMetrics]:` communicates exact inputs and return types to anyone reading your code, acting as self-documenting executable documentation.

### Extended Debugging Guide
1. **Handling Empty Blocks**: If `/sys/class/net/` contains virtual interfaces without standard operational states, default unknown fields with safe fallbacks rather than crashing with `IndexError`.
2. **Permission Denied on Real Hardware**: While our script runs purely against mock data, on actual Linux systems reading certain device queues requires `CAP_NET_ADMIN` or root capabilities.

## 6. Beginner Exercises & Challenges
1. **Add Jumbo Frame Detection**: Extend the auditor to issue a warning if an Ethernet interface has `mtu == 9000` (Jumbo Frames) while its link peer has standard MTU 1500.
2. **Filter Promiscuous Mode**: Add a check that detects if `"PROMISC"` is present in `iface.flags` and alerts the administrator that packet sniffing is active.
