# -*- coding: utf-8 -*-
"""
Day 6 Lab: High-Performance Log Wrangling Engine
Demonstrates columnar text extraction and running aggregations matching awk/sed functionality.
"""
import sys

SAMPLE_ACCESS_LOG = """192.168.1.10 - - [23/Nov/2026:08:00:01] "GET /index.html HTTP/1.1" 200 4520 12
192.168.1.15 - - [23/Nov/2026:08:00:05] "POST /api/login HTTP/1.1" 401 512 85
192.168.1.10 - - [23/Nov/2026:08:00:12] "GET /images/logo.png HTTP/1.1" 200 18450 5
10.0.50.2 - - [23/Nov/2026:08:01:00] "GET /video/intro.mp4 HTTP/1.1" 200 10485760 120
192.168.1.20 - - [23/Nov/2026:08:01:22] "GET /about.html HTTP/1.1" 404 1200 8
10.0.50.2 - - [23/Nov/2026:08:02:15] "GET /video/demo.mp4 HTTP/1.1" 200 20971520 240
192.168.1.10 - - [23/Nov/2026:08:03:00] "GET /api/user HTTP/1.1" 200 840 45
"""

def simulate_awk_aggregation(logs):
    print("==================================================")
    print("   DAY 6 LAB: AWK / SED LOG WRANGLING SIMULATION  ")
    print("==================================================")
    print("Simulating AWK command:")
    print("  awk '$9 == 200 { bytes += $10; reqs++ } END { ... }'\n")

    lines = logs.strip().split("\n")
    total_bytes = 0
    success_requests = 0
    mp4_bytes = 0

    print(f"{'IP Address':<15} {'Status':<8} {'Bytes Sent':<12} {'URL'}")
    print("-" * 55)

    for line in lines:
        parts = line.split()
        if len(parts) < 11:
            continue

        ip = parts[0]
        status = int(parts[8])
        bytes_sent = int(parts[9])
        url = parts[6]

        if status == 200:
            success_requests += 1
            total_bytes += bytes_sent
            if url.endswith(".mp4"):
                mp4_bytes += bytes_sent

        print(f"{ip:<15} {status:<8} {bytes_sent:<12} {url}")

    print("\n--- AWK END { ... } SUMMARY REPORT ---")
    print(f"Total Successful 200 Requests : {success_requests}")
    print(f"Total HTTP Bandwidth          : {total_bytes / 1024:.2f} KB ({total_bytes} bytes)")
    print(f"Video (MP4) Bandwidth         : {mp4_bytes / (1024*1024):.2f} MB")
    print("==================================================")

if __name__ == "__main__":
    simulate_awk_aggregation(SAMPLE_ACCESS_LOG)
