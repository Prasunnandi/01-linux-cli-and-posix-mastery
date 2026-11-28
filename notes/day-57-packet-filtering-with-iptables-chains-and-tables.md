# Day 57: Packet Filtering Architecture: Netfilter Hooks, iptables Chains, and Conntrack State Tables

Network firewalls on Linux do not operate in userspace; packet evaluation executes within the kernel's core networking stack via **Netfilter**. First introduced in Linux 2.4, Netfilter inserts interception hooks into the traversal path of IP packets. The userspace frontend `iptables` constructs structured tables containing ordered rules organized into chains. This masterclass deconstructs the five Netfilter hook points, packet traversal order, linear rule evaluation complexity, and the stateful connection tracking (`conntrack`) engine.

---

## 1. The Five Netfilter Kernel Hooks & Architecture

When an Ethernet frame arrives at a network interface, the network driver decodes the Layer 2 header and passes the `struct sk_buff` to the IP stack (`ip_rcv()`). Netfilter intercepts the packet at five critical interception milestones:

```text
                  [ Network Wire: Ingress Frame ]
                                |
                                v
                       +-----------------+
                       |  NF_INET_PRE_   |
                       |    ROUTING      |  (Raw, Mangle, DNAT)
                       +-----------------+
                                |
                                v
                      [ Routing Decision ]
                                |
              +-----------------+-----------------+
              | (Destination: Local)              | (Destination: Remote Host)
              v                                   v
    +-------------------+               +-------------------+
    |  NF_INET_LOCAL_IN | (Filter,      |  NF_INET_FORWARD  | (Mangle,
    |                   |  Mangle)      |                   |  Filter)
    +-------------------+               +-------------------+
              |                                   |
              v                                   |
     [ Local Process / Socket ]                   |
              |                                   |
              v                                   |
    [ Routing Decision ]                          |
              |                                   |
              v                                   |
    +--------------------+                        |
    | NF_INET_LOCAL_OUT  | (Raw, Mangle,          |
    |                    |  DNAT, Filter)         |
    +--------------------+                        |
              |                                   |
              +-----------------+-----------------+
                                |
                                v
                       +-----------------+
                       |  NF_INET_POST_  |
                       |    ROUTING      |  (Mangle, SNAT / Masquerade)
                       +-----------------+
                                |
                                v
                  [ Network Wire: Egress Frame ]
```

### Hook Point Definitions (from `include/uapi/linux/netfilter.h`)
```c
enum nf_inet_hooks {
    NF_INET_PRE_ROUTING,  /* 0: Directly after NIC ingress, before IP route lookup */
    NF_INET_LOCAL_IN,     /* 1: Packet addressed to local machine sockets */
    NF_INET_FORWARD,      /* 2: Packet destined for another host (routed hop) */
    NF_INET_LOCAL_OUT,    /* 3: Outgoing packet created by local socket */
    NF_INET_POST_ROUTING, /* 4: Immediately prior to NIC egress transmission */
    NF_INET_NUMHOOKS      /* 5: Total count */
};
```

---

## 2. Table Hierarchy & Strict Traversal Order

Multiple tables attach chains to the same Netfilter hook. When a packet passes a hook, tables execute in a strict deterministic priority order:

1. **`raw` (Priority -300)**: Used exclusively to bypass connection tracking (`NOTRACK` target).
2. **`mangle` (Priority -150)**: Modifies IP header fields (TTL, TOS/DSCP, packet MARKs).
3. **`nat` (Priority -100)**: Translates IP addresses and port numbers (DNAT in PREROUTING; SNAT in POSTROUTING). Only evaluates the *first* packet of a flow.
4. **`filter` (Priority 0)**: The core security firewall (INPUT, FORWARD, OUTPUT). Decides `ACCEPT`, `DROP`, or `REJECT`.
5. **`security` (Priority 50)**: Mandatory Access Control (SELinux) packet labeling.

---

## 3. Mathematical Analysis: Linear Rule Traversal & Conntrack Hash Tables

### Linear Evaluation Complexity
Unlike routing tables that use $O(1)$ or $O(\log N)$ radix trees, `iptables` evaluates chains **linearly**:

$$T_{\text{traversal}} = O(N_{\text{rules}} \cdot M_{\text{matches}})$$

For a packet $P$ arriving at rate $R$ (packets per second) traversing a chain with $N$ sequential rules, the CPU time consumed scales directly with $N$:

$$\text{CPU Time} = R \times \sum_{i=1}^{k} t_{\text{eval}}(R_i) \quad (\text{where } k \le N \text{ is first matching terminal rule})$$

Under a large blocklist ($N = 50,000$ rules), packet processing time exceeds inter-frame arrival intervals, resulting in 100% CPU softirq saturation (`ksoftirqd`) and network packet drops.

### Connection Tracking (`conntrack`) Hash Mathematics
To mitigate linear rules, stateful firewalls use `conntrack`. Flows are stored in a globally allocated hash table with $2^b$ buckets. Each flow is keyed by a 5-tuple: $(\text{Src IP}, \text{Dst IP}, \text{Src Port}, \text{Dst Port}, \text{Protocol})$.

Given bucket count $B$ and total tracked connections $C$, average lookup time is constant $O(1)$ provided:

$$\text{Load Factor } \alpha = \frac{C}{B} \le 1.0$$

If $C > C_{\text{max}}$ (configured in `/proc/sys/net/netfilter/nf_conntrack_max`), the kernel drops incoming SYN packets with the syslog error:
```text
nf_conntrack: table full, dropping packet
```

---

## 4. Compilable C Implementation: Querying Netfilter Conntrack State Tables

Linux exposes connection tracking state records through the `NFNETLINK` netlink socket interface. The following program demonstrates opening a raw AF_NETLINK socket to query active connections.

Compile with: `gcc -O2 -Wall -Wextra conntrack_query.c -o conntrack_query`

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <errno.h>

#define NETLINK_NETFILTER 12

struct nl_req {
    struct nlmsghdr n;
    struct nfgenmsg  g;
};

int main(void) {
    int fd = socket(AF_NETLINK, SOCK_RAW, NETLINK_NETFILTER);
    if (fd < 0) {
        perror("Failed to open AF_NETLINK netfilter socket");
        return EXIT_FAILURE;
    }

    struct sockaddr_nl sa;
    memset(&sa, 0, sizeof(sa));
    sa.nl_family = AF_NETLINK;

    if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
        perror("bind failed");
        close(fd);
        return EXIT_FAILURE;
    }

    printf("SUCCESS: Bound AF_NETLINK netfilter socket (fd=%d).\n", fd);
    printf("Stateful connection tracking engine interface accessible.\n");

    /* Read /proc/net/nf_conntrack statistics directly from procfs */
    FILE *f = fopen("/proc/sys/net/netfilter/nf_conntrack_count", "r");
    if (f) {
        char count_buf[64];
        if (fgets(count_buf, sizeof(count_buf), f)) {
            printf("Active Conntrack Connections: %s", count_buf);
        }
        fclose(f);
    } else {
        printf("Note: nf_conntrack kernel module may not be loaded.\n");
    }

    close(fd);
    return EXIT_SUCCESS;
}
```

---

## 5. Production Post-Mortem: Conntrack Exhaustion During Kubernetes Ingress Surge

### Incident Overview
During a Black Friday promotional launch, an e-commerce platform hosted on a 64-node Kubernetes cluster suffered total service degradation. External API clients reported connection timeouts, while backend application pods reported zero CPU and memory utilization.

### Root-Cause Analysis
1. **Conntrack Saturation**: The cluster nodes utilized an untuned default setting for `nf_conntrack_max` ($262,144$).
2. **Short-Lived HTTP/1.0 Handshakes**: Millions of mobile clients initiated non-persistent TCP connections. When a TCP connection enters `TIME_WAIT`, `conntrack` retains the flow state in memory for $120$ seconds (default `nf_conntrack_tcp_timeout_time_wait`).
3. **Silent Packet Drops**: The conntrack table reached 262,144 entries. The kernel Netfilter hook began dropping new incoming `SYN` packets unconditionally before they could reach Kubernetes service proxy rules (`kube-proxy`).

### Permanent Remediation
1. **Increase Conntrack Table Capacity**:
```bash
sysctl -w net.netfilter.nf_conntrack_max=2097152
sysctl -w net.netfilter.nf_conntrack_buckets=524288
```
2. **Aggressively Reduce Time-Wait Expiry**:
```bash
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=86400
```
3. **Stateless Raw Bypass**: For high-volume stateless proxies, deploy `NOTRACK` rules in the `raw` table to bypass connection tracking entirely for known ingress ports.
---

## 6. Packet Flow Across the Mangle and NAT Tables

Understanding the exact traversal sequencing across disparate Netfilter tables is essential when building complex policy-based routing (PBR) and network address translation setups.

```text
Incoming Ingress Frame
        |
        v
PREROUTING Hook:
  1. raw (CT state tracking bypass / NOTRACK)
  2. mangle (TOS, DSCP, packet marking via MARK target)
  3. nat (Destination NAT: --to-destination IP:Port)
        |
        v
Routing Decision (Input vs Forward):
  -> If Local Destination:
       INPUT Hook:
         1. mangle
         2. filter (INPUT rules: ACCEPT / DROP / REJECT)
         3. security (SELinux SECMARK)
         4. nat (Local DNAT)
  -> If Forwarded Traffic:
       FORWARD Hook:
         1. mangle
         2. filter (FORWARD rules)
         3. security
        |
        v
POSTROUTING Hook:
  1. mangle
  2. nat (Source NAT / MASQUERADE: --to-source IP)
        |
        v
Physical Wire Egress
```
