# Day 60: SELinux Internals: Type Enforcement, Security Contexts, Booleans, and the Access Vector Cache (AVC)

While AppArmor relies on pathname-based confinement, **Security-Enhanced Linux (SELinux)** implements label-based Mandatory Access Control (MAC) based on the Flask architecture. Originally engineered by the United States National Security Agency (NSA), SELinux binds cryptographically verified security labels directly to all kernel objects (inodes, processes, sockets, IPC, filesystems). Every interaction is evaluated against a mathematically proven Type Enforcement (TE) policy matrix and cached inside the Access Vector Cache (AVC).

---

## 1. Security Context Anatomy & Type Enforcement

Every process and file in an SELinux environment carries a standardized security context string adhering to the 4-tuple format:

```text
user : role : type : mls_level
  |      |      |         |
  |      |      |         +--> Multi-Level / Multi-Category Security (s0:c0,c1023)
  |      |      +------------> TYPE: Core primitive for Type Enforcement
  |      +-------------------> ROLE: Role-Based Access Control (RBAC) constraint
  +--------------------------> USER: SELinux identity (mapped to Linux UID)
```

### Deconstructing the Canonical Web Server Context
```text
system_u:system_r:httpd_t:s0
```
- `system_u`: System daemon identity.
- `system_r`: System service execution role.
- `httpd_t`: The **Domain/Type**. The kernel cares almost exclusively about this label.
- `s0`: Sensitivity level 0 with zero compartment categories.

### The Inode Security Context
Similarly, every file on an `ext4` or `xfs` filesystem stores its context within extended attributes (`security.selinux`):
```text
/var/www/html/index.html ---> system_u:object_r:httpd_sys_content_t:s0
```

---

## 2. The Type Enforcement Policy Rule Equation

SELinux enforces security through explicit whitelist rules written in policy language (CIL or TE):

```text
allow httpd_t httpd_sys_content_t : file { read getattr open };
```

### Formal Set-Theoretic Representation
Let $S$ be the Subject Domain (`httpd_t`).
Let $O$ be the Object Type (`httpd_sys_content_t`).
Let $C$ be the Object Class (`file`, `dir`, `tcp_socket`).
Let $P$ be the Requested Permission Bitmask (`read`, `write`, `execute`).

The Security Server computes authorization $A$:

$$A(S, O, C, P) = \begin{cases}
\text{ALLOW} & \text{if } P \subseteq \text{PolicyMatrix}[S, O, C] \\
\text{DENY} & \text{otherwise}
\end{cases}$$

Under SELinux, there is **no default allow**. If an explicit `allow` statement does not exist in the compiled binary policy matrix, the syscall is rejected.

---

## 3. The Access Vector Cache (AVC): High-Speed LRU Kernel Hash Engine

Consulting the full SELinux policy engine on every single syscall would introduce unacceptable performance degradation. To ensure line-rate execution, the kernel deploys the **Access Vector Cache (AVC)** (`security/selinux/avc.c`).

```text
Syscall: open() by httpd_t on httpd_sys_content_t
                     |
                     v
+-------------------------------------------------------------+
|                Access Vector Cache (AVC)                    |
|                                                             |
| Hash Key = Hash(Subject_SID ^ Object_SID ^ Object_Class)    |
|                                                             |
| [AVC Bucket Lookup: O(1)]                                   |
|   |                                                         |
|   +--> HIT: Return Cached Decision (ALLOW) in 5 nanoseconds |
|   |                                                         |
|   +--> MISS: Evict least recently used (LRU) node           |
|              Consult Security Server (Policy Matrix)        |
|              Populate AVC Bucket                            |
|              Return Decision                                |
+-------------------------------------------------------------+
```

### Kernel AVC Structure (`security/selinux/include/avc.h`)
```c
struct avc_entry {
    u32         ssid;           /* Source Security ID (Subject) */
    u32         tsid;           /* Target Security ID (Object) */
    u16         tclass;         /* Target Class (file, socket, etc.) */
    struct av_decision avd;     /* Cached permissions bitmask + audit flags */
};

struct avc_node {
    struct avc_entry    ae;
    struct hlist_node   list;
    struct rcu_head     rhead;
};
```

---

## 4. SELinux Booleans: Dynamic Kernel Policy Mutation

Recompiling an entire security policy to toggle a single operational behavior (such as allowing NGINX to connect to an external MySQL database) is impractical. SELinux **Booleans** provide 1-bit kernel switches that dynamically toggle policy branches without rebooting.

```bash
# Query status of network connection boolean
getsebool httpd_can_network_connect

# Atomically enable boolean persistently across reboots
setsebool -P httpd_can_network_connect on
```
In the kernel, setting a boolean flips an atomic bitmask in the policy engine and triggers an instant invalidation of affected AVC cache lines (`avc_ss_reset()`).

---

## 5. Compilable C Implementation: Querying Contexts via `libselinux`

Compile with: `gcc -O2 -Wall -Wextra selinux_query.c -o selinux_query -lselinux`

```c
#include <stdio.h>
#include <stdlib.h>
#include <selinux/selinux.h>
#include <selinux/context.h>

int main(int argc, char *argv[]) {
    if (argc != 2) {
        printf("Usage: %s <path_to_file>\n", argv[0]);
        return EXIT_FAILURE;
    }

    /* Check if SELinux is active */
    if (!is_selinux_enabled()) {
        printf("SELinux is NOT enabled on this host.\n");
        return EXIT_FAILURE;
    }

    int enforce = security_getenforce();
    printf("SELinux Mode: %s\n", enforce ? "ENFORCING" : "PERMISSIVE");

    /* Step 1: Query process context */
    char *proc_con = NULL;
    if (getcon(&proc_con) == 0) {
        printf("Current Process Context: %s\n", proc_con);
        freecon(proc_con);
    }

    /* Step 2: Query target file security context */
    char *file_con = NULL;
    if (getfilecon(argv[1], &file_con) > 0) {
        printf("File '%s' Context: %s\n", argv[1], file_con);

        /* Parse individual context elements */
        context_t c = context_new(file_con);
        if (c) {
            printf("  -> User: %s\n", context_user_get(c));
            printf("  -> Role: %s\n", context_role_get(c));
            printf("  -> Type: %s\n", context_type_get(c));
            printf("  -> MLS:  %s\n", context_range_get(c));
            context_free(c);
        }
        freecon(file_con);
    } else {
        perror("getfilecon failed");
    }

    return EXIT_SUCCESS;
}
```

---

## 6. Multi-Category Security (MCS) in Container Isolation

How do modern container runtimes (Docker, Podman, CRI-O) prevent container breakouts even when multiple containers run with the identical type `container_t`? They utilize **Multi-Category Security (MCS)**.

### Category Lattice Isolation
When a container starts, the container manager allocates two random categories between $c0$ and $c1023$:
- Container 1: `system_u:system_r:container_t:s0:c12,c34`
- Container 2: `system_u:system_r:container_t:s0:c56,c78`
- Volume 1: `system_u:object_r:container_file_t:s0:c12,c34`

Because the Bell-LaPadula mathematical dominance relation requires:
$$\text{Subject Categories} \supseteq \text{Object Categories}$$

Container 2 cannot read Volume 1 even if standard UNIX DAC permissions are `777`. The kernel rejects the access with an AVC denial.

---

## 7. Production Post-Mortem: The `setenforce 0` Anti-Pattern Outage

### Incident Overview
An engineer deploying a custom internal analytics service on an enterprise Red Hat Enterprise Linux cluster encountered `500 Internal Server Error` responses. Inspecting audit logs revealed SELinux AVC denials. Rather than identifying the correct file type or boolean, the engineer executed:
```bash
setenforce 0
```
This transitioned the entire production server into **Permissive** mode.

### The Breach
Three weeks later, an unauthenticated remote exploit targeted a vulnerable legacy logging library within the analytics service.
1. In Enforcing mode, the process domain `analytics_t` would have been restricted strictly to its `/opt/analytics` directory and denied access to `/etc/shadow`, `/root/.ssh`, and raw sockets.
2. In Permissive mode, SELinux merely logged violations without blocking syscalls.
3. The attacker read the host root SSH private keys, compromised the bastion gateway, and exfiltrated sensitive databases.

### Key Lesson
Never execute `setenforce 0` in production environments. Audit denials must be resolved surgically via:
1. Label restoration: `restorecon -Rv /target/directory`
2. Setting targeted booleans: `setsebool -P ... on`
3. Generating minimal custom policy modules via `audit2allow -M`.
---

## 8. SELinux Policy Compilation & Module Lifecycle

Modern SELinux policies (such as the Reference Policy or Fedora/RHEL targeted policy) follow a structured compilation pipeline from human-readable Type Enforcement (`.te`) source files into kernel-loadable binary policies:

```text
[Source .te File] ---> (checkmodule -M -m) ---> [Intermediate .mod Module]
                                                        |
                                                 (semodule_package)
                                                        v
                                             [Policy Package .pp]
                                                        |
                                                 (semodule -i)
                                                        v
                                             [Kernel Binary Policy:
                                              /etc/selinux/targeted/policy/policy.33]
```

### Writing a Minimal Policy Module
When an application requires legitimate access rejected by the targeted policy:
```text
module custom_nginx 1.0;

require {
    type httpd_t;
    type var_log_t;
    class file { read open getattr };
}

# Explicit rule grant
allow httpd_t var_log_t : file { read open getattr };
```
Compiling and installing this module introduces the exact required permission vector into the kernel AVC without compromising broader system confinement.
