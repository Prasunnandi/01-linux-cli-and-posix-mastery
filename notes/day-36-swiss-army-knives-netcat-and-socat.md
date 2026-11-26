# Day 36: Swiss Army Knives: `netcat` (`nc`) & `socat`

## 1. Architectural Foundations: Bidirectional Byte-Stream Plumbing
In the UNIX philosophy, "Everything is a file" and programs read from `stdin` and write to `stdout`.
However, standard pipelines (`cmd1 | cmd2`) are unidirectional and confined to a single host's kernel memory.
**`netcat` (the TCP/IP swiss army knife)** and **`socat` (SOcket CAT)** bridge UNIX standard streams to network sockets.

They allow an engineer to:
1. Connect any shell pipeline directly to an arbitrary TCP, UDP, or UNIX domain socket.
2. Listen on arbitrary network ports and spawn shell scripts upon connection.
3. Bridge completely incompatible socket types (e.g. proxying a local UNIX domain socket `/var/run/docker.sock` over a remote encrypted TCP port).

```
+-------------------------------------------------------------------------+
| STREAM PLUMBING ARCHITECTURE: SOCAT DUAL-ENDED RELAY                    |
|                                                                         |
| Source Endpoint (Left)                       Destination Endpoint (Right)
| +---------------------+                     +-------------------------+ |
| | UNIX Domain Socket  | <=== socat core ===>| Remote TCP/TLS Socket   | |
| | /var/run/app.sock   |      poll()/epoll() | 192.168.1.50:8443       | |
| +---------------------+                     +-------------------------+ |
|            ^                                             ^              |
|            |                                             |              |
|       File Descriptor 3                             File Descriptor 4   |
+-------------------------------------------------------------------------+
```

---

## 2. Core Command Patterns: `netcat` (`nc`)
There are two primary implementations of netcat: GNU netcat and OpenBSD netcat (`nc -N`). The examples below use the ubiquitous OpenBSD netcat.

### Port Scanning & Service Probing
```bash
# Test if a TCP port is open with a 2-second timeout (-z: zero I/O, -w: timeout)
nc -zv 192.168.1.50 443

# Scan a range of ports (1 to 1024)
nc -zv 192.168.1.50 20-100

# Test UDP port reachability (-u)
nc -zvu 192.168.1.50 53
```

### Banner Grabbing & Raw Protocol Simulation
```bash
# Manually issue an HTTP/1.1 request
printf "GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n" | nc example.com 80

# Send a raw email via SMTP protocol interaction
nc mail.example.com 25
```

### High-Speed Streaming Backups (Tar over Netcat)
```bash
# On Receiver (Target Server: 192.168.1.100):
nc -l -p 9000 | tar -xzf - -C /destination/folder/

# On Sender (Source Server):
tar -czf - /source/data/ | nc 192.168.1.100 9000
```

---

## 3. The Power of `socat`: Multipurpose Relays
While `netcat` connects `stdin/stdout` to a socket, `socat` connects **two arbitrary endpoints (addresses)** together.
Syntax: `socat [options] <address1> <address2>`

### Exposing a Local UNIX Domain Socket over TCP
```bash
# Expose Docker daemon socket over local TCP port 2375
socat TCP-LISTEN:2375,fork,reuseaddr UNIX-CLIENT:/var/run/docker.sock
```

### Encrypted SSL/TLS Tunnel between Two Servers
```bash
# Server side (Listens on SSL port 4443, decrypts, and forwards to local port 8080):
socat OPENSSL-LISTEN:4443,cert=server.pem,verify=0,fork TCP:localhost:8080

# Client side (Connects via TLS and exposes local port 8000):
socat TCP-LISTEN:8000,fork OPENSSL:server.internal:4443,verify=0
```

### Serial Port / TTY to Network Proxy
```bash
# Expose a physical hardware serial device (/dev/ttyUSB0) over TCP port 7000
socat TCP-LISTEN:7000,fork,reuseaddr FILE:/dev/ttyUSB0,b115200,raw,echo=0
```

---

## 4. Deep Mechanics: The `socat` Epoll Loop
Under the hood, `socat` opens two file descriptors ($FD_A$ and $FD_B$) and runs a high-performance event loop using `select()`, `poll()`, or `epoll()`:
1. When $FD_A$ becomes readable, `socat` reads up to 8192 bytes into a buffer and executes `write()` to $FD_B$.
2. When $FD_B$ becomes readable, `socat` reads and writes to $FD_A$.
3. When one end encounters `EOF` or sends a `FIN` packet, `socat` calls `shutdown(FD, SHUT_WR)` to cleanly half-close the other end.

---

## 5. Compilable C Program: Mini-Netcat Stream Relay
```c
/*
 * mini_netcat.c - Minimal bidirectional TCP client and standard stream relay
 * Compile: gcc -O2 -Wall mini_netcat.c -o mini_netcat
 * Usage: ./mini_netcat <ip> <port>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <poll.h>

#define BUF_SIZE 4096

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <IPv4> <Port>\n", argv[0]);
        return 1;
    }

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(atoi(argv[2]));
    inet_pton(AF_INET, argv[1], &serv_addr.sin_addr);

    printf("Connecting to %s:%s...\n", argv[1], argv[2]);
    if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        perror("connect");
        close(sock);
        return 1;
    }
    printf("Connected! Relay active (stdin <-> socket). Press Ctrl+D to exit.\n");

    struct pollfd fds[2];
    fds[0].fd = STDIN_FILENO;
    fds[0].events = POLLIN;
    fds[1].fd = sock;
    fds[1].events = POLLIN;

    char buffer[BUF_SIZE];
    while (1) {
        int ret = poll(fds, 2, -1);
        if (ret < 0) break;

        /* stdin has data -> send to socket */
        if (fds[0].revents & POLLIN) {
            ssize_t bytes = read(STDIN_FILENO, buffer, sizeof(buffer));
            if (bytes <= 0) break;
            write(sock, buffer, bytes);
        }

        /* socket has data -> write to stdout */
        if (fds[1].revents & POLLIN) {
            ssize_t bytes = read(sock, buffer, sizeof(buffer));
            if (bytes <= 0) break;
            write(STDOUT_FILENO, buffer, bytes);
        }

        if ((fds[0].revents & (POLLERR | POLLHUP)) || (fds[1].revents & (POLLERR | POLLHUP))) {
            break;
        }
    }

    close(sock);
    return 0;
}
```

---

## 6. Production War Story: The Unauthenticated Socket Proxy Backdoor
In 2019, a junior developer wanted to inspect Docker containers on a remote testing server from their local Mac.
The developer ran on the remote host:
`socat TCP-LISTEN:2375,fork UNIX-CLIENT:/var/run/docker.sock &`
Because the developer omitted `bind=127.0.0.1`, `socat` bound to `0.0.0.0:2375`, exposing the unauthenticated Docker daemon control socket to the public internet!
Within 25 minutes, automated internet scanners detected the open Docker API port, submitted a container creation payload with root host mount (`-v /:/host`), scheduled a cryptocurrency miner cron job in `/host/etc/cron.d/`, and compromised the entire server fleet.
Rule of thumb: **Never expose internal sockets or loopback services with `socat` without explicitly binding to `127.0.0.1` or requiring mutual TLS (`OPENSSL-LISTEN`)**.
---

## 8. Deep Systems Internals: UNIX Domain Sockets vs TCP Loopback Latency
Why do high-performance microservices (e.g. Nginx to Gunicorn, or Docker CLI to dockerd) connect via UNIX domain sockets (`/var/run/app.sock`) rather than TCP loopback (`127.0.0.1:8080`)?
Let's analyze the kernel execution paths:
- **TCP Loopback (`127.0.0.1`)**:
  - Traverses the entire TCP/IP networking stack!
  - Computes IP headers, TCP headers, sequence numbers, flow control sliding windows, and checksums.
  - Generates ACK packets and passes through `iptables` / `nftables` connection tracking (`conntrack`).
- **UNIX Domain Socket (`AF_UNIX`)**:
  - Completely bypasses the networking stack!
  - Packets do not exist; data is copied directly between the sender and receiver's kernel memory page buffers via simple pointer synchronization.
  - **Latency**: UNIX domain sockets are **$2	imes 	ext{ to } 3	imes$ faster** and use half the CPU cycles of TCP loopback.
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `nc -zv` hangs indefinitely**:
   - Root Cause: A stateful firewall (e.g. AWS Security Group, iptables) is silently dropping packets (`DROP`) instead of rejecting them with `RST` or `ICMP Port Unreachable`.
   - Fix: Always pass `-w 2` (timeout 2 seconds) when scripting with netcat: `nc -w 2 -zv host port`.
2. **Symptom: `socat` terminates immediately after first connection closes**:
   - Root Cause: By default, `socat` handles a single connection and exits!
   - Fix: Always pass `,fork` option on listening endpoints (e.g. `TCP-LISTEN:8080,fork`) so socat spawns a child process for each incoming client while the parent keeps listening.
3. **Symptom: `socat` fails with `Address already in use`**:
   - Add `,reuseaddr` option to allow binding immediately even if sockets are lingering in `TIME-WAIT`.
---

## 10. Advanced Security Auditing: Restricted Shell Execution & Sandboxing
When using `netcat -e /bin/bash` or `socat EXEC:...`:
1. Traditional netcat compiled with `-DGAPING_SECURITY_HOLE` allows remote command execution without authentication.
2. In production systems, disable `netcat-traditional` and strictly enforce `netcat-openbsd`, which removes the `-e` flag entirely.
3. If remote execution is required, wrap commands inside `firejail` or Linux namespaces to restrict filesystem access and drop all capabilities.
---

## 11. Advanced Socat Address Types & Protocol Bridges
Beyond simple TCP and UDP sockets, `socat` supports over 40 distinct address types:
1. **`SYSTEM:<command>` / `EXEC:<command>`**: Spawns a shell or binary and pipes data to its stdin/stdout.
2. **`PTY`**: Generates a pseudoterminal pair.
3. **`GOPEN:<path>`**: Generic file open with arbitrary POSIX open flags (`O_RDWR`, `O_CREAT`).
4. **`TUN:<ip>/<netmask>`**: Allocates a Linux kernel TUN virtual network interface to build an impromptu point-to-point VPN tunnel over UDP in a single command line:
```bash
# Host A:
socat TUN:10.0.0.1/24,up UDP-LISTEN:5555

# Host B:
socat TUN:10.0.0.2/24,up UDP:host_a_ip:5555
```
