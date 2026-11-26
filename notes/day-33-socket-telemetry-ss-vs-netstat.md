# Day 33: Socket Telemetry: `ss` vs Legacy `netstat`

## 1. Architectural Foundations: The Death of `/proc/net/tcp`
For decades, systems administrators used `netstat -tulnp` to check listening network sockets.
However, on high-load production servers with 50,000+ concurrent connections, running `netstat` can freeze the server or cause latency spikes!
Why?
- `netstat` reads `/proc/net/tcp` and `/proc/net/tcp6`.
- `/proc/net/tcp` is an ASCII-formatted pseudo-file generated on the fly.
- When `/proc/net/tcp` is read, the Linux kernel must acquire global socket locks (`tcp_hashinfo.lhash2`), format tens of thousands of binary kernel socket descriptors into human-readable text strings, and copy them across the user-kernel boundary page by page!
- In contrast, modern **`ss` (Socket Statistics)** uses the **`inet_diag` Netlink kernel subsystem**.
- `inet_diag` dumps raw binary socket structures directly into user space memory buffers without text formatting, and allows kernel-side filtering!

```
+-------------------------------------------------------------------------+
| TELEMETRY ARCHITECTURE: NETSTAT VS SS                                   |
|                                                                         |
| [netstat]                                      [ss]                     |
|    |                                            |                       |
|  open("/proc/net/tcp")                 socket(AF_NETLINK, NETLINK_INET_DIAG)
|    |                                            |                       |
|  Kernel locks socket hash table       Kernel streams raw binary structs |
|  Formats 50,000 text lines            Kernel filters by state/port      |
|  Copies text strings to user-space    Zero formatting in kernel space   |
|  SLOW: 2,500ms on busy servers        FAST: 15ms on busy servers        |
|    v                                            v                       |
+-------------------------------------------------------------------------+
```

---

## 2. Kernel Data Structures: `inet_diag_msg`
The `inet_diag` subsystem delivers socket metadata in compact binary structures (`linux/inet_diag.h`):

```c
struct inet_diag_msg {
    __u8    idiag_family;     /* AF_INET or AF_INET6 */
    __u8    idiag_state;      /* TCP state: TCP_ESTABLISHED, TCP_LISTEN, etc. */
    __u8    idiag_timer;      /* Active timer: 0=none, 1=retransmit, 2=keepalive */
    __u8    idiag_retrans;    /* Number of unacknowledged retransmissions */
    struct inet_diag_sockid id; /* 5-Tuple: sport, dport, src IP, dst IP, cookie */
    __u32   idiag_expires;    /* Remaining timer duration in jiffies */
    __u32   idiag_rqueue;     /* Receive queue byte length (backlog) */
    __u32   idiag_wqueue;     /* Send queue byte length (unacked bytes) */
    __u32   idiag_uid;        /* Owning user ID */
    __u32   idiag_inode;      /* Socket inode number */
};
```

---

## 3. Essential Command Patterns: `ss` Masterclass

### Basic Diagnostic Queries
```bash
# List all TCP listening sockets with process names and PIDs
ss -tulpn

# List all ESTABLISHED TCP connections
ss -t -a state established

# List all sockets in TIME-WAIT state
ss -t state time-wait

# Summary statistics of all socket types (TCP, UDP, RAW, UNIX sockets)
ss -s
```

### Advanced Filtering Syntax (Kernel-Side Evaluation)
```bash
# Find all connections connected to port 443 (HTTPS)
ss -t '( dport = :443 or sport = :443 )'

# Find all connections from a specific subnet
ss -t dst 192.168.1.0/24

# Filter sockets with send buffer queue > 0 (identifies blocked senders!)
ss -t -i 'wqueue > 0'

# Display internal TCP metrics: RTT, cwnd, ssthresh, pacing rate!
ss -t -i
```

---

## 4. Understanding Send/Receive Queues in `ss`
In `ss -l` (Listening sockets) vs `ss` (Established sockets), the `Recv-Q` and `Send-Q` columns mean completely different things!

| Mode | `Recv-Q` Column Meaning | `Send-Q` Column Meaning |
| :--- | :--- | :--- |
| **Listening (`ss -l`)** | Current pending connections in `accept()` backlog queue | Maximum backlog capacity (limit set by `listen(fd, backlog)`) |
| **Established (`ss`)** | Bytes received in kernel socket buffer, **not yet read** by application | Bytes sent into kernel socket buffer, **not yet acknowledged** by remote |

> **Critical Production Metric**: If `Recv-Q > Send-Q` on a listening socket, the application is overloaded and dropping incoming connections (SYN backlog overflow)!

---

## 5. Compilable C Program: Inspecting Socket States via `inet_diag` Netlink
```c
/*
 * inet_diag_socket_query.c - Queries TCP sockets via kernel NETLINK_INET_DIAG
 * Compile: gcc -O2 -Wall inet_diag_socket_query.c -o inet_diag_socket_query
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <linux/inet_diag.h>
#include <arpa/inet.h>

#define BUF_SIZE 8192

const char *tcp_state_to_str(int state) {
    switch (state) {
        case 1: return "ESTABLISHED";
        case 2: return "SYN_SENT";
        case 3: return "SYN_RECV";
        case 10: return "LISTEN";
        case 6: return "TIME_WAIT";
        case 7: return "CLOSE";
        default: return "OTHER";
    }
}

int main(void) {
    int fd = socket(AF_NETLINK, SOCK_RAW, NETLINK_INET_DIAG);
    if (fd < 0) {
        perror("socket(AF_NETLINK)");
        return 1;
    }

    struct {
        struct nlmsghdr nlh;
        struct inet_diag_req_v2 req;
    } request;

    memset(&request, 0, sizeof(request));
    request.nlh.nlmsg_len = sizeof(request);
    request.nlh.nlmsg_type = SOCK_DIAG_BY_FAMILY;
    request.nlh.nlmsg_flags = NLM_F_REQUEST | NLM_F_DUMP;

    request.req.sdiag_family = AF_INET;
    request.req.sdiag_protocol = IPPROTO_TCP;
    request.req.idiag_states = (1 << 1) | (1 << 10); /* ESTABLISHED and LISTEN */

    if (send(fd, &request, sizeof(request), 0) < 0) {
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
    printf("KERNEL INET_DIAG SOCKET TELEMETRY AUDIT\n");
    printf("=========================================\n");

    struct nlmsghdr *h = (struct nlmsghdr *)buf;
    while (NLMSG_OK(h, len)) {
        if (h->nlmsg_type == NLMSG_DONE) break;
        struct inet_diag_msg *msg = (struct inet_diag_msg *)NLMSG_DATA(h);

        char src_ip[INET_ADDRSTRLEN], dst_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, msg->id.idiag_src, src_ip, sizeof(src_ip));
        inet_ntop(AF_INET, msg->id.idiag_dst, dst_ip, sizeof(dst_ip));

        printf("State: %-12s | %s:%u -> %s:%u | Recv-Q: %u | Send-Q: %u\n",
               tcp_state_to_str(msg->idiag_state),
               src_ip, ntohs(msg->id.idiag_sport),
               dst_ip, ntohs(msg->id.idiag_dport),
               msg->idiag_rqueue, msg->idiag_wqueue);

        h = NLMSG_NEXT(h, len);
    }

    close(fd);
    return 0;
}
```

---

## 6. Production War Story: The Frozen Node and the 120,000 Connection `netstat` Crash
In 2017, a payment processing proxy server experienced an unexplainable 3-second latency freeze every minute.
Prometheus monitoring showed CPU usage spiking to 100% on CPU core 0, coinciding exactly with a monitoring cron job:
`netstat -s > /dev/null`
The server maintained 120,000 concurrent persistent TCP connections. Every minute, `netstat` opened `/proc/net/tcp`, which forced the kernel to serialize 120,000 socket descriptors into a 25 MB text document. The kernel lock blocked socket accept calls, causing thousands of payments to time out.
Replacing the cron job with `ss -s` reduced execution time from **3,400ms down to 1.8ms**, completely eliminating the CPU spikes and customer timeouts.

---

## 7. Verification Checklist & Command Reference
- [ ] Run `ss -s` to view global socket allocation summary.
- [ ] Monitor `ss -ltnp` to verify application listen backlog limits (`Send-Q`).
- [ ] Use `ss -ti` to inspect real-time TCP round-trip latency (`rtt`) and congestion window (`cwnd`) for any live socket.
---

## 8. Deep Systems Internals: TCP Socket Buffer Tuning via `ss -i`
When you run `ss -t -i`, modern Linux dumps internal TCP socket variables directly from `struct tcp_sock`:
- **`rto`**: Retransmission Timeout in milliseconds (Jacobson's timer).
- **`rtt`**: Smoothed Round-Trip Time (`SRTT`) and variance (`rttvar`).
- **`cwnd`**: Current Congestion Window in Maximum Segment Size (MSS) units.
- **`ssthresh`**: Slow Start Threshold boundary.
- **`bytes_acked`**: Total payload bytes acknowledged by remote peer over the connection lifespan.
- **`pacing_rate`**: Kernel Fair-Queueing (FQ) rate limiter bandwidth in bytes per second.
Understanding these metrics enables systems engineers to diagnose whether throughput bottlenecks stem from application processing latency, TCP window exhaustion, or physical packet drops.
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `ss -ltn` shows non-zero `Recv-Q` matching `Send-Q`**:
   - Root Cause: The application listening socket backlog is completely saturated! The application thread is stuck or blocked, failing to call `accept()` in time. Incoming TCP `SYN` packets are being dropped by the kernel.
   - Fix: Inspect application event loop latency and increase system-wide backlog limit: `sysctl -w net.core.somaxconn=4096`.
2. **Symptom: Thousands of sockets stuck in `TIME-WAIT`**:
   - Normal TCP behavior for connection termination (waiting 2MSL = 60s).
   - If ephemeral port exhaustion occurs (`bind: Cannot assign requested address`), enable socket reuse: `sysctl -w net.ipv4.tcp_tw_reuse=1`.
3. **Symptom: Sockets stuck in `CLOSE-WAIT`**:
   - Root Cause: Remote client sent `FIN` (closed connection), but local application forgot to call `close(fd)`! This is an application-level file descriptor leak.
---

## 10. Advanced Security Auditing: TCP SYN Backlog Hardening
To protect high-throughput network services against TCP SYN floods and backlog saturation:
```bash
# Expand the maximum number of remembered connection requests waiting for ACK
sysctl -w net.ipv4.tcp_max_syn_backlog=8192

# Enable stateless cryptographic SYN Cookies when backlog queue overflows
sysctl -w net.ipv4.tcp_syncookies=1

# Expand listen backlog queue capacity
sysctl -w net.core.somaxconn=4096

# Accelerate TCP FIN timeout to quickly reclaim memory from dying connections
sysctl -w net.ipv4.tcp_fin_timeout=15
```
