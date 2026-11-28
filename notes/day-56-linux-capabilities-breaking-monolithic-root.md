# Day 56: Linux Capabilities: Deconstructing the Monolithic Superuser and Scoped Privilege Models

The traditional UNIX security paradigm enforced an uncompromising binary: a process either possesses UID 0 (root) with unconstrained administrative mastery, or an unprivileged UID subject to strict DAC limits. This all-or-nothing model created massive attack surfaces: to perform a trivial privileged action (such as binding port 80 or setting system time), a binary required the full SUID-root bit, leaving the entire system vulnerable to privilege escalation. Linux Capabilities (POSIX 1003.1e draft) decompose the monolithic root privilege into approximately 41 granular, independent bit flags.

---

## 1. Kernel Representation & The Five Capability Sets

In the Linux kernel, process credentials (`struct cred`) track capabilities across five distinct 64-bit bitmasks (defined in `include/linux/capability.h` and `<sys/capability.h>`):

```c
/* Kernel capability definition */
typedef struct kernel_cap_struct {
    __u32 cap[_KERNEL_CAPABILITY_U32S]; /* 64 bits total on modern Linux */
} kernel_cap_t;

struct cred {
    /* ... */
    kernel_cap_t cap_inheritable; /* Inherited across execve() if allowed by file */
    kernel_cap_t cap_permitted;   /* Hard upper-bound limiting what can be adopted */
    kernel_cap_t cap_effective;   /* Currently active for kernel permission checks */
    kernel_cap_t cap_bset;        /* Bounding set: absolute system-wide ceiling */
    kernel_cap_t cap_ambient;     /* Ambient set: preserved across unprivileged execve */
    /* ... */
};
```

### The Roles of the Five Sets
1. **Effective ($P_E$)**: The bitmask checked directly by kernel functions (e.g., `capable(CAP_NET_BIND_SERVICE)`).
2. **Permitted ($P_P$)**: The limiting superset of capabilities that the process may transition into its Effective set using `cap_set_proc()`.
3. **Inheritable ($P_I$)**: Capabilities preserved across an `execve()` when matched by the file's inheritable set ($F_I$).
4. **Bounding ($P_B$)**: A security ceiling that restricts capabilities across all subsequent `execve()` calls. Capabilities dropped from $P_B$ cannot be reacquired even by root.
5. **Ambient ($P_A$)**: Introduced in Linux 4.3 to allow unprivileged processes to execute unprivileged child binaries with preserved capabilities without needing file capabilities or SUID bits.

---

## 2. Mathematical Capability Transformation Formulas Across `execve()`

When a process executes `execve(filename, argv, envp)`, the kernel computes the new process capabilities ($P_P', P_E', P_I', P_A'$) based on the caller's credentials and the target binary's VFS extended attributes (`security.capability`).

### The Formal POSIX / Linux Transformation Equations
Let $F_P$ and $F_I$ be the File Permitted and File Inheritable sets. Let $F_E$ be the File Effective single-bit flag:

$$P_P' = \left( P_A \right) \cup \left( P_B \cap F_P \right) \cup \left( P_I \cap F_I \right)$$

$$P_E' = \begin{cases}
P_P' & \text{if } F_E == 1 \\
P_A & \text{if } F_E == 0
\end{cases}$$

$$P_I' = P_I$$

$$P_A' = \begin{cases}
P_A & \text{if } F_P == 0 \land F_I == 0 \\
\emptyset & \text{if file has capabilities or SUID/SGID set}
\end{cases}$$

Notice that if a binary lacks file capabilities ($F_P = 0, F_I = 0, F_E = 0$), the new process retains exactly the Ambient capabilities $P_A$:
$$P_P' = P_A, \quad P_E' = P_A$$

---

## 3. High-Value Capabilities Catalog

| Capability | Bit | Permitted System Actions | Attack Vector if Compromised |
| :--- | :---: | :--- | :--- |
| **`CAP_NET_BIND_SERVICE`** | 10 | Bind sockets to ports $< 1024$ (e.g. 80, 443, 53) | Low (port hijacking / spoofing) |
| **`CAP_NET_RAW`** | 13 | Open `SOCK_RAW` sockets, ICMP ping, sniffing | Layer 2/3 packet forgery, ARP spoofing |
| **`CAP_SYS_ADMIN`** | 21 | Mount/unmount filesystems, eBPF, namespaces | **Instant Root** (equivalent to full root) |
| **`CAP_SYS_PTRACE`** | 19 | Trace arbitrary processes via `ptrace()` | Code injection into elevated processes |
| **`CAP_DAC_OVERRIDE`** | 1 | Bypass all DAC file read, write, execute checks | Overwrite `/etc/shadow` or `/etc/sudoers` |
| **`CAP_SETUID`** | 7 | Arbitrarily manipulate process UIDs | Elevate $EUID$ directly to 0 |

---

## 4. Compilable C Implementation: Dropping Privileges & Retaining Scoped Capabilities

The following C program demonstrates how an unprivileged network daemon can drop root identity while retaining only `CAP_NET_BIND_SERVICE` using `libcap`.

Compile with: `gcc -O2 -Wall -Wextra scoped_daemon.c -o scoped_daemon -lcap`

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/prctl.h>
#include <sys/capability.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <errno.h>

int drop_root_keep_bind(uid_t target_uid, gid_t target_gid) {
    /* Step 1: Tell kernel to preserve permitted capabilities across UID change */
    if (prctl(PR_SET_KEEPCAPS, 1, 0, 0, 0) < 0) {
        perror("prctl(PR_SET_KEEPCAPS)");
        return -1;
    }

    /* Step 2: Drop GID and UID */
    if (setgid(target_gid) != 0 || setuid(target_uid) != 0) {
        perror("setgid/setuid failed");
        return -1;
    }

    /* Step 3: Re-enable CAP_NET_BIND_SERVICE in the Effective set */
    cap_t caps = cap_init();
    cap_value_t cap_list[1] = { CAP_NET_BIND_SERVICE };

    /* Set CAP_NET_BIND_SERVICE in Permitted and Effective sets */
    cap_set_flag(caps, CAP_PERMITTED, 1, cap_list, CAP_SET);
    cap_set_flag(caps, CAP_EFFECTIVE, 1, cap_list, CAP_SET);

    if (cap_set_proc(caps) < 0) {
        perror("cap_set_proc failed");
        cap_free(caps);
        return -1;
    }

    cap_free(caps);
    return 0;
}

int main(void) {
    if (getuid() != 0) {
        fprintf(stderr, "Must run as root initially to configure capabilities.\n");
        return EXIT_FAILURE;
    }

    printf("Initial Process: UID=%d, EUID=%d\n", getuid(), geteuid());

    /* Drop root to 'nobody' (UID 65534) while keeping port bind authority */
    if (drop_root_keep_bind(65534, 65534) != 0) {
        return EXIT_FAILURE;
    }

    printf("Privileges dropped! Current UID=%d, EUID=%d\n", getuid(), geteuid());

    /* Test: Bind privileged port 80 as unprivileged user */
    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(80);
    addr.sin_addr.s_addr = INADDR_ANY;

    if (bind(sockfd, (struct sockaddr *)&addr, sizeof(addr)) == 0) {
        printf("SUCCESS: Bound privileged port 80 as unprivileged UID %d via CAP_NET_BIND_SERVICE!\n", getuid());
        close(sockfd);
        return EXIT_SUCCESS;
    } else {
        perror("Bind to port 80 failed");
        close(sockfd);
        return EXIT_FAILURE;
    }
}
```

---

## 5. File Capabilities (`setcap`, `getcap`) & Container Isolation

Instead of relying on runtime `prctl()` calls, binaries can store static capability bitmasks in their filesystem extended attributes (`xattrs` under `security.capability`).

```bash
# Set CAP_NET_RAW on ping to eliminate SUID root requirement
setcap cap_net_raw+ep /usr/bin/ping

# Inspect assigned file capabilities
getcap /usr/bin/ping
# Output: /usr/bin/ping cap_net_raw=ep
```

### Container Hardening via Bounding Set Pruning
Docker and Kubernetes isolate microservices by stripping dangerous capabilities from the bounding set $P_B$ prior to container launch:
```yaml
securityContext:
  capabilities:
    drop:
      - ALL
    add:
      - NET_BIND_SERVICE
```
Even if an attacker breaches the container and attains UID 0 inside the container namespace, the absence of `CAP_SYS_ADMIN`, `CAP_DAC_OVERRIDE`, and `CAP_SYS_PTRACE` makes breakout into the host operating system mathematically impossible.

---

## 6. Production Post-Mortem: The Overly Permissive CAP_SYS_ADMIN Container Escape

### Incident Overview
A financial institutions data-processing pipeline container was provisioned with `--cap-add=SYS_ADMIN` because the legacy application required mounting a temporary ramdisk (`tmpfs`).

A vulnerability (Remote Code Execution) was discovered in the applications exposed web service:
1. **Container Compromise**: The attacker attained an unprivileged shell inside the container namespace.
2. **Accessing Host Devices**: Because `CAP_SYS_ADMIN` was present in $P_E$, the attacker had access to kernel `cgroup` v1 notification hooks (`release_agent`).
3. **Triggering Host Execution**: The attacker mounted a custom cgroup hierarchy, wrote a host-executable bash script to `/cmd`, configured `/cmd` as the `release_agent`, and triggered an empty cgroup task notification.
4. **Host Takeover**: The Linux host kernel executed `/cmd` with full host root authority outside all namespaces.

### Remediation
1. **Never Grant `CAP_SYS_ADMIN`**: Replace container-level mount requirements with host-mounted volumes pre-configured by Kubernetes.
2. **Read-Only Root Filesystems**: Enforce `readOnlyRootFilesystem: true` to prevent dropping and executing payload scripts.
---

## 7. Ambient Capabilities (`PR_CAP_AMBIENT`) in Modern Systemd Services

Historically, launching an unprivileged daemon with capabilities required assigning file capabilities (`setcap`) or executing as root and dropping privileges in C. Systemd (v229+) introduced native Ambient capability assignment for service units:

```ini
[Unit]
Description=High-Performance Edge Proxy
After=network.target

[Service]
Type=simple
User=proxyuser
Group=proxyuser

# Retain only CAP_NET_BIND_SERVICE in Ambient set across execve()
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE

# Restrict privilege re-acquisition
NoNewPrivileges=true
ExecStart=/opt/proxy/bin/edge_proxy

[Install]
WantedBy=multi-user.target
```
When systemd invokes `execve()`, the `AmbientCapabilities` directive ensures that `proxyuser` retains `CAP_NET_BIND_SERVICE` without possessing any file capabilities or root privileges.
