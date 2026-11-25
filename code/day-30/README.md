# Hands-On Lab: Day 30 - Milestone 1: System Health Audit CLI (`system_health_audit_cli.py`)

## 1. What Are We Building & Why Does It Matter?
This milestone synthesizes the first 29 days of Linux systems programming into an enterprise diagnostics CLI.
In production cloud environments (Kubernetes, AWS EC2, bare-metal servers), an automated health auditor must monitor:
1. **CPU Load vs Physical Core Count** (detecting queue stagnation).
2. **Virtual Memory Available Percentage** (detecting OOM killer risk).
3. **Disk Block and Inode Utilization** (detecting full filesystems and inode starvation).

In this lab, we build `system_health_audit_cli.py`, a complete modular CLI tool that outputs both human-readable reports and machine-readable JSON with standardized exit codes (`0` for Healthy, `1` for Warning, `2` for Critical).

---

## 2. Python Concepts for Beginners
1. **Multi-Subsystem Health Aggregation**:
   - Evaluates three separate domains and computes an overall health score.
2. **Formatted Text Reporting**:
   - Uses multi-line string lists and `"
".join(lines)` to generate clean console output.
3. **Structured Machine Output (`json.dumps()`)**:
   - Converts Python dictionaries into standardized JSON for integration with Datadog, Prometheus, or CI/CD pipelines.

---

## 3. Step-by-Step Code Walkthrough

```python
def analyze_system_metrics(...):
    # Evaluates CPU
    if load_1m > (cpu_cores * 2.0):
        cpu_status = "CRITICAL"
        overall_status = 2
    # Evaluates Memory
    if mem_avail_pct < 5:
        mem_status = "CRITICAL"
        overall_status = 2
    # Evaluates Inodes
    if disk_used_pct >= 90 or inode_used_pct >= 90:
        storage_status = "CRITICAL"
        overall_status = 2
```
- If any single subsystem enters a critical state, `overall_status` is elevated to `2`, guaranteeing that monitoring alerts fire immediately.

---

## 4. How to Run the Script

```bash
cd code/day-30
python system_health_audit_cli.py
```

### Expected Output
```
====================================================
       ENTERPRISE SYSTEM HEALTH AUDIT REPORT        
====================================================
CPU Status    : [OK] (1m Load: 3.50 across 8 cores)
Memory Status : [OK] (56% Available: 18432 MB free)
Storage Status: [OK] (Disk: 45%, Inodes: 30%)
----------------------------------------------------
OVERALL HEALTH: HEALTHY (Exit Code: 0)
====================================================

[Simulating Inode Exhaustion Incident]
====================================================
       ENTERPRISE SYSTEM HEALTH AUDIT REPORT        
====================================================
CPU Status    : [OK] (1m Load: 4.00 across 8 cores)
Memory Status : [OK] (50% Available: 16384 MB free)
Storage Status: [CRITICAL] (Disk: 40%, Inodes: 95%)
----------------------------------------------------
OVERALL HEALTH: CRITICAL (Exit Code: 2)

Active Diagnostic Alerts:
  [!] Root filesystem space or inodes >= 90% full!
====================================================

[MILESTONE 1 VERIFIED] Enterprise Health Audit Engine fully operational!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`FileNotFoundError: [Errno 2] No such file or directory: '/proc/stat'`**:
   - Linux pseudo-filesystems like `/proc` and `/sys` do not exist natively on Windows or macOS. Our simulator mocks these files so the audit CLI runs cross-platform without platform-dependent crashes.
2. **Permission Denied (`PermissionError`)**:
   - In real Linux production environments, inspecting certain kernel knobs or other users' `/proc/[pid]/io` requires root privileges (`sudo`). Your script should gracefully catch permission errors and mark entries as `[ACCESS DENIED]`.
3. **Division by Zero in Percentage Calculations**:
   - When calculating memory or disk utilization `(used / total) * 100`, if `total` is `0`, Python raises `ZeroDivisionError`. Always guard with `if total > 0:`.

---

## 6. Beginner Exercises & Challenges
1. **Add Network Socket Audit**:
   - Extend `system_health_audit_cli.py` to parse simulated `/proc/net/tcp` entries and report listening ports and ESTABLISHED connection counts.
2. **Zombie Process Detection**:
   - Add a rule that checks for processes in state `'Z'` (Zombie) and flags parent processes that fail to reap child exit statuses via `waitpid()`.
3. **JSON and Markdown Report Exporters**:
   - Add a `--format=json` and `--format=markdown` CLI flag that serializes the full system health report into a machine-readable JSON object or a formatted audit report file.
