# Day 32: Kernel Routing Table Manipulation (`ip route`)

## 1. Architectural Foundations: The Linux FIB (Forwarding Information Base)
Every time a Linux system transmits a packet or receives a packet destined for another host, the kernel's network subsystem queries the **Forwarding Information Base (FIB)**.
The FIB is not a simple linear list; it is a high-performance radix tree (or LC-trie: Level-Compressed Trie) optimized to perform **Longest Prefix Matching (LPM)** in nanoseconds.

When evaluating where to send a packet with destination IP `192.168.1.150`:
1. The kernel checks matching entries in the routing table.
2. If both `192.168.1.0/24` and `0.0.0.0/0` (Default Gateway) exist, the kernel selects `192.168.1.0/24` because `/24` has a longer prefix length than `/0`.
3. If multiple routes match with the same prefix length, the route with the lowest **Metric** value is chosen!

```
+-------------------------------------------------------------------------+
| LONGEST PREFIX MATCH (LPM) TRIE LOOKUP                                  |
|                                                                         |
| Destination IP: 10.1.2.45                                               |
|                                                                         |
| Routing Table Entries:                                                  |
| 1. 0.0.0.0/0 via 192.168.1.1 dev eth0 (Prefix: 0)                      |
| 2. 10.0.0.0/8 via 172.16.0.1 dev tun0 (Prefix: 8)                      |
| 3. 10.1.2.0/24 via 10.1.2.1 dev eth1  (Prefix: 24) <-- MATCHES (LPM!)  |
| 4. 10.1.2.45/32 dev eth2              (Prefix: 32) <-- EXACT MATCH!     |
|                                                                         |
| DECISION: Packet is routed out of eth2 directly!                        |
+-------------------------------------------------------------------------+
```

---

## 2. Kernel Data Structures: `struct fib_table` & Routing Tables
The Linux kernel supports up to **$2^{32}$ distinct routing tables** (configured via `/etc/iproute2/rt_tables`):
- `table 255` (`local`): High-priority table for local machine IPs, loopback, and broadcast addresses. Evaluated first!
- `table 254` (`main`): The default routing table where normal routes reside (`ip route show`).
- `table 253` (`default`): Reserved for post-processing rules.
- Custom tables (`1` to `252`): Used for **Policy-Based Routing (PBR)** via `ip rule`.

```c
/* include/net/ip_fib.h */
struct fib_table {
    struct hlist_node   tb_hlist;
    u32                 tb_id;      /* Table ID: 254 (main), 255 (local) */
    int                 tb_num_default;
    struct rcu_head     rcu;
    unsigned long       *tb_data;   /* Pointer to radix trie structures */
};
```

---

## 3. Essential Command Patterns: `ip route`

### Inspecting Routes
```bash
# Display the main routing table
ip route show

# Display routes in brief format or for specific subnet
ip route show 10.0.0.0/8

# Display routes from the local kernel table (loopback/broadcasts)
ip route show table local

# Simulate a routing lookup for a specific destination IP (Crucial for debugging!)
ip route get 8.8.8.8
# Output shows: 8.8.8.8 via 192.168.1.1 dev eth0 src 192.168.1.50 uid 1000 cache
```

### Adding, Modifying, and Deleting Routes
```bash
# Add a Default Gateway
ip route add default via 192.168.1.1 dev eth0

# Add a static route for a remote network subnet via a router gateway
ip route add 10.50.0.0/16 via 192.168.1.254 dev eth0

# Add a route with an explicit metric (lower metric = higher priority)
ip route add 172.16.0.0/12 via 192.168.1.200 dev eth0 metric 100

# Replace an existing route atomically without packet loss
ip route change default via 192.168.1.2 dev eth0

# Delete a static route
ip route del 10.50.0.0/16 via 192.168.1.254 dev eth0
```

---

## 4. Policy-Based Routing (PBR): Multiple Uplinks & `ip rule`
Standard routing decides packet destination based strictly on **destination IP**.
**Policy-Based Routing (PBR)** allows routing based on **source IP, ingress interface, or firewall mark (fwmark)**.

Scenario: A server has two network providers:
- `eth0` (ISP A: 198.51.100.50)
- `eth1` (ISP B: 203.0.113.50)

If a packet arrives on `eth1` (ISP B), Linux must reply back through `eth1`, not `eth0`!
```bash
# 1. Create a custom routing table in /etc/iproute2/rt_tables (or use ID 100)
# 2. Add default gateway to table 100
ip route add default via 203.0.113.1 dev eth1 table 100

# 3. Add a policy routing rule: any traffic originating from ISP B's IP uses table 100!
ip rule add from 203.0.113.50 table 100

# 4. View active routing policy rules
ip rule show
```

---

## 5. Compilable C Program: Querying the Linux Kernel Routing Table
```c
/*
 * netlink_route_dump.c - Dumps active IPv4 routes via Netlink AF_NETLINK
 * Compile: gcc -O2 -Wall netlink_route_dump.c -o netlink_route_dump
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <arpa/inet.h>
#include <net/if.h>

#define BUF_SIZE 8192

int main(void) {
    int fd = socket(AF_NETLINK, SOCK_RAW, NETLINK_ROUTE);
    if (fd < 0) {
        perror("socket");
        return 1;
    }

    struct {
        struct nlmsghdr n;
        struct rtmsg r;
    } req;

    memset(&req, 0, sizeof(req));
    req.n.nlmsg_len = NLMSG_LENGTH(sizeof(struct rtmsg));
    req.n.nlmsg_flags = NLM_F_REQUEST | NLM_F_DUMP;
    req.n.nlmsg_type = RTM_GETROUTE;
    req.r.rtm_family = AF_INET;
    req.r.rtm_table = RT_TABLE_MAIN;

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
    printf("LINUX KERNEL MAIN ROUTING TABLE DUMP\n");
    printf("=========================================\n");

    struct nlmsghdr *nlh = (struct nlmsghdr *)buf;
    while (NLMSG_OK(nlh, len)) {
        if (nlh->nlmsg_type == NLMSG_DONE) break;
        struct rtmsg *rtm = (struct rtmsg *)NLMSG_DATA(nlh);
        struct rtattr *rta = RTM_RTA(rtm);
        int rta_len = RTM_PAYLOAD(nlh);

        char dst_ip[INET_ADDRSTRLEN] = "default (0.0.0.0)";
        char gw_ip[INET_ADDRSTRLEN]  = "direct-link";
        int if_index = 0;

        while (RTA_OK(rta, rta_len)) {
            if (rta->rta_type == RTA_DST) {
                inet_ntop(AF_INET, RTA_DATA(rta), dst_ip, sizeof(dst_ip));
            } else if (rta->rta_type == RTA_GATEWAY) {
                inet_ntop(AF_INET, RTA_DATA(rta), gw_ip, sizeof(gw_ip));
            } else if (rta->rta_type == RTA_OIF) {
                if_index = *(int *)RTA_DATA(rta);
            }
            rta = RTA_NEXT(rta, rta_len);
        }

        char ifname[IFNAMSIZ];
        if_indextoname(if_index, ifname);

        printf("Dest: %-18s/%-2d | Gateway: %-15s | Interface: %s\n",
               dst_ip, rtm->rtm_dst_len, gw_ip, ifname);

        nlh = NLMSG_NEXT(nlh, len);
    }

    close(fd);
    return 0;
}
```

---

## 6. Production War Story: The Asymmetric Routing Black Hole
In 2018, a major financial enterprise added a backup 10 Gbps direct connection to an AWS cloud environment.
Immediately after adding the second network card, incoming database connections from the cloud began mysteriously timing out during the TCP 3-way handshake!
Packet traces showed:
1. Client sent `SYN` to `eth1` (10 Gbps backup card).
2. The server received the `SYN` and generated `SYN-ACK`.
3. However, the server's default routing table routed all outbound traffic via `eth0` (the primary 1 Gbps internet card)!
4. The client's firewall saw a `SYN-ACK` coming from `eth0`'s IP address instead of `eth1`'s IP, and dropped the packet as an invalid spoofing attempt!
5. Furthermore, Linux's built-in **Reverse Path Filtering (`rp_filter`)** dropped packets because the ingress interface did not match the best reverse route in the FIB!
Fix: Enable policy routing (`ip rule`) for each network card and configure `net.ipv4.conf.all.rp_filter = 2` (Loose Reverse Path verification).

---

## 7. Verification Checklist & Command Reference
- [ ] Use `ip route get <IP>` to test and verify which route and interface the kernel chooses for any destination.
- [ ] Ensure only **one** default gateway exists in the main routing table, or multiple default gateways have distinct metrics.
- [ ] Check `cat /proc/sys/net/ipv4/ip_forward` (must be `1` if the Linux box acts as a router or VPN server).
---

## 8. Deep Systems Internals: The Kernel Routing Cache & Nexthop Objects
In Linux kernels prior to 3.6, route lookups were cached in an explicit "Routing Cache" hash table.
However, attackers discovered that sending packets to randomized IP addresses forced the kernel to generate millions of ephemeral route cache entries, causing hash collisions and kernel denial-of-service (`OOM`).
In modern Linux:
1. The old route cache has been completely eliminated in favor of the lockless **LC-Trie** (Level-Compressed Trie).
2. The lookup time is strictly bounded to $O(\log_2(	ext{prefix length}))$.
3. Starting in Linux 5.3, routes utilize **Nexthop Objects** (`ip nexthop`), decoupling the routing destination from the gateway IP and MAC address resolution. This allows instant BGP/multipath failover across thousands of routes by updating a single nexthop object pointer in memory!
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `ip route add` fails with `RTNETLINK answers: Network is unreachable`**:
   - Root Cause: You attempted to set a gateway IP address that is not in any locally attached subnet!
   - Fix: You must first assign an IP address on that subnet to the local interface before specifying a gateway in that subnet.
2. **Symptom: Server cannot reach internet despite default route present**:
   - Run `ip route get 8.8.8.8` to identify which interface and source IP the kernel selects.
   - Run `arping -I eth0 <gateway_ip>` to verify L2 Ethernet ARP resolution of the gateway MAC address.
3. **Symptom: Intermittent packet loss across dual-homed multi-ISP server**:
   - Check `sysctl net.ipv4.conf.all.rp_filter`. If set to `1` (Strict Reverse Path), packets arriving on non-default interfaces are silently dropped by the kernel!
   - Set `sysctl -w net.ipv4.conf.all.rp_filter=2` (Loose mode).
