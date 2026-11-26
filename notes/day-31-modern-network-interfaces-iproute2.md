# Day 31: Modern Network Interface CLI (`ip link`, `ip addr`)

## 1. Architectural Foundations: Deprecation of `net-tools` (`ifconfig`)
For the first two decades of Linux, network interface configuration was handled by the `net-tools` package (`ifconfig`, `route`, `arp`). However, in 2001, Linux kernel networking underwent a fundamental architectural transformation:
1. `ifconfig` relies on legacy `ioctl()` system calls (`SIOCGIFADDR`, `SIOCSIFADDR`) on dummy sockets.
2. The legacy `ioctl` interface is synchronous, inefficient, cannot report multiple IP addresses per interface cleanly, and is blind to modern kernel features like network namespaces, policy routing, VLANs, and traffic control.
3. Modern Linux uses **`iproute2`** (via the `ip` binary), which communicates with the kernel through **Netlink Sockets (`AF_NETLINK`)**.

```
+-------------------------------------------------------------------------+
| SYSTEM CALL ARCHITECTURE: NET-TOOLS VS IPROUTE2                         |
|                                                                         |
| [ifconfig / route]                   [ip link / ip addr / ip route]     |
|         |                                          |                    |
|    ioctl(fd, SIOC...)                  socket(AF_NETLINK, NETLINK_ROUTE)|
|         |                                          |                    |
|  Synchronous / Slow                Asynchronous / Event-Driven / Fast   |
|  Single IP per device               Arbitrary secondary IPs & VLANs    |
|  Blind to namespaces                Full Network Namespace awareness    |
|         v                                          v                    |
| +---------------------------------------------------------------------+ |
| |                         LINUX KERNEL CORE                           | |
| +---------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
```

---

## 2. Kernel Data Structures: `struct net_device` & Netlink
In the Linux kernel source (`include/linux/netdevice.h`), every network interface is represented by `struct net_device`:

```c
struct net_device {
    char                name[IFNAMSIZ];      /* Interface name, e.g. "eth0" */
    unsigned long       mem_end;             /* Shared memory end */
    unsigned long       mem_start;           /* Shared memory start */
    unsigned long       base_addr;           /* Device I/O address */
    int                 irq;                 /* Device IRQ number */
    unsigned long       state;               /* Interface state flags */
    struct net_device_stats stats;           /* Packet statistics (rx/tx) */
    unsigned int        flags;               /* IFF_UP, IFF_BROADCAST, etc. */
    unsigned int        mtu;                 /* Maximum Transmission Unit */
    unsigned short      type;                /* Interface hardware type */
    unsigned char       dev_addr[MAX_ADDR_LEN]; /* Hardware MAC address */
    /* ... pointer to packet transmit queues and Netlink handlers ... */
};
```

When you execute `ip link set eth0 up`, `ip` creates a `NETLINK_ROUTE` socket and sends a `RTM_NEWLINK` message to the kernel. The kernel updates the `flags` field in `struct net_device` to include `IFF_UP`, initializes hardware DMA descriptor rings, and enables interrupts.

---

## 3. Essential Command Patterns: `ip link` & `ip addr`

### Managing Interface Physical / Link Layer (`ip link`)
```bash
# List all network interfaces with link layer details (MAC, MTU, state)
ip link show

# Bring an interface UP or DOWN
ip link set dev eth0 up
ip link set dev eth0 down

# Change Maximum Transmission Unit (MTU) - e.g. for Jumbo Frames
ip link set dev eth0 mtu 9000

# Change MAC address (device must be DOWN first)
ip link set dev eth0 down
ip link set dev eth0 address 00:11:22:33:44:55
ip link set dev eth0 up

# Enable Promiscuous Mode (sniffs all packets on the broadcast domain)
ip link set dev eth0 promisc on
```

### Managing IP Layer Configurations (`ip addr`)
```bash
# Display IP addresses across all interfaces with CIDR notation
ip -br addr show        # Brief one-line format
ip addr show dev eth0   # Detailed view for specific interface

# Assign an IPv4 address with subnet mask
ip addr add 192.168.1.50/24 dev eth0

# Assign a secondary IPv4 address to the same interface (No sub-interfaces needed!)
ip addr add 10.0.0.50/16 dev eth0

# Delete an assigned IP address
ip addr del 192.168.1.50/24 dev eth0

# Flush all IP addresses on an interface instantly
ip addr flush dev eth0
```

---

## 4. Deep Mechanics: Interface Flags & Link States
When reading `ip link show`, examine the flags enclosed in angle brackets:
`eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000`

- **`UP`**: Administrative status. The system administrator enabled the interface (`ip link set eth0 up`).
- **`LOWER_UP`**: Physical layer status (L1/L2 carrier detect). Physical Ethernet cable is plugged in and link negotiation succeeded, or Wi-Fi radio is associated.
- **`NO-CARRIER`**: Administrative state is `UP`, but the physical wire is unplugged or switch port is dead!
- **`PROMISC`**: Interface is in promiscuous mode, delivering all observed network frames to the kernel network stack, regardless of destination MAC address.

---

## 5. Compilable C Program: Inspecting Network Interfaces via Netlink
```c
/*
 * netlink_interface_dump.c - Queries network interface names via Linux Netlink
 * Compile: gcc -O2 -Wall netlink_interface_dump.c -o netlink_interface_dump
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <net/if.h>

#define BUF_SIZE 8192

int main(void) {
    int fd = socket(AF_NETLINK, SOCK_RAW, NETLINK_ROUTE);
    if (fd < 0) {
        perror("socket(AF_NETLINK)");
        return 1;
    }

    struct {
        struct nlmsghdr n;
        struct ifinfomsg r;
    } req;

    memset(&req, 0, sizeof(req));
    req.n.nlmsg_len = NLMSG_LENGTH(sizeof(struct ifinfomsg));
    req.n.nlmsg_flags = NLM_F_REQUEST | NLM_F_DUMP;
    req.n.nlmsg_type = RTM_GETLINK;
    req.r.ifi_family = AF_UNSPEC;

    if (send(fd, &req, req.n.nlmsg_len, 0) < 0) {
        perror("send");
        close(fd);
        return 1;
    }

    char buf[BUF_SIZE];
    ssize_t len = recv(fd, buf, sizeof(buf), 0);
    if (len < 0) {
        perror("recv");
        close(fd);
        return 1;
    }

    printf("=========================================\n");
    printf("KERNEL NETLINK INTERFACE AUDIT (RTM_GETLINK)\n");
    printf("=========================================\n");

    struct nlmsghdr *nlh = (struct nlmsghdr *)buf;
    while (NLMSG_OK(nlh, len)) {
        if (nlh->nlmsg_type == NLMSG_DONE) break;
        struct ifinfomsg *ifi = (struct ifinfomsg *)NLMSG_DATA(nlh);
        struct rtattr *rta = IFLA_RTA(ifi);
        int rta_len = IFLA_PAYLOAD(nlh);

        char ifname[IFNAMSIZ] = "unknown";
        while (RTA_OK(rta, rta_len)) {
            if (rta->rta_type == IFLA_IFNAME) {
                strncpy(ifname, (char *)RTA_DATA(rta), IFNAMSIZ - 1);
            }
            rta = RTA_NEXT(rta, rta_len);
        }

        printf("Interface Index: %2d | Name: %-10s | Admin State: %s | Physical: %s\n",
               ifi->ifi_index,
               ifname,
               (ifi->ifi_flags & IFF_UP) ? "UP" : "DOWN",
               (ifi->ifi_flags & IFF_RUNNING) ? "RUNNING (Carrier OK)" : "NO-CARRIER");

        nlh = NLMSG_NEXT(nlh, len);
    }

    close(fd);
    return 0;
}
```

---

## 6. Production War Story: The Promiscuous Mode CPU Exhaustion Incident
In 2019, an SRE deployed an open-source security monitoring agent across a 500-node Kubernetes cluster.
Within 10 minutes of deployment, CPU utilization on all worker nodes spiked to $100\%$, and network packet processing latency surged from 0.1ms to 45ms!
Investigation revealed that the agent had enabled `promisc on` on the physical 25 Gbps network interface (`ip link set dev eth0 promisc on`).
Under normal operation, the network interface card (NIC) hardware filters out packets whose destination MAC address does not match the host.
By putting the NIC into promiscuous mode, the hardware filter was completely disabled. Every single multicast, broadcast, and VLAN packet on the physical top-of-rack switch was copied over the PCIe bus and pushed into the Linux kernel network stack, causing millions of software interrupts (`ksoftirqd`) per second.
Lesson: Promiscuous mode should strictly be confined to dedicated packet-sniffing appliances or isolated TAP interfaces.

---

## 7. Verification Checklist & Command Reference
- [ ] Run `ip -br link` to verify all physical interfaces display `UP` and `LOWER_UP`.
- [ ] Verify MTU configuration matches network fabric (Standard Ethernet = 1500, Jumbo Frame SAN = 9000).
- [ ] Ensure interface statistics (`ip -s link show dev eth0`) show zero RX/TX errors or dropped packets.
- [ ] Use `ip addr flush` with caution: flushing on an SSH-connected interface instantly severs the remote session!
---

## 8. Deep Systems Internals: Netlink Protocol Frame Structure
Netlink communication does not use ASCII or text streams; it uses strict binary headers defined in `linux/netlink.h`:
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                          Length                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|            Type               |           Flags               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Sequence Number                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Process ID (PID)                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   Netlink Payload (rtattr...)                 |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

When an interface state changes:
1. The kernel driver detects physical carrier link state change via hardware interrupts.
2. The kernel invokes `rtmsg_ifinfo(RTM_NEWLINK, dev, ...)` to broadcast a netlink event on the `RTNLGRP_LINK` multicast group.
3. User-space network managers (e.g. `systemd-networkd`, `NetworkManager`) listening on netlink sockets receive this event asynchronously in sub-millisecond time without polling!
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `ip link set eth0 up` fails with `RTNETLINK answers: Cannot assign requested address`**:
   - Root Cause: Interface hardware MAC address is corrupted or invalid (all zeros `00:00:00:00:00:00` or multicast `01:...`).
   - Fix: Assign a valid unicast MAC: `ip link set dev eth0 address 52:54:00:12:34:56`.
2. **Symptom: Interface status shows `NO-CARRIER` despite cable connected**:
   - Run `ethtool eth0` to check physical autonegotiation speed and duplex status.
   - Force speed and duplex if switch autonegotiation is broken: `ethtool -s eth0 speed 1000 duplex full autoneg off`.
3. **Symptom: Dropped packets reported in `ip -s link`**:
   - Check ring buffer capacity: `ethtool -g eth0`.
   - Expand RX descriptor ring size to maximum: `ethtool -G eth0 rx 4096`.
