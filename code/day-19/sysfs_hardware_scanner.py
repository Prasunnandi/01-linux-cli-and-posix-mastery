#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sysfs_hardware_scanner.py - Linux Sysfs & PCI Device Inspector
Demonstrates parsing PCI vendor/device identifiers and sysfs topology.
"""

KNOWN_VENDORS = {
    "0x8086": "Intel Corporation",
    "0x10de": "NVIDIA Corporation",
    "0x1002": "Advanced Micro Devices, Inc. (AMD)",
    "0x144d": "Samsung Electronics Co Ltd"
}

def decode_pci_slot(pci_address: str) -> dict:
    parts = pci_address.split(':')
    domain = parts[0]
    bus = parts[1]
    dev_func = parts[2].split('.')
    device = dev_func[0]
    func = dev_func[1]
    return {
        "canonical_address": pci_address,
        "domain": domain,
        "bus": bus,
        "device": device,
        "function": func
    }

def identify_pci_device(vendor_id: str, device_id: str) -> str:
    vendor_name = KNOWN_VENDORS.get(vendor_id.lower(), "Unknown Vendor")
    return f"{vendor_name} [Device ID: {device_id}]"

if __name__ == "__main__":
    slot = "0000:03:00.0"
    v_id = "0x10de"
    d_id = "0x2484"
    
    decoded = decode_pci_slot(slot)
    identity = identify_pci_device(v_id, d_id)
    
    print("=== Linux PCI Device & Sysfs Analyzer ===")
    for k, v in decoded.items():
        print(f"  {k}: {v}")
    print(f"  hardware_identity: {identity}")
