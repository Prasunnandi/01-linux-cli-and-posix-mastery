# Day 41: Init System Dependency DAG & Concurrency Dispatcher

## 1. What Are We Building & Why Does It Matter?
In traditional UNIX System V Init (`/etc/init.d/`), services started sequentially one by one using shell scripts. If you had 40 services and each took 1.5 seconds, the server required a full minute to boot.
`systemd` solved this by modeling services as a **Directed Acyclic Graph (DAG)**. Services that do not depend on each other are executed in parallel waves.
In this lab, we build a **Dependency Graph Engine** in pure Python that:
1. Validates unit relationships (`Requires=` vs `After=`).
2. Detects circular dependency deadlocks via depth-first search (DFS).
3. Dispatches independent units concurrently in topological waves.

---

## 2. Python Concepts for Beginners

### A. Python Sets for Fast Lookups
A `set` stores unique elements without duplicates and provides $O(1)$ constant-time membership checking:
```python
dependencies = {"network.target", "dbus.service"}
if "network.target" in dependencies:
    print("Dependency present!")
```

### B. Python `dataclasses`
We use `@dataclass` to cleanly define nodes without writing repetitive `__init__` code:
```python
from dataclasses import dataclass, field
from typing import Set

@dataclass
class UnitNode:
    name: str
    requires: Set[str] = field(default_factory=set)
    after: Set[str] = field(default_factory=set)
```

### C. In-Degree Tracking in Graph Algorithms
The "in-degree" of a node is the number of prerequisites that must complete before it can start. When a node's in-degree drops to 0, it is immediately ready to run!

---

## 3. Step-by-Step Code Walkthrough

1. **`UnitNode`**: Holds service metadata, requirement sets, ordering constraints, and active status.
2. **`detect_cycles()`**: Uses a recursion stack in a Depth-First Search (DFS) to detect circular ordering edges like `A -> B -> A`.
3. **`compute_dispatch_waves()`**: Implements Kahn's topological sort algorithm to group services into concurrent execution waves.
4. **`main()` Function**: Bootstraps standard Linux units (`syslog.socket`, `dbus.service`, `network.target`, `nginx.service`), verifies that no cycles exist, and dispatches them in waves.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-41/init_system_dependency_graph.py
```

Expected output:
```text
====================================================
DAY 41: INIT SYSTEM DEPENDENCY DAG & CONCURRENCY
====================================================
1. Inspecting Unit Dependency Graph for Cycles...
   [PASS] Zero dependency cycles detected in DAG.

2. Computing Parallel Dispatch Waves:
   Wave 1 (Concurrent): ['dbus.socket', 'syslog.socket']
   Wave 2 (Concurrent): ['dbus.service', 'syslog.service']
   Wave 3 (Concurrent): ['network.target']
   Wave 4 (Concurrent): ['nginx.service', 'sshd.service']

[VERIFIED] Topological concurrency dispatcher completed with 100% fidelity!
```

---

## 5. Common Python Errors & Troubleshooting

- **`RuntimeError: Ordering cycles detected`**: Occurs if Unit A specifies `After=B` and Unit B specifies `After=A`. The engine detects this and halts safely.
- **KeyError in Graphs**: When looking up dependencies in dictionaries, always check `if dep in self.units:` before accessing to avoid crashes on external unmanaged services.

---

## 6. Beginner Exercises & Challenges

1. **Simulate a Cycle**: Add two units with mutual `After=` dependencies and observe how `detect_cycles()` catches and prints the cycle path.
2. **Execution Timing**: Add a `start_duration_sec` attribute to each unit and calculate the total elapsed wallclock time when running waves concurrently versus sequentially.
3. **Wants= Support**: Add weak dependencies (`Wants=`) where failure of a dependency does not prevent the unit from being scheduled.
