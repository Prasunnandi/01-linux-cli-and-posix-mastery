# Day 19: Hardware Probing & Bus Topology (lspci, lsusb)

## 1. Architectural Foundations: The Linux Device Model & Sysfs

The Linux kernel maintains a unified object-oriented view of all physical buses, hardware controllers, and peripheral devices known as the **Unified Device Model**. This hierarchy is exposed dynamically to user space through the pseudo-filesystem mounted at **`/sys` (sysfs)**.

```
/sys/
+-- bus/              (Hardware buses: pci, usb, i2c, scsi)
|   +-- pci/devices/  (Symlinks to all discovered PCI devices)
|   +-- usb/devices/  (Symlinks to all discovered USB devices)
+-- class/            (Functional categories: net, block, drm, tty)
|   +-- net/          (Network interfaces: eth0, wlan0)
|   +-- block/        (Block storage devices: sda, nvme0n1)
+-- devices/          (The true physical device tree matching hardware topology)
```

---

## 2. The PCI & PCIe Bus Architecture (`lspci`)

Every device plugged into a PCI or PCI Express slot is addressed by a canonical four-part identifier:
$$\text{Domain : Bus : Device . Function } (\text{DDDD:BB:DD.F})$$

Example: `0000:03:00.0`
- `0000`: PCI Domain (typically 0 on single-socket machines).
- `03`: PCI Bus Number (assigned during system firmware bus enumeration).
- `00`: Physical Device slot number on that bus.
- `0`: Function number inside multi-function silicon (e.g. Function 0 = GPU, Function 1 = HDMI Audio).

### 2.1 The PCI Configuration Space
Every PCI device provides a mandatory **256-byte Configuration Space** (expanded to $4096\text{ bytes}$ on PCIe). The kernel reads the first 16 bytes at boot to identify the hardware:
- **Vendor ID (VID)**: 16-bit identifier assigned by PCI-SIG (e.g. `0x10DE` = NVIDIA, `0x8086` = Intel).
- **Device ID (DID)**: 16-bit identifier defined by the vendor.
- **Base Address Registers (BARs)**: Memory addresses assigned by the kernel to map device registers into CPU physical address space (**MMIO - Memory-Mapped I/O**).

```bash
# View human-readable PCI hierarchy with kernel drivers:
$ lspci -tv
-[0000:00]-+-00.0  Intel Corporation 8th Gen Core Processor Host Bridge
           +-01.0-[01]----00.0  NVIDIA Corporation GA104 [GeForce RTX 3070]
           +-17.0  Intel Corporation Cannon Lake SATA AHCI Controller
           \-1d.0-[02-04]----00.0  Samsung Electronics NVMe SSD Controller

# Inspect raw hexadecimal VID/DID and active kernel driver:
$ lspci -s 01:00.0 -vnn
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA104 [10de:2484] (rev a1)
        Subsystem: EVGA Device [3842:3755]
        Kernel driver in use: nouveau
        Kernel modules: nouveau, nvidia_drm
```

---

## 3. The USB Subsystem (`lsusb`) & Dynamic Uevents

USB is an asymmetrical, polled, tree-structured bus managed by a **Host Controller** (xHCI).
Devices present a strict descriptor hierarchy:
`Device Descriptor -> Configuration Descriptor -> Interface Descriptor -> Endpoint Descriptors`

### 3.1 Kernel Hotplugging: Netlink Sockets & `udev`
When a USB device or PCIe card is inserted:
1. The hardware host controller generates an electrical interrupt (IRQ).
2. The kernel detects the insertion, reads device descriptors, and instantiates a new `struct device`.
3. The kernel emits a **`UEVENT` broadcast packet** over an asynchronous `NETLINK_KOBJECT_UEVENT` socket.
4. The user-space daemon **`udevd`** receives the netlink message, evaluates declarative rules in `/etc/udev/rules.d/`, and creates the appropriate device node in `/dev` (e.g. `/dev/ttyUSB0` or `/dev/sdb`) with configured user permissions.
