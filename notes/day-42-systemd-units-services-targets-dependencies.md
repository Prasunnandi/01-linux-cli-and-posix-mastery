# Day 42: systemd Unit Architecture - Services, Targets, and Dependency Grammar

## 1. Unit Taxonomy and The Unified Object Model

systemd eliminates divergent configuration syntaxes by establishing an object-oriented abstraction called a **Unit**. Every managed system resource—from daemon processes and network sockets to disk mount points and memory limits—is represented as a declarative unit configuration file residing in `/usr/lib/systemd/system/` (system packages), `/run/systemd/system/` (runtime volatile), or `/etc/systemd/system/` (administrator overrides).

### The 11 Core Unit Types:
1. `.service`: Daemon process execution, restart policies, and environment containment.
2. `.target`: Synchronization points and grouping nodes in the dependency graph (replaces SysVinit runlevels).
3. `.socket`: Inter-process communication sockets (UNIX domain or TCP/UDP) for on-demand activation.
4. `.device`: Kernel hardware devices exposed via udev rules.
5. `.mount`: Filesystem mount point managed by `/etc/fstab` generator.
6. `.automount`: Filesystem mount points triggered dynamically upon directory access.
7. `.timer`: Monotonic or real-time calendar clocks replacing legacy cron jobs.
8. `.path`: Inotify-based file system path monitoring.
9. `.slice`: Hierarchical control group (cgroup) nodes managing memory, CPU, and I/O quotas.
10. `.scope`: Dynamically created processes organized under a cgroup (used by Docker/containerd).
11. `.swap`: Memory swap partition or swap file activation.

```
+--------------------------------------------------------------------------+
|                     systemd UNIT GRAMMAR HIERARCHY                       |
+--------------------------------------------------------------------------+
                                    |
      +-----------------------------+-----------------------------+
      |                             |                             |
      v                             v                             v
+------------------+      +------------------+      +------------------+
|  [Unit] Section  |      | [Service] Section|      | [Install] Section|
| - Description    |      | - Type=notify    |      | - WantedBy=      |
| - Requires=      |      | - ExecStart=     |      |   multi-user.    |
| - Wants=         |      | - Restart=always |      |   target         |
| - After=         |      | - MemoryMax=2G   |      | - RequiredBy=    |
| - Conflicts=     |      | - User=www-data  |      | - Alias=         |
+------------------+      +------------------+      +------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: systemd Unit State Machine

In systemd source code (`src/core/unit.h`), units are represented as massive C structs containing bitfields that govern dynamic transitions, dependency sets, and cgroup linkages.

```c
/* Real systemd Architecture excerpted from src/core/unit.h */
typedef enum UnitType {
    UNIT_SERVICE,
    UNIT_SOCKET,
    UNIT_TARGET,
    UNIT_DEVICE,
    UNIT_MOUNT,
    UNIT_AUTOMOUNT,
    UNIT_TIMER,
    UNIT_PATH,
    UNIT_SLICE,
    UNIT_SCOPE,
    UNIT_SWAP,
    _UNIT_TYPE_MAX,
    _UNIT_TYPE_INVALID = -EINVAL,
} UnitType;

typedef enum UnitDependency {
    UNIT_REQUIRES,
    UNIT_REQUISITE,
    UNIT_WANTS,
    UNIT_BINDS_TO,
    UNIT_PART_OF,
    UNIT_UPHOLDS,
    UNIT_REQUIRED_BY,
    UNIT_REQUISITE_OF,
    UNIT_WANTED_BY,
    UNIT_BOUND_BY,
    UNIT_UPHELD_BY,
    UNIT_CONFLICTS,
    UNIT_CONFLICTED_BY,
    UNIT_BEFORE,
    UNIT_AFTER,
    UNIT_ON_SUCCESS,
    UNIT_ON_FAILURE,
    UNIT_TRIGGERS,
    UNIT_TRIGGERED_BY,
    UNIT_PROPAGATES_RELOAD_TO,
    UNIT_RELOADED_BY,
    UNIT_PROPAGATES_STOP_TO,
    UNIT_STOPPED_BY,
    _UNIT_DEPENDENCY_MAX
} UnitDependency;

struct Unit {
    Manager                     *manager;
    UnitType                    type;
    UnitActiveState             current_active_state;
    UnitActiveState             deserialized_active_state;

    /* Unit name and aliases */
    char                        *id;
    Set                         *aliases;

    /* Binary bitfields for unit behavior */
    bool                        in_load_queue:1;
    bool                        in_dbus_queue:1;
    bool                        in_cleanup_queue:1;
    bool                        sent_dbus_new_signal:1;
    bool                        ignore_on_isolate:1;
    bool                        stop_when_bound_queue:1;
    bool                        refuse_manual_start:1;
    bool                        refuse_manual_stop:1;
    bool                        default_dependencies:1;

    /* Dependency Hash Maps: UnitDependency -> Hashmap of Units */
    Hashmap                     *dependencies[_UNIT_DEPENDENCY_MAX];

    /* Associated Linux CGroup Path */
    char                        *cgroup_path;
    CGroupMask                  cgroup_realized_mask;
};
```

---

## 3. Mathematical Foundations: Dependency Grammar Equivalence Classes

systemd decouples **Dependency Requirements** (whether unit $A$ needs unit $B$ running) from **Temporal Ordering** (which unit starts first). Confusing these two semantics is the primary cause of service failure in production.

### Requirement Relations:
Let $U$ be the universe of units.
1. **`Requires=`**: Strong functional dependency. If $(A, B) \in 	ext{Requires}$, then:
   $$	ext{Active}(A) \implies 	ext{Active}(B)$$
   If $B$ fails to activate or crashes, $A$ is automatically terminated.
2. **`Wants=`**: Weak opportunistic dependency:
   $$	ext{Start}(A) \implies 	ext{AttemptStart}(B)$$
   The failure of $B$ has zero effect on the health or startup of $A$.
3. **`BindsTo=`**: Hard physical binding:
   $$	ext{Active}(A) \iff 	ext{Active}(B)$$
   Used when service $A$ directly controls hardware device $B$ (e.g. WiFi daemon bound to `sys-subsystem-net-devices-wlan0.device`).
4. **`Conflicts=`**: Mutual exclusion:
   $$	ext{Active}(A) \implies 
eg 	ext{Active}(B)$$
   Starting $A$ triggers an automatic stop job for $B$.

### Temporal Ordering Relations:
1. **`After=`**: $B$ must complete its initialization before $A$ executes `ExecStart`:
   $$T_{	ext{Start}}(A) \ge T_{	ext{Ready}}(B)$$
2. **`Before=`**: $A$ must complete initialization before $B$ begins:
   $$T_{	ext{Start}}(B) \ge T_{	ext{Ready}}(A)$$

### The Formal Cycle Detection Theorem:
Let $G_{	ext{order}} = (V, E_{	ext{order}})$ where $E_{	ext{order}} = \{(u, v) \mid u 	ext{ After } v\}$.
systemd computes strongly connected components (SCCs) via Tarjan's algorithm. If any cycle $C \subseteq V$ exists:
$$\exists v_1, v_2, \dots, v_k \in V 	ext{ such that } (v_1, v_2), (v_2, v_3), \dots, (v_k, v_1) \in E_{	ext{order}}$$
systemd logs an error: `Ordering cycle found! Breaking ordering cycle by deleting job...` and arbitrarily prunes an edge, leading to non-deterministic boot behavior unless manually resolved.

---

## 4. Compilable C Implementation: sd_notify Protocol Implementation

The gold standard for production Linux daemons is `Type=notify`. Under this model, systemd marks a service as `Active (running)` only when the daemon explicitly transmits a readiness datagram across an isolated UNIX domain socket (`$NOTIFY_SOCKET`).

Save the following program as `notify_daemon.c`:

```c
/*
 * notify_daemon.c - Native implementation of the systemd sd_notify() protocol
 * Demonstrates:
 * 1. Resolving the volatile $NOTIFY_SOCKET environment variable
 * 2. Transmitting initialization state over UNIX domain datagram socket
 * 3. Heartbeat watchdog notifications (WATCHDOG=1)
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread notify_daemon.c -o notify_daemon
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <errno.h>

int send_systemd_notification(const char *state_message)
{
    const char *socket_path = getenv("NOTIFY_SOCKET");
    if (!socket_path) {
        /* Not running under systemd or Type=notify not configured */
        return 0;
    }

    int fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (fd < 0) {
        perror("socket AF_UNIX failed");
        return -1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;

    /* Handle abstract socket namespace if path begins with '@' */
    if (socket_path[0] == '@') {
        addr.sun_path[0] = ' ';
        strncpy(addr.sun_path + 1, socket_path + 1, sizeof(addr.sun_path) - 2);
    } else {
        strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);
    }

    ssize_t sent = sendto(fd, state_message, strlen(state_message), 0,
                          (struct sockaddr *)&addr, sizeof(addr));
    close(fd);

    return (sent >= 0) ? 1 : -1;
}

int main(void)
{
    printf("[DAEMON] Initializing worker buffers and opening database pools...\n");
    sleep(2); /* Simulate heavy internal initialization */

    /* Notify systemd that initialization is complete */
    if (send_systemd_notification("READY=1\nSTATUS=Serving client traffic on port 8080\n") > 0) {
        printf("[DAEMON] Emitted READY=1 datagram to systemd NOTIFY_SOCKET\n");
    } else {
        printf("[DAEMON] Running in standalone mode ($NOTIFY_SOCKET unset)\n");
    }

    /* Simulate periodic watchdog heartbeat */
    int ticks = 0;
    while (ticks < 3) {
        sleep(1);
        send_systemd_notification("WATCHDOG=1\n");
        printf("[DAEMON] Emitted WATCHDOG=1 heartbeat\n");
        ticks++;
    }

    printf("[DAEMON] Graceful shutdown initiation...\n");
    send_systemd_notification("STOPPING=1\n");
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The Wants= vs Requires= Database Outage

In 2019, a high-frequency financial metrics pipeline went down across an entire availability zone. The web API had been packaged with the following unit file:

```ini
[Unit]
Description=Metrics Web Gateway
Requires=postgresql.service
After=postgresql.service
```

During a routine security update, the PostgreSQL cluster was restarted. Because `Requires=` enforces a hard transitive dependency, the moment `postgresql.service` entered the `deactivating` state, systemd immediately issued a `SIGTERM` to `metrics-gateway.service`. 

Even worse, PostgreSQL took 45 seconds to perform a database recovery checkpoint. Because the metrics gateway had `Restart=on-failure` with a rate limit of 5 restarts in 30 seconds (`StartLimitBurst=5`), systemd flagged the gateway as failed (`systemd: Unit entered failed state`) and refused to start it even after PostgreSQL was fully operational.

**The Fix**:
1. Changed `Requires=` to `Wants=`: The web gateway was built with an internal connection pool that retried database connections automatically. Dropping `Requires=` allowed the gateway to stay online, queue incoming telemetry in RAM, and reconnect smoothly once the database finished restarting.
2. Adjusted `StartLimitIntervalSec=0` and configured `RestartSec=5s` to prevent systemd's restart throttling during legitimate downstream failovers.

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Deep Technical Purpose |
| :--- | :--- | :--- |
| `systemctl cat <unit>` | View Definition | Displays merged unit file including all drop-in override `.d/*.conf` snippets. |
| `systemctl list-dependencies <unit>` | Dependency Tree | Recursively renders the `Requires=`, `Wants=`, and `After=` dependency tree. |
| `systemctl show <unit> -p ActiveState,SubState` | Precise Telemetry | Inspects exact internal enum values directly from the C data structure. |
| `systemctl edit <unit>` | Drop-in Override | Opens `/etc/systemd/system/<unit>.d/override.conf` without modifying package defaults. |
| `systemctl daemon-reload` | Re-index DAG | Re-reads all unit files from disk and reconstructs the in-memory dependency graph. |
