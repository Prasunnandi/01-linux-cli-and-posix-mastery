# Day 57: Netfilter iptables Chain Evaluator & Conntrack Lab Tutorial

Welcome to Day 57 of Linux CLI and POSIX Mastery. Today, you will build a Python implementation of the Linux Netfilter packet filtering subsystem, modeling linear rule chains (`INPUT`, `FORWARD`, `OUTPUT`) and stateful connection tracking (`conntrack`).

---

## 1. What Are We Building & Why Does It Matter?

Linux firewalls execute inside kernel space via the Netfilter framework. When an incoming network packet arrives, the kernel evaluates it against ordered chains of rules.

Key architectural concepts:
- **Linear Rule Traversal**: Rules are evaluated one-by-one from top to bottom. The first matching rule decides the packet's fate (`ACCEPT`, `DROP`, `REJECT`).
- **Connection Tracking (`conntrack`)**: Maintains an in-memory hash table of active 5-tuple network flows. It categorizes packets as `NEW`, `ESTABLISHED`, `RELATED`, or `INVALID`.
- **Default Chain Policy**: If no rule in the chain matches the packet, the fallback default policy (typically `DROP`) is applied.

In this lab, you simulate this exact kernel pipeline in pure Python.

---

## 2. Python Concepts for Beginners

### A. Normalized Tuple Hashing for Bidirectional Flows
In a bidirectional TCP connection, packets flow in two directions: Client $\to$ Server and Server $\to$ Client. To track both directions in a single connection table, normalize the key:
```python
forward = (src_ip, dst_ip, src_port, dst_port, protocol)
reverse = (dst_ip, src_ip, dst_port, src_port, protocol)
canonical_key = min(forward, reverse)
```

### B. Python Enums for Filter Actions
Use `enum.Enum` to define symbolic firewall verdicts:
```python
import enum

class RuleTarget(enum.Enum):
    ACCEPT = "ACCEPT"
    DROP = "DROP"
    REJECT = "REJECT"
```

### C. Optional Filter Criteria
Use `Optional[T]` dataclass fields so rules only match attributes that are explicitly specified:
```python
if rule.dport and rule.dport != packet.dst_port:
    continue  # Port did not match
```

---

## 3. Step-by-Step Code Walkthrough

1. **`Packet5Tuple` & `FilterRule` Dataclasses**: Encapsulates network packet metadata and firewall rule filters.
2. **`ConntrackTable`**:
   - `_normalize_key()`: Ensures forward and reverse packets resolve to the identical table entry.
   - `process_packet()`: Checks existing connections. Transitions `NEW` flows to `ESTABLISHED`. Drops packets if `max_entries` is exceeded.
3. **`IPTablesEngine`**:
   - `append_rule()`: Inserts rules into chains (`INPUT`, `FORWARD`, `OUTPUT`).
   - `evaluate_chain()`:
     1. Passes packet to `conntrack`.
     2. Sequentially evaluates rules until the first match.
     3. Applies default policy if no rule matched.
4. **`main()` Test Suite**: Validates stateful `NEW` acceptance, `ESTABLISHED` reply tracking, default drop on unauthorized ports, and conntrack table saturation.

---

## 4. How to Run & Expected Output

Run the script from your terminal using Python 3:
```bash
python code/day-57/iptables_chain_evaluator_and_conntrack.py
```

Expected output:
```text
=== Day 57: Netfilter iptables Chain Evaluator & Conntrack Engine ===
[*] Test 1 Passed: Inbound SSH SYN accepted: Matched rule #2 (Target: ACCEPT)
[*] Test 2 Passed: Inbound SSH ACK recognized as ESTABLISHED: Matched rule #1 (Target: ACCEPT)
[*] Test 3 Passed: Unauthorized MySQL port dropped by default policy: Default chain policy (DROP)
[*] Test 4 Passed: Conntrack table saturation successfully detected and dropped: Conntrack table full; packet dropped
All Netfilter iptables & Conntrack Engine assertions passed successfully!
```

---

## 5. Common Python Errors & Troubleshooting

- **State Desynchronization**: Ensure both forward (`src -> dst`) and reverse (`dst -> src`) packet tuples map to the identical conntrack key.
- **Rule Ordering Pitfalls**: Fast-path rules (such as accepting `ESTABLISHED` traffic) must always be inserted at the top of the chain to minimize CPU overhead.

---

## 6. Beginner Exercises & Challenges

1. **Implement CIDR Subnet Matches**: Extend `src_ip` and `dst_ip` in `FilterRule` to match CIDR subnets (e.g. `10.0.0.0/8`).
2. **Add Port Range Support**: Allow rules to specify port ranges (e.g. `1024-65535`) rather than single port integers.
3. **Implement Rule Hit Counters**: Add `packets_matched` and `bytes_matched` integers to `FilterRule` to emulate `iptables -L -v` traffic statistics.
