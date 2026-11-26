# Hands-On Lab: Day 34 - Glibc Stub Resolver & `ndots` Simulator (`dns_stub_resolver_sim.py`)

## 1. What Are We Building & Why Does It Matter?
In Linux, when you call `curl api.stripe.com`, your operating system does not query the internet directly.
It invokes Glibc's **Stub Resolver**, which reads `/etc/resolv.conf`.
In modern container environments (like Kubernetes), `/etc/resolv.conf` is configured with `options ndots:5` and several search domains (`default.svc.cluster.local`, `svc.cluster.local`).
Because `api.stripe.com` only has 2 dots (which is less than 5), Glibc mistakenly assumes it is an internal hostname and generates **3 or 4 wasted DNS queries** across your search domains before finally querying `api.stripe.com`!

In this lab, we build `dns_stub_resolver_sim.py` to simulate Glibc's exact resolution algorithm and prove how adding a trailing dot (`api.stripe.com.`) eliminates wasted queries.

---

## 2. Python Concepts for Beginners
1. **String Manipulation (`.count()` and `.endswith()`)**:
   - `hostname.count(".")` counts the number of dots in the string.
   - `hostname.endswith(".")` detects whether the domain name is fully qualified (FQDN).
2. **List Mutation and Slicing**:
   - `queries_attempted.append(expanded)` records every single query issued for auditability.
3. **Tuples as Function Return Values**:
   - `return ip, queries_attempted` returns a 2-element tuple unpacked with `ip, attempts = sim.resolve(...)`.

---

## 3. Step-by-Step Code Walkthrough

```python
if num_dots >= self.config.ndots:
    queries_attempted.append(hostname)
    if hostname in self.dns_db:
        return self.dns_db[hostname], queries_attempted
```
- If the domain has at least `ndots` dots, it tries the domain name directly first.
- If it has fewer than `ndots` dots, it iterates through `search_domains`, appending each one sequentially.
- Appending a trailing dot `api.stripe.com.` bypasses search domains completely, executing in 1 query instead of 4!

---

## 4. How to Run the Script

```bash
cd code/day-34
python dns_stub_resolver_sim.py
```

### Expected Output
```
====================================================
DAY 34: GLIBC STUB RESOLVER & NDOTS SIMULATOR
====================================================
Resolving 'db01':
  Queries issued : ['db01.default.svc.cluster.local', 'db01.svc.cluster.local', 'db01.prod.internal']
  Resulting IP   : 10.0.1.50

Resolving 'api.stripe.com' under ndots:5 (Kubernetes Latency Trap):
  Queries issued : ['api.stripe.com.default.svc.cluster.local', 'api.stripe.com.svc.cluster.local', 'api.stripe.com.prod.internal', 'api.stripe.com']
  Total queries  : 4 (3 wasted search attempts!)
  Resulting IP   : 198.51.100.99

Resolving 'api.stripe.com.' (Trailing dot FQDN optimization):
  Queries issued : ['api.stripe.com']
  Total queries  : 1 (Direct lookup!)
  Resulting IP   : 198.51.100.99
-------------------------------------------------------
[VERIFIED] Glibc stub resolver ndots and search domain mechanics verified!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`AttributeError: 'NoneType' object has no attribute 'rstrip'`**:
   - Ensure the input `hostname` is a valid string, not `None`.
2. **Trailing Dot Discrepancies**:
   - Forgetting to strip the trailing dot before looking up in `self.dns_db` causes a key mismatch if dictionary keys don't include dots.

---
### Additional Python Beginner Foundations
- **Parsing Configuration Files Line-by-Line**:
  When reading `/etc/resolv.conf`, always strip leading whitespace and ignore comment lines starting with `#` or `;`. Using `line.strip().startswith(('#', ';'))` cleanly avoids false positive parsing.
- **Round-Robin Iterator with `itertools.cycle`**:
  To rotate through a list of DNS nameservers like production stub resolvers do, use `itertools.cycle(nameservers)`. Calling `next()` smoothly rotates through targets.

### Extended Debugging Guide
1. **Handling DNS Search Domains**: When a user queries `myservice`, a stub resolver tries `myservice.production.internal` before querying the root domain.
2. **Timeout and Retry Cascades**: If nameserver 1 does not answer within 2 seconds, the stub resolver must back off and try nameserver 2 rather than hanging indefinitely.

## 6. Beginner Exercises & Challenges
1. **Simulate Nameserver Timeout**: Modify the simulator to support multiple nameservers. If nameserver 0 fails to answer within `timeout=2` seconds, simulate failover to nameserver 1.
2. **Implement Round-Robin (`rotate`)**: Add support for `options rotate`, shuffling nameservers on each query.
