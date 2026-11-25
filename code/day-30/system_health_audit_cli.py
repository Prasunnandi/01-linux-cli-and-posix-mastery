#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system_health_audit_cli.py - Enterprise Linux System Health Audit CLI
Milestone 1 Core Tool: Synthesizes CPU load, memory pressure, storage
capacity, and inode allocation into a production diagnostics reporting engine.
"""
import sys
import json

def analyze_system_metrics(cpu_cores: int, load_1m: float,
                           mem_total_kb: int, mem_avail_kb: int,
                           disk_used_pct: int, inode_used_pct: int) -> dict:
    overall_status = 0 # 0=Healthy, 1=Warning, 2=Critical
    alerts = []

    # 1. CPU Load Analysis
    cpu_status = "OK"
    if load_1m > (cpu_cores * 2.0):
        cpu_status = "CRITICAL"
        overall_status = 2
        alerts.append("CPU Load is critical (> 2x total cores)!")
    elif load_1m > cpu_cores:
        cpu_status = "WARNING"
        if overall_status < 1: overall_status = 1
        alerts.append("CPU Load exceeds core count.")

    # 2. Memory Available Analysis
    mem_avail_pct = int((mem_avail_kb / mem_total_kb) * 100)
    mem_status = "OK"
    if mem_avail_pct < 5:
        mem_status = "CRITICAL"
        overall_status = 2
        alerts.append("Available RAM is critically low (< 5%)! OOM imminent.")
    elif mem_avail_pct < 15:
        mem_status = "WARNING"
        if overall_status < 1: overall_status = 1
        alerts.append("Available RAM is low (< 15%).")

    # 3. Storage & Inode Analysis
    storage_status = "OK"
    if disk_used_pct >= 90 or inode_used_pct >= 90:
        storage_status = "CRITICAL"
        overall_status = 2
        alerts.append("Root filesystem space or inodes >= 90% full!")
    elif disk_used_pct >= 80 or inode_used_pct >= 80:
        storage_status = "WARNING"
        if overall_status < 1: overall_status = 1
        alerts.append("Root filesystem usage >= 80%.")

    return {
        "status_code": overall_status,
        "status_label": "HEALTHY" if overall_status == 0 else ("WARNING" if overall_status == 1 else "CRITICAL"),
        "cpu": {"cores": cpu_cores, "load_1m": load_1m, "status": cpu_status},
        "memory": {"total_mb": mem_total_kb // 1024, "avail_mb": mem_avail_kb // 1024, "avail_pct": mem_avail_pct, "status": mem_status},
        "storage": {"disk_used_pct": disk_used_pct, "inode_used_pct": inode_used_pct, "status": storage_status},
        "alerts": alerts
    }

def format_text_report(report: dict) -> str:
    lines = [
        "====================================================",
        "       ENTERPRISE SYSTEM HEALTH AUDIT REPORT        ",
        "====================================================",
        f"CPU Status    : [{report['cpu']['status']}] (1m Load: {report['cpu']['load_1m']:.2f} across {report['cpu']['cores']} cores)",
        f"Memory Status : [{report['memory']['status']}] ({report['memory']['avail_pct']}% Available: {report['memory']['avail_mb']} MB free)",
        f"Storage Status: [{report['storage']['status']}] (Disk: {report['storage']['disk_used_pct']}%, Inodes: {report['storage']['inode_used_pct']}%)",
        "----------------------------------------------------",
        f"OVERALL HEALTH: {report['status_label']} (Exit Code: {report['status_code']})"
    ]
    if report["alerts"]:
        lines.append("\nActive Diagnostic Alerts:")
        for a in report["alerts"]:
            lines.append(f"  [!] {a}")
    lines.append("====================================================")
    return "\n".join(lines)

if __name__ == "__main__":
    # Test Scenario: Production web server under normal healthy load
    healthy_data = analyze_system_metrics(
        cpu_cores=8, load_1m=3.5,
        mem_total_kb=32 * 1024 * 1024, mem_avail_kb=18 * 1024 * 1024,
        disk_used_pct=45, inode_used_pct=30
    )
    print(format_text_report(healthy_data))
    assert healthy_data["status_code"] == 0

    # Test Scenario: Degraded node with inode exhaustion
    print("\n[Simulating Inode Exhaustion Incident]")
    degraded_data = analyze_system_metrics(
        cpu_cores=8, load_1m=4.0,
        mem_total_kb=32 * 1024 * 1024, mem_avail_kb=16 * 1024 * 1024,
        disk_used_pct=40, inode_used_pct=95 # Inodes full!
    )
    print(format_text_report(degraded_data))
    assert degraded_data["status_code"] == 2
    print("\n[MILESTONE 1 VERIFIED] Enterprise Health Audit Engine fully operational!")
