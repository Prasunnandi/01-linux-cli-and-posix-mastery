# Day 39: SSH Tunneling: Local, Remote & Dynamic SOCKS5

## 1. Architectural Foundations: Encrypted TCP Multiplexing
SSH is not just an interactive remote shell; it is a full-featured, encrypted transport multiplexer (RFC 4254).
An established SSH connection runs over a single TCP socket (port 22).
Inside this single encrypted TCP stream, SSH can multiplex dozens of independent virtual channels:
- Channel 0: Interactive pseudoterminal session (PTY)
- Channel 1: SFTP file transfer stream
- Channel 2: Local port forwarding tunnel
- Channel 3: SOCKS5 dynamic proxy request

```
+-------------------------------------------------------------------------+
| SSH TRANSPORT MULTIPLEXING (RFC 4254)                                   |
|                                                                         |
| Local Host                                           Remote SSH Server  |
|                                                                         |
| [Local Browser]                                                         |
|       | (Port 8080)                                                     |
|       v                                                                 |
| +---------------------------------------------------------------------+ |
| |                    ENCRYPTED SSH TUNNEL (TCP/22)                    | |
| |                                                                     | |
| | [Channel 0: Bash Shell PTY] ======================================> | |
| | [Channel 1: Local Port Forward 8080] ====> TCP connect() to Target  | |
| | [Channel 2: Dynamic SOCKS5 Proxy] =======> Arbitrary Outbound Conns | |
| +---------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
```

---

## 2. The Three Tunnel Archetypes: `-L`, `-R`, and `-D`

### 1. Local Port Forwarding (`ssh -L`)
Forward traffic from your **local machine** through the SSH server to a **remote destination**.
- **Syntax**: `ssh -L [local_ip:]local_port:target_host:target_port user@ssh_server`
- **Use Case**: Accessing a private internal database (e.g. RDS or Redis) that is only accessible from inside the private VPC.

```bash
# Forward local port 5432 to private database 10.0.1.50:5432 via bastion host
ssh -N -L 5432:10.0.1.50:5432 ubuntu@bastion.corp.internal

# Now connect your local psql client directly:
psql -h 127.0.0.1 -p 5432 -U app_user production_db
```

### 2. Remote (Reverse) Port Forwarding (`ssh -R`)
Forward traffic from a port on the **remote SSH server** back to your **local machine**.
- **Syntax**: `ssh -R [remote_ip:]remote_port:local_host:local_port user@ssh_server`
- **Use Case**: Exposing a development web server running on your laptop (`localhost:3000`) to a public server so a client or webhook (e.g. Stripe webhook) can reach it.

```bash
# Remote public server listens on port 8080 and forwards all traffic back to your laptop port 3000
ssh -N -R 8080:localhost:3000 ubuntu@public-server.com
```
*(Note: Requires `GatewayPorts yes` in `/etc/ssh/sshd_config` on the remote server to bind to non-loopback interfaces).*

### 3. Dynamic Port Forwarding & SOCKS5 (`ssh -D`)
Instead of binding to a single static destination host and port, SSH turns your local machine into a full **SOCKS5 Application Proxy** (RFC 1928).
- **Syntax**: `ssh -D local_port user@ssh_server`
- **Use Case**: Routing your entire browser or CLI traffic through a remote server in another region or country.

```bash
# Open a SOCKS5 proxy on local port 1080
ssh -N -D 1080 ubuntu@remote-ec2-node

# Direct curl or Chrome through the encrypted proxy:
curl --socks5-hostname 127.0.0.1:1080 api.internal.service/ip
```

---

## 3. Production CLI Flags for Daemonized Tunnels
When creating SSH tunnels in production or automation scripts, always pass these four flags:
- **`-N`**: Do not execute a remote command or open a shell. (Tunnels only).
- **`-f`**: Fork into the background immediately before command execution.
- **`-q`**: Quiet mode (suppress non-error messages).
- **`-C`**: Enable on-the-fly stream compression (reduces bandwidth on slow links).

```bash
ssh -f -N -C -L 6379:redis.internal:6379 user@bastion.corp.internal
```

---

## 4. Compilable C Program: SOCKS5 Protocol Client Handshake (RFC 1928)
```c
/*
 * socks5_handshake_demo.c - Implements RFC 1928 SOCKS5 client authentication handshake
 * Compile: gcc -O2 -Wall socks5_handshake_demo.c -o socks5_handshake_demo
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>

int main(void) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_in proxy_addr;
    memset(&proxy_addr, 0, sizeof(proxy_addr));
    proxy_addr.sin_family = AF_INET;
    proxy_addr.sin_port = htons(1080); /* Standard SOCKS5 port */
    inet_pton(AF_INET, "127.0.0.1", &proxy_addr.sin_addr);

    printf("Connecting to local SOCKS5 proxy at 127.0.0.1:1080...\n");
    if (connect(sock, (struct sockaddr *)&proxy_addr, sizeof(proxy_addr)) < 0) {
        perror("connect (Ensure 'ssh -D 1080' is running!)");
        close(sock);
        return 1;
    }

    /*
     * RFC 1928 Client Method Negotiation:
     * Byte 0: SOCKS Version (0x05)
     * Byte 1: Number of Methods (0x01)
     * Byte 2: Method 0x00 (NO AUTHENTICATION REQUIRED)
     */
    unsigned char greeting[3] = { 0x05, 0x01, 0x00 };
    write(sock, greeting, 3);

    /* Server selects method */
    unsigned char resp[2];
    read(sock, resp, 2);

    printf("=========================================\n");
    printf("RFC 1928 SOCKS5 HANDSHAKE VERIFICATION\n");
    printf("=========================================\n");
    printf("SOCKS Version Returned : 0x%02X (Expected 0x05)\n", resp[0]);
    printf("Auth Method Selected   : 0x%02X (%s)\n",
           resp[1], (resp[1] == 0x00) ? "No Auth Required" : "Auth Required / Rejected");

    if (resp[0] == 0x05 && resp[1] == 0x00) {
        printf("Status: SOCKS5 tunnel is READY to accept TCP connection requests!\n");
    }
    printf("=========================================\n");

    close(sock);
    return 0;
}
```

---

## 5. Production War Story: The Database Port Forwarding Port Exhaustion
In 2020, an engineering team deployed an automated microservice integration test suite.
The test script spawned a new SSH tunnel before every test case:
`ssh -f -N -L 5432:db:5432 bastion &`
The test runner ran 1,200 tests in parallel.
Within 3 minutes, local developer workstations froze, throwing `bind: Address already in use` and `fork: Resource temporarily unavailable`.
Over 1,000 orphan background SSH processes were spawned, each holding open file descriptors and competing for local port 5432.
Fix: Never spawn ad-hoc background SSH tunnels inside loop scripts! Use **SSH Multiplexing (`ControlMaster`)** or a dedicated persistent connection pool.
---

## 8. Deep Systems Internals: SSH Port Forwarding Packet Multiplexing Trace
When you run `ssh -L 8080:target:80 user@server`:
1. The local SSH client opens a listening TCP socket on `127.0.0.1:8080`.
2. When a local browser connects to `8080`, the client accepts the socket and assigns an internal `Channel ID` (e.g. Channel 2).
3. The client sends an `SSH_MSG_CHANNEL_OPEN` packet of type `"direct-tcpip"` to the remote server over the encrypted SSH transport connection.
4. The remote SSH server receives the packet, invokes `connect()` to `target:80`, and replies with `SSH_MSG_CHANNEL_OPEN_CONFIRMATION`.
5. From then on, application payload bytes are packaged inside `SSH_MSG_CHANNEL_DATA` packets, encrypted with the session cipher (e.g. ChaCha20-Poly1305), and transferred across the single underlying TCP pipe!
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: Remote port forwarding `ssh -R 8080:...` only listens on `127.0.0.1`**:
   - Root Cause: OpenSSH server disables binding remote forwarding to public IP addresses by default for security.
   - Fix: Add `GatewayPorts yes` or `GatewayPorts clientspecified` to `/etc/ssh/sshd_config` on the remote server and restart sshd: `systemctl restart sshd`.
2. **Symptom: SOCKS5 proxy works for web browsing, but DNS leaks local IP**:
   - Root Cause: The client browser is performing DNS resolution locally before sending the request to SOCKS5.
   - Fix: Configure the browser or CLI to use **Remote DNS resolution** (in curl: `--socks5-hostname` instead of `--socks5`).
3. **Symptom: SSH tunnel dies silently after 10 minutes of inactivity**:
   - Root Cause: NAT firewalls and cloud load balancers drop idle TCP connections from their state tables.
   - Fix: Configure keepalives: `ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=3 ...`.
---

## 10. Advanced Security Auditing: Disabling SSH Tunnels on Bastion Hosts
If an enterprise security policy requires bastion hosts to act strictly as audit logging jump points and forbids developers from creating unauthorized TCP tunnels into the private network:
In `/etc/ssh/sshd_config`:
```ssh-config
# Disable all port forwarding tunnels
AllowTcpForwarding no
AllowStreamLocalForwarding no
GatewayPorts no
PermitTunnel no
X11Forwarding no
```
To permit tunneling only for specific authorized administrators:
```ssh-config
Match Group devops-admins
    AllowTcpForwarding yes
```
---

## 11. SSH Tunnel Security & Firewall Traversal Mechanics
Why do network firewalls often struggle to detect SSH tunnels?
1. To an external Layer-4 firewall or Deep Packet Inspection (DPI) appliance, an SSH tunnel appears as an ordinary, encrypted SSH-2.0 TLS/crypto session to port 22.
2. The inner payload packets (e.g. HTTP, PostgreSQL, Redis) are completely encapsulated and encrypted inside SSH transport layer frames (`SSH_MSG_CHANNEL_DATA`).
3. To defend against unauthorized egress tunnels, enterprise security teams use Next-Generation Firewalls (NGFW) with SSH decryption proxies, or restrict outbound port 22 connections using mutual-TLS egress gateways.
