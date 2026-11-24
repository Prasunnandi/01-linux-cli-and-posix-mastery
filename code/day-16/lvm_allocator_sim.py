#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lvm_allocator_sim.py - Logical Volume Management (LVM) Extent Simulator
Demonstrates Physical Extent (PE) to Logical Extent (LE) mapping and volume growth.
"""

class VolumeGroup:
    def __init__(self, name: str, pe_size_mb: int = 4):
        self.name = name
        self.pe_size_mb = pe_size_mb
        self.physical_volumes = {}
        self.logical_volumes = {}
        self.total_pe = 0
        self.allocated_pe = 0

    def add_pv(self, pv_name: str, size_gb: int):
        pe_count = (size_gb * 1024) // self.pe_size_mb
        self.physical_volumes[pv_name] = pe_count
        self.total_pe += pe_count
        print(f"[PV ADDED] {pv_name}: {size_gb} GB ({pe_count} PEs)")

    def create_lv(self, lv_name: str, size_gb: int):
        needed_pe = (size_gb * 1024) // self.pe_size_mb
        if self.allocated_pe + needed_pe > self.total_pe:
            raise ValueError(f"Insufficient free extents in VG {self.name}!")
        self.logical_volumes[lv_name] = needed_pe
        self.allocated_pe += needed_pe
        print(f"[LV CREATED] {lv_name}: {size_gb} GB ({needed_pe} LEs allocated)")

    def get_summary(self) -> dict:
        free_pe = self.total_pe - self.allocated_pe
        return {
            "vg_name": self.name,
            "pe_size_mb": self.pe_size_mb,
            "total_pe": self.total_pe,
            "allocated_pe": self.allocated_pe,
            "free_pe": free_pe,
            "total_gb": (self.total_pe * self.pe_size_mb) / 1024,
            "free_gb": (free_pe * self.pe_size_mb) / 1024
        }

if __name__ == "__main__":
    vg = VolumeGroup("vg_production", pe_size_mb=4)
    vg.add_pv("/dev/sda2", size_gb=500)
    vg.add_pv("/dev/sdb1", size_gb=1000)
    
    vg.create_lv("lv_root", size_gb=200)
    vg.create_lv("lv_database", size_gb=800)
    
    summary = vg.get_summary()
    print("\n=== LVM Volume Group Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
