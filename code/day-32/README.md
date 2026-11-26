# Hands-On Lab: Day 32 - Kernel Routing Longest Prefix Match (`routing_table_lpm.py`)

## 1. What Are We Building & Why Does It Matter?
When an operating system sends an IP packet, how does it know whether to send it to your local Wi-Fi router, through a corporate VPN tunnel, or straight to a local Ethernet card?
The Linux kernel uses the **Forwarding Information Base (FIB)** and evaluates routes using **Longest Prefix Matching (LPM)**.
If you have a default route (`0.0.0.0/0`), a VPN route (`10.0.0.0/8`), and a local subnet (`10.1.2.0/24`), a packet to `10.1.2.99` matches **all three routes**!
LPM mandates that the route with the most specific (longest) subnet mask (`/24`) wins.

In this lab, we build a pure Python implementation of the Linux kernel FIB routing engine using 32-bit bitmask arithmetic.

---

## 2. Python Concepts for Beginners
1. **Bitwise Left Shift (`<<`) and Bitwise OR (`|`)**:
   - `(octets[0] << 24) | (octets[1] << 16) ...` combines four 8-bit numbers (bytes) into a single 32-bit integer.
2. **Bitwise AND (`&`)**:
   - `(dst_int & route.mask_int) == route.net_int`:
   - Masking turns off all bits outside the subnet. If the remaining bits match the route's network address, the destination IP belongs to that network!
3. **Calculating Subnet Masks**:
   - `(0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF` dynamically generates a bitmask of `prefix_len` continuous 1-bits followed by zeros. For `/24`, this generates `255.255.255.0` (`0xFFFFFF00`).

---

## 3. Step-by-Step Code Walkthrough

```python
def lookup(self, dst_ip_str: str) -> Optional[RouteEntry]:
    dst_int = ip_to_int(dst_ip_str)
    best_match = None
    for route in self.routes:
        if (dst_int & route.mask_int) == route.net_int:
            if best_match is None or route.prefix_len > best_match.prefix_len:
                best_match = route
    return best_match
```
- The algorithm evaluates every route:
  - If the packet destination matches the route's subnet, it checks whether `prefix_len` is greater than the current best match.
  - `/32` beats `/24`, which beats `/8`, which beats `/0`.

---

## 4. How to Run the Script

```bash
cd code/day-32
python routing_table_lpm.py
```

### Expected Output
```
====================================================
DAY 32: KERNEL ROUTING LONGEST PREFIX MATCH (LPM)
====================================================
Destination IP   | Selected Route | Outgoing Dev | Gateway
-----------------------------------------------------------------
8.8.8.8          | 0.0.0.0/0      | eth0         | 192.168.1.1
10.5.0.1         | 10.0.0.0/8     | tun0         | 172.16.0.1
10.1.2.99        | 10.1.2.0/24    | eth1         | 10.1.2.1
10.1.2.45        | 10.1.2.45/32   | eth2         | DIRECT
-----------------------------------------------------------------
[VERIFIED] Linux FIB Longest Prefix Matching logic confirmed 100% accurate!
```

---

## 5. Common Python Errors & Troubleshooting
1. **Integer Overflow on Shifts**:
   - In Python, integers can grow infinitely large. Always mask with `& 0xFFFFFFFF` to ensure values remain within 32-bit unsigned bounds.
2. **`ValueError: invalid literal for int()`**:
   - If `ip_to_int` is passed an invalid string like `"192.168.1"`, `.split(".")` produces only 3 items, causing an unpack or index error.

---
### Additional Python Beginner Foundations
- **Bitwise Integer Masks in Networking**:
  In IPv4 routing, a subnet mask like `/24` corresponds to 24 leading ones (`0xFFFFFF00`). In Python, `(0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF` calculates this mask without needing string manipulation.
- **Sorting with Custom Keys**:
  Python's `.sort(key=lambda r: r.prefix_len, reverse=True)` uses Timsort ($O(N \log N)$), ensuring that the longest prefix is tested first during longest prefix matching (LPM).

### Extended Debugging Guide
1. **Default Route Metric Ties**: When two routes match `/0` (default gateway), routers use metric/cost as the tiebreaker. Ensure your routing table sorts first by prefix length descending, then by metric ascending.
2. **Handling Host Routes (`/32`)**: Single host routes have a prefix length of 32. Ensure bitshift logic handles `prefix_len == 32` without overflowing.

## 6. Beginner Exercises & Challenges
1. **Metric Tie-Breaking**: Add two routes with identical prefix length `/24` but different metrics (`metric=50` and `metric=100`). Verify that the route with the lower metric is chosen!
2. **Implement Route Deletion**: Add a `del_route(cidr)` method to `LinuxFIB` that removes an existing route from the routing table.
