# Day 35: Packet Capture & Sniffing (`tcpdump`, BPF)

## 1. Architectural Foundations: `AF_PACKET` Raw Sockets & BPF
How does `tcpdump` intercept raw network packets before the kernel firewall (`iptables`/`nftables`) or socket buffers process them?
`tcpdump` operates via two foundational kernel technologies:
1. **`AF_PACKET` Sockets (`SOCK_RAW`)**: A specialized socket family (`socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))`) that taps into the device driver layer (`netif_receive_skb`).
2. **Berkeley Packet Filter (BPF / cBPF)**: Running in-kernel packet filtering code.

If the kernel copied every 25 Gbps packet to user space for `tcpdump` to inspect, the host would crash from memory bus exhaustion.
Instead, `tcpdump` compiles your filter expression (e.g. `port 80`) into a tiny, high-performance **BPF bytecode program**.
The BPF program runs **inside the kernel interrupt handler**. If a packet does not match the filter, it is discarded immediately without waking up user space!

```
+-------------------------------------------------------------------------+
| PACKET CAPTURE ARCHITECTURE: AF_PACKET & BPF                            |
|                                                                         |
| Network Interface Card (NIC)                                            |
|      |                                                                  |
|      v                                                                  |
| Kernel Driver Layer (netif_receive_skb)                                 |
|      |                                                                  |
|      +---> [In-Kernel BPF Filter Program]                               |
|      |            |                                                     |
|      |      Matches filter?                                             |
|      |      /            \                                             |
|      |   (NO)            (YES)                                          |
|      |    v                v                                            |
|      | Discard       Copy to AF_PACKET Ring Buffer                      |
|      |                     |                                            |
|      v                     v                                            |
| Standard IP Stack     User space (tcpdump / Wireshark)                  |
| (iptables, TCP, app)                                                    |
+-------------------------------------------------------------------------+
```

---

## 2. Kernel Data Structures: `struct sock_fprog` & BPF Instructions
A BPF filter program is composed of 64-bit microcode instructions (`linux/filter.h`):

```c
struct sock_filter {
    __u16   code;   /* Actual BPF opcode (e.g. BPF_LD, BPF_JMP) */
    __u8    jt;     /* Jump offset if test is true */
    __u8    jf;     /* Jump offset if test is false */
    __u32   k;      /* Generic multiuse field (address/immediate value) */
};

struct sock_fprog {
    unsigned short      len;    /* Number of BPF instructions */
    struct sock_filter  *filter;/* Pointer to instruction array */
};
```

When you write `tcpdump -d 'ip and tcp port 80'`, `tcpdump` outputs the disassembled BPF bytecode:
```
(000) ldh      [12]                ; Load Ethernet type field at offset 12
(001) jeq      #0x800   jt 2  jf 8 ; Is it IPv4 (0x0800)?
(002) ldb      [23]                ; Load IP protocol field at offset 23
(003) jeq      #0x6     jt 4  jf 8 ; Is it TCP (protocol 6)?
(004) ldh      [20]                ; Load IP flags & fragment offset
(005) jset     #0x1fff  jt 8  jf 6 ; Skip if packet is a fragment!
(006) ldh      [56]                ; Load destination TCP port
(007) jeq      #0x50    jt 9  jf 8 ; Port 80? If yes, keep packet!
(008) ret      #0                  ; Discard packet!
(009) ret      #262144             ; Keep up to 262144 bytes!
```

---

## 3. Essential Command Patterns: `tcpdump` Masterclass

### Production Capture Filters
```bash
# Capture packets on specific interface, don't resolve hostnames/ports (-n -nn)
tcpdump -i eth0 -nn

# Capture full packet payload without truncation (-s 0)
tcpdump -i eth0 -nn -s 0 -w /tmp/capture.pcap

# Capture traffic for a specific host and port
tcpdump -i eth0 -nn host 192.168.1.50 and port 443

# Capture only TCP SYN packets (Detects incoming connection attempts!)
tcpdump -i eth0 -nn "tcp[tcpflags] & (tcp-syn) != 0 and tcp[tcpflags] & (tcp-ack) == 0"

# Capture only TCP RST packets (Detects abrupt connection drops!)
tcpdump -i eth0 -nn "tcp[tcpflags] & (tcp-rst) != 0"

# Print packet payload in ASCII and HEX (-X)
tcpdump -i eth0 -nn -X port 80
```

---

## 4. Reading and Analyzing PCAP Files
```bash
# Read an existing capture file without re-sniffing
tcpdump -nn -r /tmp/capture.pcap

# Filter an existing pcap file for HTTP POST requests
tcpdump -nn -r /tmp/capture.pcap "tcp dst port 80 and (tcp[((tcp[12:1] & 0xf0) >> 2):4] = 0x504f5354)"
```

---

## 5. Compilable C Program: Raw Socket Sniffer with `AF_PACKET`
```c
/*
 * raw_packet_sniffer.c - Captures raw Ethernet frames using AF_PACKET
 * Compile: gcc -O2 -Wall raw_packet_sniffer.c -o raw_packet_sniffer
 * Run: sudo ./raw_packet_sniffer
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <netinet/ether.h>
#include <arpa/inet.h>

#define BUF_SIZE 65536

int main(void) {
    int raw_sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (raw_sock < 0) {
        perror("socket(AF_PACKET) - Requires root/sudo!");
        return 1;
    }

    printf("=========================================\n");
    printf("RAW AF_PACKET ETHERNET SNIFFER ACTIVE\n");
    printf("Capturing 5 packets...\n");
    printf("=========================================\n");

    unsigned char buffer[BUF_SIZE];
    for (int i = 0; i < 5; i++) {
        ssize_t data_size = recvfrom(raw_sock, buffer, BUF_SIZE, 0, NULL, NULL);
        if (data_size < 0) {
            perror("recvfrom");
            break;
        }

        struct ether_header *eth = (struct ether_header *)buffer;
        printf("Packet %d (%zd bytes): ", i + 1, data_size);
        printf("Src MAC: %s -> ", ether_ntoa((struct ether_addr *)eth->ether_shost));
        printf("Dst MAC: %s | ", ether_ntoa((struct ether_addr *)eth->ether_dhost));

        if (ntohs(eth->ether_type) == ETHERTYPE_IP) {
            struct iphdr *ip = (struct iphdr *)(buffer + sizeof(struct ether_header));
            char src_ip[INET_ADDRSTRLEN], dst_ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &(ip->saddr), src_ip, sizeof(src_ip));
            inet_ntop(AF_INET, &(ip->daddr), dst_ip, sizeof(dst_ip));
            printf("IPv4: %s -> %s (Proto: %d)\n", src_ip, dst_ip, ip->protocol);
        } else {
            printf("Non-IPv4 Frame (0x%04x)\n", ntohs(eth->ether_type));
        }
    }

    close(raw_sock);
    return 0;
}
```

---

## 6. Production War Story: The Storage Exhaustion `tcpdump` Outage
In 2020, a network engineer logged into a core production database server to diagnose intermittent latency.
The engineer ran:
`sudo tcpdump -i any -w /root/debug.pcap`
The engineer went home for the weekend, forgetting that `tcpdump` was running in the background.
On a 10 Gbps database server carrying high-throughput replica traffic, `debug.pcap` wrote data at 120 MB/second.
Within 90 minutes, the root filesystem (`/`) was $100\%$ full.
The database kernel tried to append to write-ahead logs (`WAL`), failed with `ENOSPC: No space left on device`, and crashed into an emergency shutdown state, taking down the entire e-commerce checkout system.
Rule of thumb:
1. **Always use circular buffer rotation**: `tcpdump -W 5 -C 100 -w capture.pcap` (Max 5 files of 100 MB each).
2. **Always restrict packet snapshot length (`-s`)**: Capture headers only (`-s 96`).
---

## 8. Deep Systems Internals: Packet Ring Buffers (`PACKET_MMAP`)
To achieve zero-copy packet capture at 10 Gbps and 100 Gbps speeds, Linux provides **`PACKET_MMAP`** (via `PACKET_RX_RING` socket options).
In standard raw sockets:
- Every packet triggers a hardware interrupt.
- The kernel copies packet bytes into user space via `recvfrom()` (expensive memory copy + CPU context switch).
In `PACKET_MMAP`:
1. The kernel allocates a contiguous ring buffer in kernel memory.
2. The user application maps this memory directly into its address space via `mmap()`.
3. The kernel writes packets directly into the shared ring buffer and hands ownership to user space with atomic memory barriers.
4. Tools like `tshark`, `Suricata`, and `Zeek` use `PACKET_MMAP` to capture millions of packets per second with zero packet drops!
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `tcpdump` reports `packet dropped by kernel` in output summary**:
   - Root Cause: The rate of incoming packets exceeded the user space buffer draining speed. The `AF_PACKET` socket queue overflowed.
   - Fix: Increase socket receive buffer: `tcpdump -B 4096` (Allocates 4 MB buffer), and use narrow BPF filters (`port 443`) to discard unwanted traffic in kernel space.
2. **Symptom: Captured packet payload shows truncated data**:
   - Older versions of tcpdump default to snapshot length of 68 or 96 bytes.
   - Fix: Always specify `-s 0` (or `-s 65535`) to capture full, untruncated packet payloads.
3. **Symptom: Packet timestamps are drifting or inaccurate**:
   - Check if NIC hardware timestamping is supported: `ethtool -T eth0`.
   - Enable hardware timestamping in tcpdump using `-j adapter_unsynced`.
---

## 10. Advanced Security Auditing: Capturing Without Root via Linux Capabilities
Running `tcpdump` as `root` is a security risk. If a maliciously crafted packet triggers a vulnerability in `libpcap`'s protocol parser, the attacker achieves root code execution!
Instead, grant `tcpdump` fine-grained Linux Capabilities:
```bash
# Grant raw packet capture and network administration capabilities
sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/sbin/tcpdump

# Now run tcpdump as an unprivileged user!
tcpdump -i eth0 -nn
```
---

## 11. Advanced BPF Bytecode JIT Compilation & Hardware Offload
In modern Linux kernels (4.x+):
1. The classic cBPF (classic Berkeley Packet Filter) bytecode generated by `tcpdump` is automatically translated by the kernel into **eBPF (extended BPF)**.
2. The kernel's **BPF JIT (Just-In-Time) Compiler** translates eBPF bytecode into native x86-64 machine code instructions!
```bash
# Check if BPF JIT compiler is enabled (1 = enabled)
cat /proc/sys/net/core/bpf_jit_enable
```
3. On high-end SmartNICs (e.g. Netronome, Mellanox ConnectX-6), the compiled BPF filter can even be offloaded directly into the **NIC hardware ASIC**!
   Packets that do not match the filter are discarded on the physical network card before traversing the PCIe bus or waking up the host CPU!
