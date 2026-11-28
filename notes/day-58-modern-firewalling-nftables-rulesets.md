# Day 58: Modern Firewalling: nftables VM Bytecode, Sets, Dictionaries, and Atomic Ruleset Swaps

For nearly two decades, Linux packet filtering was fragmented across four distinct utilities: `iptables` (IPv4), `ip6tables` (IPv6), `arptables` (ARP), and `ebtables` (Ethernet bridging). Each utility implemented duplicate kernel code and linear rule matching. `nftables` (Linux 3.13+) replaces this legacy infrastructure with an in-kernel lightweight register-based Virtual Machine (VM). Instead of hardcoded packet matchers, `nftables` compiles declarative rules into bytecode, provides $O(1)$ set lookups, and enforces atomic transactional ruleset commits.

---

## 1. The nftables Virtual Machine Architecture

The core of `nftables` is a tiny, high-performance bytecode interpreter embedded in `net/netfilter/nf_tables_core.c`. A rule in `nftables` is an array of sequential VM instructions (expressions) executed against packet data.

```text
Incoming Packet (sk_buff)
          |
          v
+-----------------------------------------------------------+
|               nftables Kernel VM Engine                   |
|                                                           |
|  [ Reg 1: Payload ]   [ Reg 2: Metadata ]   [ Reg Verdict ]|
|                                                           |
|  Instruction 1: nft_payload_get (Offset: 12, Len: 4)      |
|                 -> Load IPv4 Dst into Reg 1               |
|                                                           |
|  Instruction 2: nft_cmp_fast (Reg 1 == 192.168.1.1)       |
|                 -> Match: Continue; Mismatch: Next Rule   |
|                                                           |
|  Instruction 3: nft_payload_get (Offset: 22, Len: 2)      |
|                 -> Load TCP Dst Port into Reg 1           |
|                                                           |
|  Instruction 4: nft_set_lookup (Reg 1 in @allowed_ports)  |
|                 -> O(1) Hash / O(log N) RB-Tree Match     |
|                                                           |
|  Instruction 5: nft_immediate (Verdict = NF_ACCEPT)       |
+-----------------------------------------------------------+
```

### The Kernel Expression Struct (`include/net/netfilter/nf_tables.h`)
```c
struct nft_expr {
    const struct nft_expr_ops   *ops;
    unsigned char               data[] __aligned(NFT_EXPR_DMA_ALIGN);
};

struct nft_regs {
    /* Four 32-bit data registers (Reg 1 to 4) */
    u32             data[4];
    /* Verdict register: NF_ACCEPT, NF_DROP, NFT_GOTO, NFT_JUMP */
    struct nft_verdict verdict;
};
```

---

## 2. Advanced Data Structures: Sets, Dictionaries, and Concatenations

The most profound performance breakthrough in `nftables` is native support for typed data structures directly inside kernel memory.

### Algorithmic Comparison: iptables vs nftables Sets
- **Legacy `iptables` with IP-set**: Requires separate `ipset` daemon, synchronized via netlink.
- **`nftables` Sets**: Built directly into the grammar. Uses **rbtrees** (red-black trees) for intervals/subnets ($O(\log N)$ search) and **hash tables** for discrete IPs ($O(1)$ search).

$$\text{Complexity for } N \text{ rules}: \quad T_{\text{iptables}} = O(N), \quad T_{\text{nftables}} = O(1)$$

```text
# nftables anonymous set
nft add rule inet filter input ip saddr { 10.0.0.1, 10.0.0.2, 192.168.1.0/24 } accept

# nftables Dictionary (Map): Evaluates key and sets target action in 1 step!
nft add rule inet filter input tcp dport vmap { 22 : accept, 80 : accept, 443 : accept, 3306 : drop }
```

### Concatenations (Tuple Matching Without Multi-Rule Loops)
`nftables` allows concatenating disparate packet fields into a single compound lookup key:
```text
# Matches (Source IP, Destination Port) simultaneously in 1 lookup
nft add rule inet filter input ip saddr . tcp dport @firewall_matrix
```

---

## 3. Atomic Ruleset Replacement & Transaction Semantics

A critical flaw in `iptables` was non-atomic rule updates. Modifying rules required dumping the entire table to userspace, editing the list in userspace, and re-injecting the whole blob. Under heavy traffic, packets were processed against half-loaded states.

### The Netlink Transaction Engine
`nftables` implements an ACID-compliant transactional model:
1. Userspace prepares an atomic transaction batch over Netlink socket (`NFNL_MSG_BATCH_BEGIN`).
2. The kernel verifies all expressions, allocates memory, and pre-validates bytecode.
3. If any single rule fails syntax or memory allocation, the entire batch is rolled back (`NFNL_MSG_BATCH_ABORT`).
4. On success (`NFNL_MSG_BATCH_END`), the kernel atomically switches rule generation counters with zero packet drops.

```text
Generation N:   [Active Ruleset Table A] <--- Processing Live Traffic
                           |
                     (Atomic Flip)
                           v
Generation N+1: [New Ruleset Table B]    <--- Processing Live Traffic
```

---

## 4. Compilable C Implementation: Interfacing with libnftnl Engine

`libnftnl` is the low-level C library providing userspace translation from C structures to Netlink bytecode objects.

Compile with: `gcc -O2 -Wall -Wextra test_nft.c -o test_nft -lnftnl -lmnl`

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libmnl/libmnl.h>
#include <libnftnl/table.h>
#include <linux/netfilter.h>
#include <linux/netfilter/nf_tables.h>

int main(void) {
    /* Initialize an nftables table object */
    struct nftnl_table *table = nftnl_table_alloc();
    if (table == NULL) {
        perror("nftnl_table_alloc failed");
        return EXIT_FAILURE;
    }

    /* Configure Table Name and Address Family (inet = IPv4 + IPv6 unified) */
    nftnl_table_set_str(table, NFTNL_TABLE_NAME, "production_filter");
    nftnl_table_set_u32(table, NFTNL_TABLE_FAMILY, NFPROTO_INET);

    printf("SUCCESS: Configured nftables table 'production_filter' (Family: INET).\n");
    printf("Bytecode compilation engine ready for rule insertion.\n");

    /* Free allocated structure */
    nftnl_table_free(table);
    return EXIT_SUCCESS;
}
```

---

## 5. Unified Dual-Stack Architecture: The `inet` Family

In legacy configurations, engineers maintained dual rulebooks:
- `/etc/iptables/rules.v4` for IPv4
- `/etc/iptables/rules.v6` for IPv6

Discrepancies between the two files frequently left IPv6 ports open to the public internet while IPv4 was strictly locked down.

### The Unified `inet` Table Solution
`nftables` introduces the `inet` table family, which evaluates IPv4 and IPv6 packets within a single unified rulebook:

```text
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        # Accept loopback traffic for both 127.0.0.1 and ::1
        iif "lo" accept

        # Accept established connections for both IPv4 and IPv6
        ct state established,related accept

        # Accept ICMP (IPv4) and ICMPv6 (IPv6) essential neighbor discovery
        ip protocol icmp accept
        ip6 nexthdr icmpv6 accept

        # Allow SSH on both protocols simultaneously
        tcp dport 22 accept
    }
}
```

---

## 6. Production Post-Mortem: DDoS Rule Bloat CPU Starvation

### Incident Overview
A financial brokerage firm suffered a sustained distributed denial-of-service (DDoS) attack consisting of randomized UDP packets across 80,000 source IP addresses. The automated mitigation script appended an `iptables` drop rule for each attacking IP:
```bash
iptables -A INPUT -s $ATTACKER_IP -j DROP
```

### The Cascade Failure
1. By rule 45,000, `iptables` was performing $45,000$ sequential pointer traversals per incoming packet.
2. At an ingress rate of $350,000$ packets per second, each packet required traversing thousands of rules before matching.
3. System CPU time spent in `ksoftirqd` reached 100% across all 32 processor cores. Legitimate client transactions stalled completely.

### The nftables Remediation
The security team migrated the mitigation pipeline to an `nftables` dynamic set:
```bash
# Create high-speed hash set
nft add set inet filter blackhole { type ipv4_addr\; flags timeout\; }
nft add rule inet filter input ip saddr @blackhole drop

# Mitigation bot simply adds IPs to the set with 1-hour expiration:
nft add element inet filter blackhole { 198.51.100.25 timeout 1h }
```
Because the set evaluates in $O(1)$ time via the internal kernel hash table, CPU utilization plummeted from 100% to **3.2%**, and the DDoS attack was completely neutralized.
---

## 7. State Synchronization with conntrackd in High-Availability Pairs

In enterprise environments deploying active-backup firewall pairs (using CARP, VRRP, or Keepalived), dropping state tables upon a node failover terminates millions of active TCP sessions.

### The conntrackd Replication Daemon
Linux integrates userspace state synchronization via `conntrackd` (`netfilter/conntrack-tools`):
1. **Event Multicast**: When a master node processes a new TCP flow, the kernel Netfilter conntrack hook emits an event over `NFNETLINK`.
2. **Dedicated Sync Network**: `conntrackd` captures this event and multicasts it over an isolated heartbeat VLAN to the backup node.
3. **Hot Standby Table Injection**: The backup node injects the exact 5-tuple, sequence numbers, and TCP window scaling factors into its local kernel conntrack table.
4. **Zero-Downtime Failover**: Upon master physical failure, the backup node takes over the virtual IP (VIP) without requiring clients to re-establish TCP connections.
---

## 8. Packet Tracing in nftables with nftrace

Debugging complex packet drop issues in `nftables` does not require inserting artificial logging rules. Modern kernels feature built-in tracing via `meta nftrace`:

```bash
# Enable tracing for incoming packets matching specific destination port
nft add rule inet filter input tcp dport 8080 meta nftrace set 1

# Monitor kernel trace events in real time
nft monitor trace
```
The output streams each expression evaluation, register contents, and intermediate verdicts directly from the kernel VM, enabling microsecond diagnosis of routing and filtering anomalies.
