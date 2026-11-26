# Day 40: ControlMaster & SSH Multiplexing at Scale

## 1. Architectural Foundations: The Cost of SSH Handshakes
Every time a client opens a brand-new SSH connection to a server:
1. **TCP 3-Way Handshake**: 1 full Round-Trip Time ($1 	imes 	ext{RTT}$).
2. **Protocol Version Exchange**: Client and server announce `SSH-2.0-OpenSSH_...`.
3. **Key Exchange (KEX)**: Diffie-Hellman / Curve25519 key generation ($1 	imes 	ext{RTT}$).
4. **Server Host Key Verification**: Client verifies host signature.
5. **Client Authentication**: Asymmetric signature verification of Ed25519 key ($1 	imes 	ext{RTT}$).
6. **Session & PTY Allocation**: Allocation of remote pseudoterminal ($1 	imes 	ext{RTT}$).

On a transatlantic connection with 80ms latency, establishing a single SSH connection takes **at least 350ms to 600ms** of network transit and CPU cryptographic work!
If you run configuration management tools (like **Ansible**) or high-frequency CI/CD deployments that execute 500 commands in sequence:
$$500 	ext{ commands} 	imes 500	ext{ms} = 250 	ext{ seconds (over 4 minutes of pure handshake overhead!)}$$

**OpenSSH ControlMaster (Multiplexing)** eliminates 100% of this overhead.
It establishes one master SSH connection, creates a local **UNIX Domain Socket**, and routes all subsequent SSH sessions over the **existing authenticated TCP connection** in less than 2 milliseconds!

```
+-------------------------------------------------------------------------+
| OPENSSH CONTROLMASTER ARCHITECTURE                                      |
|                                                                         |
| Local Workstation                                     Remote Server     |
| +-----------------------------------------------+                       |
| | First SSH Command:                             |                       |
| | Spawns Master Connection                      |                       |
| | Creates Socket: /tmp/ssh-ctrl-user@host:22    |                       |
| +-----------------------------------------------+                       |
|          |                                                              |
|          v (Full Handshake: 500ms)                                      |
|    ================== Established TCP Connection ==================     |
|                                                                         |
| +-----------------------------------------------+                       |
| | Subsequent SSH Commands (e.g. Ansible):       |                       |
| | Detects existing /tmp/ssh-ctrl-... socket!    |                       |
| | Passes commands directly over existing stream |                       |
| | ZERO HANDSHAKE DELAY! (Latency: ~2ms)         |                       |
| +-----------------------------------------------+                       |
+-------------------------------------------------------------------------+
```

---

## 2. Configuration Masterclass: `~/.ssh/config`
To enable multiplexing transparently for all SSH commands, Git, and Ansible, configure `~/.ssh/config`:

```ssh-config
Host *
    # Enable connection multiplexing
    ControlMaster auto

    # Path to the UNIX domain socket used for multiplexing
    ControlPath ~/.ssh/sockets/ctrl-%r@%h:%p

    # Keep master connection alive in background for 30 minutes after last session exits!
    ControlPersist 30m

    # Prevent connection drops
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

- **`ControlMaster auto`**: Checks if a master socket already exists. If yes, joins as a client; if no, becomes the master!
- **`ControlPath`**: Specifies socket location. `%r` = remote username, `%h` = remote hostname, `%p` = port.
- **`ControlPersist 30m`**: When the terminal closes, the master process stays alive as a daemon in the background for 30 minutes. The next command connects **instantly** without entering credentials!

---

## 3. Controlling and Managing the Master Socket CLI
```bash
# Check if a master connection is currently active for a host
ssh -O check prod-server

# Tell the master process to stop accepting new multiplexed sessions
ssh -O stop prod-server

# Forcefully terminate the master connection and close all multiplexed channels
ssh -O exit prod-server
```

---

## 4. Benchmarking the Acceleration: Cold vs Multiplexed
Let's measure the performance difference over a 50ms latency connection:

```bash
# Cold Execution (No multiplexing):
time for i in {1..10}; do ssh prod-server "echo ping" > /dev/null; done
# Output: real 0m5.842s

# Multiplexed Execution (With ControlMaster):
time for i in {1..10}; do ssh prod-server "echo ping" > /dev/null; done
# Output: real 0m0.184s  <--- 31x FASTER!
```

---

## 5. Compilable C Program: Detecting Active ControlMaster UNIX Sockets
```c
/*
 * control_socket_scanner.c - Scans ~/.ssh/sockets for active ControlMaster sockets
 * Compile: gcc -O2 -Wall control_socket_scanner.c -o control_socket_scanner
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <dirent.h>

int test_socket(const char *path) {
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return 0;

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);

    int active = (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) == 0);
    close(fd);
    return active;
}

int main(void) {
    const char *home = getenv("HOME");
    if (!home) home = ".";

    char socket_dir[512];
    snprintf(socket_dir, sizeof(socket_dir), "%s/.ssh/sockets", home);

    printf("=========================================\n");
    printf("OPENSSH CONTROLMASTER SOCKET AUDIT\n");
    printf("Directory: %s\n", socket_dir);
    printf("=========================================\n");

    DIR *d = opendir(socket_dir);
    if (!d) {
        printf("Directory does not exist. (No active multiplexed sessions).\n");
        return 0;
    }

    struct dirent *dir;
    int count = 0;
    while ((dir = readdir(d)) != NULL) {
        if (dir->d_name[0] == '.') continue;

        char full_path[1024];
        snprintf(full_path, sizeof(full_path), "%s/%s", socket_dir, dir->d_name);
        int is_live = test_socket(full_path);

        printf("Socket: %-30s | Status: %s\n",
               dir->d_name, is_live ? "LIVE (Active Master)" : "STALE (Dead Master)");
        count++;
    }
    closedir(d);

    if (count == 0) {
        printf("No active ControlMaster sockets found.\n");
    }
    printf("=========================================\n");
    return 0;
}
```

---

## 6. Production War Story: The Stale Control Socket Deadlock
In 2021, an automated continuous deployment pipeline began failing intermittently with:
`Control socket connect(/root/.ssh/sockets/ctrl-deploy@web01:22): Connection refused`
Investigation revealed:
1. The deployment runner host experienced an abrupt kernel panic and rebooted.
2. The socket file `/root/.ssh/sockets/ctrl-deploy@web01:22` persisted on disk in the root filesystem.
3. Upon reboot, the next SSH command saw the socket file on disk, assumed a master connection was already alive, and attempted to connect to it!
4. Because the owning process was dead, the connection was refused and all deployments failed!
Fix: In ephemeral CI/CD environments, place socket files in volatile RAM under `/dev/shm` or `/run/user/$UID/` (e.g. `ControlPath /run/user/%u/ssh-%C`), ensuring stale sockets are automatically wiped on reboot.
---

## 8. Deep Systems Internals: ControlPersist Daemonization Lifecycle
How does `ControlPersist 30m` work under the Linux process model?
1. When the initial user terminal session completes and exits, the master SSH process does not terminate.
2. It invokes `fork()` to detach from the controlling terminal (TTY), closes standard input/output, and becomes an independent session daemon in state `S` (Sleeping).
3. It arms an internal kernel timer (`timerfd_create` or `alarm`).
4. Every time a new client connects to the UNIX domain socket (`ControlPath`), the timer is reset back to 30 minutes.
5. If 30 continuous minutes elapse with zero active client connections, the master process cleanly sends an `SSH_MSG_DISCONNECT` to the remote server, deletes the socket file from `/tmp/ssh-*`, and exits.
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `ssh` fails with `ControlPath too long`**:
   - Root Cause: UNIX domain socket paths in Linux have a hard kernel limit of **108 characters** (`sizeof(struct sockaddr_un.sun_path)`). If `$HOME` has a long path, the expanded string overflows.
   - Fix: Use compact socket paths with hash representation: `ControlPath ~/.ssh/sockets/%C` (`%C` produces a compact 40-character SHA1 hash of host, user, and port).
2. **Symptom: Multiplexed sessions freeze simultaneously**:
   - Root Cause: All multiplexed sessions share the single underlying TCP pipe. If a network blip causes TCP retransmission timeout, all open windows stall together.
   - Fix: For interactive terminal work, use independent connections; reserve multiplexing for high-frequency CLI automation and file transfers.
3. **Symptom: Graceful termination of lingering background masters**:
   - Run `ssh -O exit <hostname>` to tell the master process to cleanly disconnect and remove its socket.
---

## 10. Advanced Security Auditing: Securing the ControlMaster Socket Directory
The UNIX domain socket created by `ControlMaster` allows **any process that can read and write to the socket to execute arbitrary remote commands as that user without entering a password**!
If a malicious user on a shared server gains access to your socket, they have full remote access.
Security rules:
1. Ensure the socket directory has strict permissions: `chmod 700 ~/.ssh/sockets`.
2. Never store ControlMaster sockets in shared world-writable directories like `/tmp` unless using isolated per-user private directories (`/run/user/$UID/`).
3. Set `ControlPersist` to a reasonable timeout (e.g. `10m` or `30m`), never `yes` (infinite).
---

## 11. Ansible Pipeline Acceleration with SSH ControlMaster
In modern DevOps automation with Ansible:
1. By default, Ansible opens a new SSH connection for every single task on every managed host.
2. A playbook with 30 tasks running across 50 servers generates $30 	imes 50 = 1,500$ separate SSH handshakes!
3. By enabling SSH pipelining and ControlMaster in `ansible.cfg`:
```ini
[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60m -o PreferredAuthentications=publickey
```
Execution times routinely drop from **15 minutes down to 45 seconds**, transforming enterprise infrastructure deployment speed.
