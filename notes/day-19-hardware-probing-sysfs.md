# Day 19: Hardware Probing & Bus Topology (lspci, lsusb, sysfs)

## 1. Architectural Foundations: The Linux Device Model
Modern operating systems must dynamically discover, configure, power-manage, and handle hotplugging of arbitrary peripheral hardware. The Linux kernel accomplishes this through the **Unified Device Model** rooted in the `/sys` filesystem (**sysfs**).

```
+----------------------------------------------------------------------------+
|                               /sys (sysfs)                                 |
+----------------------------------------------------------------------------+
       |                         |                          |
       v                         v                          v
  /sys/bus/                  /sys/class/                /sys/devices/
  (Buses: pci, usb, i2c)     (Functional: net, block)   (Physical Hardware Tree)
       |                         |                          ^
       +-------------------------+--------------------------+
       (Symbolic links establish relationships to physical bus paths)
```

### Core Kernel Objects
- **`struct kobject`**: The fundamental object glue. Provides reference counting (`kref`), sysfs directory representation, and parent-child hierarchy.
- **`struct bus_type`**: Represents a physical or virtual communication bus (e.g., `pci_bus_type`, `usb_bus_type`). Matches drivers against devices via `match()` callbacks.
- **`struct device`**: Represents a physical instance of hardware connected to a bus.
- **`struct device_driver`**: Represents software that can control a `struct device`.

---

## 2. The PCI Bus Hierarchy & DBDF Notation
Peripheral Component Interconnect Express (PCIe) devices are addressed using the **Domain:Bus:Device.Function (DBDF)** format:
$$\text{0000:03:00.0} \implies \text{Domain 0000}, \text{Bus 03}, \text{Device 00}, \text{Function 0}$$

### PCI Configuration Space (256 - 4096 Bytes)
Every PCIe function exposes a hardware configuration register space mapped into memory:
- **Vendor ID (16 bits)**: Assigned by PCI-SIG (e.g., `0x8086` for Intel, `0x10DE` for NVIDIA).
- **Device ID (16 bits)**: Model identifier assigned by vendor.
- **Class Code (24 bits)**: Specifies function type (e.g., `0x010802` = Non-Volatile Memory controller / NVMe; `0x020000` = Ethernet controller).
- **Base Address Registers (BAR0 - BAR5)**: Memory or I/O ranges assigned by firmware/kernel for MMIO communication.

---

## 3. Kernel Hotplug & The Netlink uevent Socket
When hardware is plugged into a physical port:
1. Host controller hardware generates an interrupt (IRQ).
2. The kernel bus driver enumerates the device and allocates a `struct device`.
3. The kernel broadcasts a **uevent** string over an `AF_NETLINK` broadcast socket to userspace.
4. The userspace daemon `systemd-udevd` reads the netlink message, applies rules from `/etc/udev/rules.d/`, creates device nodes in `/dev/`, and loads matching kernel modules via `modprobe`.

---

## 4. Production Masterclass: Compilable C Real-Time uevent Hotplug Monitor

Save as `uevent_monitor.c` and compile with `gcc -Wall -Wextra -O2 uevent_monitor.c -o uevent_monitor`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <linux/netlink.h>

#define UEVENT_BUFFER_SIZE 4096

int main(void) {
    printf("====================================================\\n");
    printf("LINUX KERNEL NETLINK HARDWARE UEVENT MONITOR\\n");
    printf("Listening for USB, PCI, and Block device events...\\n");
    printf("====================================================\\n");

    // Open Netlink socket bound to kernel kobject uevent multicast
    int sock_fd = socket(PF_NETLINK, SOCK_RAW, NETLINK_KOBJECT_UEVENT);
    if (sock_fd < 0) {
        perror("socket(NETLINK_KOBJECT_UEVENT)");
        return 1;
    }

    struct sockaddr_nl sa;
    memset(&sa, 0, sizeof(sa));
    sa.nl_family = AF_NETLINK;
    sa.nl_groups = 1; // Multicast group 1 (uevent broadcast)
    sa.nl_pid = getpid();

    if (bind(sock_fd, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
        perror("bind");
        close(sock_fd);
        return 1;
    }

    char buffer[UEVENT_BUFFER_SIZE];

    // Read and decode broadcast uevents
    while (1) {
        ssize_t len = recv(sock_fd, buffer, sizeof(buffer) - 1, 0);
        if (len < 0) {
            if (errno == EINTR) continue;
            perror("recv");
            break;
        }

        // Kernel separates key-value strings with null bytes ('\\0')
        buffer[len] = '\\0';
        printf("\\n[KERNEL HARDWARE EVENT DETECTED]\\n");

        char *ptr = buffer;
        while (ptr < buffer + len) {
            if (strlen(ptr) > 0) {
                printf("  |-- %s\\n", ptr);
            }
            ptr += strlen(ptr) + 1;
        }
    }

    close(sock_fd);
    return 0;
}
```

---

## 5. Production Post-Mortem: The PCIe AER Link Flapping Disaster
### The Outage
A distributed Ceph storage node lost 4 NVMe drives simultaneously under heavy 100 GbE network traffic. Drives disappeared from `/dev/nvme*` without physical power loss.

### Root Cause Analysis
Examination of `dmesg -T` revealed:
`PCIe Bus Error: severity=Corrected, type=Physical Layer, (Receiver Error)`
`pcieport 0000:00:03.0: AER: Multiple Corrected error received`
The server chassis backplane had a micro-fractured PCIe riser cable. High electromagnetic interference from neighboring GPU fans corrupted PCIe TLP (Transaction Layer Packets). Once the PCIe Advanced Error Reporting (AER) error counter exceeded the kernel threshold, the kernel link-training state machine automatically downgraded the link width from Gen4 x4 to Gen1 x1, and eventually took the bus offline to protect system RAM from DMA corruption.

### Remediation
1. Monitored PCIe AER counters via sysfs:
   ```bash
   cat /sys/bus/pci/devices/0000:03:00.0/aer_dev_correctable
   ```
2. Replaced defective PCIe riser cable and verified link speed via `lspci -vvv -s 03:00.0 | grep LnkSta`.

---

## 6. USB Bus Topology & Descriptor Hierarchy
Universal Serial Bus (USB) uses a tiered-star topology anchored by a **Host Controller** and a **Root Hub**. Devices communicate over logical channels called **Pipes** connected to hardware **Endpoints**.

```
+----------------------------------------------------------------------------+
|                          Device Descriptor (18 Bytes)                      |
|                  idVendor, idProduct, bNumConfigurations                   |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
|                     Configuration Descriptor (9 Bytes)                     |
|                 bNumInterfaces, bmAttributes, bMaxPower                    |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
|                       Interface Descriptor (9 Bytes)                       |
|           bInterfaceClass (e.g. 0x03 HID, 0x08 Mass Storage)               |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
|                        Endpoint Descriptors (7 Bytes)                      |
|            bEndpointAddress (Direction: IN/OUT, Endpoint Number)           |
|            bmAttributes (0=Control, 1=Isochronous, 2=Bulk, 3=Interrupt)    |
|            wMaxPacketSize (e.g. 64B for USB 2.0 Full Speed, 1024B SuperSpeed)|
+----------------------------------------------------------------------------+
```

### The Four USB Transfer Types
1. **Control Transfers**: Bi-directional transfers on Endpoint 0 used exclusively for device enumeration, descriptor queries, and bus configuration.
2. **Interrupt Transfers**: Unidirectional, guaranteed latency polling (e.g., keyboards, mice, gamepads). Fixed polling intervals (`bInterval`).
3. **Bulk Transfers**: Unidirectional, non-time-critical high-bandwidth transfers with guaranteed error correction and hardware retries (e.g., USB flash drives, printers, external SSDs).
4. **Isochronous Transfers**: Unidirectional, real-time periodic data with guaranteed bandwidth but **NO RETRIES** (e.g., webcams, audio streaming). Dropped packets are dropped permanently to maintain clock synchronization.

---

## 7. Creating Custom sysfs Attributes in Kernel Drivers
Device drivers expose runtime configuration knobs to userspace via the `sysfs` filesystem using the `DEVICE_ATTR` macro family:

```c
#include <linux/device.h>
#include <linux/kernel.h>

static int debug_level = 1;

// Read callback invoked when userspace runs: cat /sys/devices/.../debug_level
static ssize_t debug_level_show(struct device *dev, struct device_attribute *attr, char *buf) {
    // buf is guaranteed to be a full PAGE_SIZE (4096 bytes)
    return sysfs_emit(buf, "%d\n", debug_level);
}

// Write callback invoked when userspace runs: echo 3 > /sys/devices/.../debug_level
static ssize_t debug_level_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count) {
    int val;
    if (kstrtoint(buf, 10, &val) < 0) {
        return -EINVAL;
    }
    debug_level = val;
    dev_info(dev, "Updated driver debug level to %d\n", debug_level);
    return count; // Must return number of consumed bytes
}

// Define: dev_attr_debug_level with rw permissions (0644)
static DEVICE_ATTR_RW(debug_level);
```

When the driver attaches to the device, it registers the attribute group:
```c
static struct attribute *my_attrs[] = {
    &dev_attr_debug_level.attr,
    NULL,
};
static const struct attribute_group my_attr_group = {
    .attrs = my_attrs,
};

// Inside probe():
sysfs_create_group(&pdev->dev.kobj, &my_attr_group);
```
Userspace can now dynamically read and tune driver internal parameters directly via `/sys` without compiling or restarting services!

