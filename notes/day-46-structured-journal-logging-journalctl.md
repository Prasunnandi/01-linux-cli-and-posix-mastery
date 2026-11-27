# Day 46: Structured Journal Logging - systemd-journald Internals, Binary Format, and journalctl

## 1. Architectural Revolution: Moving Beyond Flat Text Logs

Traditional UNIX logging relied on `/dev/log`, an unauthenticated UNIX domain datagram socket read by syslog daemons (syslogd, rsyslog, syslog-ng). While simple, flat-text syslog architecture suffers from critical enterprise weaknesses:
1. **Unstructured & Untyped**: Log lines are freeform text strings (`printf` outputs). Extracting PID, UID, unit name, or error codes requires complex regex parsing at ingestion time.
2. **Easy to Forge**: Any unprivileged local process can connect to `/dev/log` and forge log lines pretending to originate from `sshd` or `kernel`.
3. **No Forward Integrity**: If an attacker gains root privileges, they can retroactively edit `/var/log/auth.log` with a text editor to erase all forensic evidence.
4. **Poor Query Performance**: Searching 50 GB of flat text logs across timestamps requires linear disk sweeps ($O(N)$ scanning with `grep`).

`systemd-journald` fundamentally redesigned Linux logging around **Structured Binary Append-Only Storage**. Every log entry is stored as a set of indexed key-value attributes (`MESSAGE=`, `_PID=`, `_UID=`, `_SYSTEMD_UNIT=`, `_COMM=`), validated by kernel-authenticated socket credentials (`SO_PEERCRED`), and indexed via hash tables and Forward Secure Sealing (FSS).

```
+--------------------------------------------------------------------------+
|                     systemd-journald INGESTION PIPELINE                  |
+--------------------------------------------------------------------------+
|  Sources:                                                                |
|  - /run/systemd/journal/socket (Native structured API via sd_journal_send)|
|  - /dev/log (Legacy RFC 3164/5424 syslog compatibility socket)           |
|  - /dev/kmsg (Linux kernel printk ring buffer)                           |
|  - Standard Output & Error of all managed service cgroups                |
+--------------------------------------------------------------------------+
                                    |
                                    v Kernel SO_PEERCRED Authentication
+--------------------------------------------------------------------------+
|                             systemd-journald                             |
|  - Interrogates kernel for immutable metadata:                           |
|    _PID, _UID, _GID, _CAP_EFFECTIVE, _COMM, _EXE, _CMDLINE, _AUDIT_SESSION|
|  - Deduplicates objects via hash tables (Entry Array & Data Objects)     |
|  - Forward Secure Sealing (FSS) cryptographic hashing                    |
+--------------------------------------------------------------------------+
                                    |
                                    v Memory-Mapped I/O (mmap)
+--------------------------------------------------------------------------+
|            /var/log/journal/<machine-id>/system.journal                  |
+--------------------------------------------------------------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: Journal Binary File Format

The systemd journal stores data on disk in a highly optimized binary format (`src/journal/journal-def.h`). Below are the real C structures representing the header and object containers:

```c
/* Real systemd Architecture excerpted from src/journal/journal-def.h */
#define HEADER_SIGNATURE "LPKSHHRH" /* 8-byte file magic number */

struct Header {
    uint8_t             signature[8];   /* Magic string LPKSHHRH */
    uint32_t            compatible_flags;
    uint32_t            incompatible_flags;
    uint8_t             state;          /* STATE_OFFLINE, STATE_ONLINE, STATE_ARCHIVED */
    uint8_t             reserved[7];
    sd_id128_t          file_id;        /* Unique 128-bit file UUID */
    sd_id128_t          machine_id;     /* Host 128-bit machine UUID */
    sd_id128_t          boot_id;        /* Current boot 128-bit UUID */
    sd_id128_t          seqnum_id;
    uint64_t            header_size;
    uint64_t            arena_size;
    uint64_t            data_hash_table_offset;
    uint64_t            data_hash_table_size;
    uint64_t            field_hash_table_offset;
    uint64_t            field_hash_table_size;
    uint64_t            tail_object_offset;
    uint64_t            n_objects;
    uint64_t            n_entries;
    uint64_t            seqnum;
} __attribute__((packed));

typedef enum ObjectType {
    OBJECT_UNUSED = 0,
    OBJECT_DATA,            /* Stores key-value payload: "MESSAGE=Hello" */
    OBJECT_FIELD,           /* Stores field names: "MESSAGE", "_PID" */
    OBJECT_ENTRY,           /* Array of offsets pointing to DATA objects */
    OBJECT_DATA_HASH_TABLE,
    OBJECT_FIELD_HASH_TABLE,
    OBJECT_ENTRY_ARRAY,     /* B-tree style indexing array for fast seeking */
    OBJECT_TAG,             /* FSS cryptographic validation tag */
    _OBJECT_TYPE_MAX
} ObjectType;

struct ObjectHeader {
    uint8_t             type;           /* ObjectType enum */
    uint8_t             flags;          /* Compression: 1=XZ, 2=LZ4, 4=ZSTD */
    uint8_t             reserved[6];
    uint64_t            size;           /* Total size of object payload */
    uint8_t             payload[];      /* Variable-length payload */
} __attribute__((packed));
```

---

## 3. Mathematical Foundations: Forward Secure Sealing (FSS)

To mathematically prove that logs have not been tampered with or truncated by an attacker who achieves root access, systemd-journald implements **Forward Secure Sealing (FSS)** based on the Bellare-Miner cryptographic signature scheme.

### Epoch Ratcheting:
Time is divided into discrete epochs $e \in \{0, 1, 2, \dots\}$. 
Let $K_0$ be the master private key generated during setup (`journalctl --setup-keys`), and let $\mathcal{H}$ be a cryptographically secure one-way hash function (HMAC-SHA256).

At the start of epoch $e$, the active signing key $K_e$ is derived deterministically from the previous key:
$$K_e = \mathcal{H}(K_{e-1})$$
Crucially, $K_{e-1}$ is **permanently and securely erased from memory and disk**. 

### The Security Invariant:
Because $\mathcal{H}$ is computationally infeasible to invert:
$$	ext{Given } K_e, \quad 	ext{computing } K_{e-k} 	ext{ requires solving pre-image resistance for } \mathcal{H}^k$$

When an attacker breaches the server at epoch $e_{	ext{breach}}$, they possess only $K_{e_{	ext{breach}}}$. They can tamper with future logs ($e \ge e_{	ext{breach}}$), but they mathematically **cannot forge valid signatures for past epochs** ($e < e_{	ext{breach}}$). 

During verification:
$$	ext{Tag}_e = \mathcal{H}\left(K_e \parallel 	ext{CumulativeHash}(	ext{Logs}_e)ight)$$
Any retroactive deletion or modification of prior log entries causes verification to fail with `Seal verification failed!`.

---

## 4. Compilable C Implementation: Native sd_journal_send Structured Logger

Save the following program as `journal_logger.c`:

```c
/*
 * journal_logger.c - Structured Journal Logging via Native UNIX Domain Socket
 * Demonstrates:
 * 1. Constructing structured key-value log attributes
 * 2. Transmitting across /run/systemd/journal/socket
 * 3. Kernel metadata enrichment and log levels
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread journal_logger.c -o journal_logger
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/uio.h>
#include <errno.h>

/* Emulates the core mechanics of systemd's sd_journal_sendv() */
int log_to_journal(const char *priority, const char *msg, const char *custom_key, const char *custom_val)
{
    int fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (fd < 0) {
        perror("socket AF_UNIX failed");
        return -1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, "/run/systemd/journal/socket", sizeof(addr.sun_path) - 1);

    /* Construct payload buffer with newline-delimited key=value pairs */
    char buf[2048];
    int len = snprintf(buf, sizeof(buf),
                       "PRIORITY=%s\n"
                       "MESSAGE=%s\n"
                       "CODE_FILE=%s\n"
                       "CODE_LINE=%d\n"
                       "%s=%s\n",
                       priority, msg, __FILE__, __LINE__, custom_key, custom_val);

    ssize_t sent = sendto(fd, buf, len, 0, (struct sockaddr *)&addr, sizeof(addr));
    close(fd);

    return (sent == len) ? 0 : -1;
}

int main(void)
{
    printf("====================================================\n");
    printf("STRUCTURED SYSTEMD JOURNAL LOGGING ENGINE\n");
    printf("====================================================\n");

    printf("[CLIENT] Emitting structured diagnostic events...\n");

    /* Send an INFO event (Priority 6) with custom transaction ID metadata */
    if (log_to_journal("6", "Order processing initiated successfully", "TX_ID", "TX-998214") == 0) {
        printf("  [PASS] Emitted INFO with TX_ID=TX-998214\n");
    } else {
        printf("  [NOTE] /run/systemd/journal/socket unavailable (non-systemd environment)\n");
    }

    /* Send an ALERT event (Priority 1) */
    if (log_to_journal("1", "Database pool exhaustion detected!", "POOL_LOAD", "100%") == 0) {
        printf("  [PASS] Emitted ALERT with POOL_LOAD=100%\n");
    }

    printf("[CLIENT] Verification complete.\n");
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The 80GB In-Memory /run/log/journal OOM Storm

In 2020, an e-commerce platform experienced sudden host crashes during Black Friday. The hosts were configured with default systemd settings where `/var/log/journal/` did not exist; consequently, systemd-journald defaulted to **volatile runtime logging** inside `/run/log/journal/`.

1. **The Architecture**: In Linux, `/run` is a virtual `tmpfs` RAM-backed filesystem.
2. **The Bug**: A legacy microservice had its debug logging enabled, outputting 45,000 JSON payloads per second.
3. **The Disaster**: By default, `RuntimeMaxUse=` defaults to 10% of physical RAM (up to 4 GB). However, an override had set `RuntimeMaxUse=80%`. Journald consumed 52 GB of physical memory storing volatile logs. 
4. **The Impact**: As free RAM vanished, the Linux kernel triggered the Out-Of-Memory (OOM) killer, which promptly terminated the main database engine and the Redis cluster.

**The Fix**:
1. Ensure persistent logging is enabled on non-volatile NVMe storage by creating `/var/log/journal`:
   ```bash
   mkdir -p /var/log/journal
   systemd-tmpfiles --create --prefix /var/log/journal
   ```
2. Configure hard quota ceilings in `/etc/systemd/journald.conf`:
   ```ini
   [Journal]
   Storage=persistent
   SystemMaxUse=10G
   SystemKeepFree=20G
   RateLimitIntervalSec=30s
   RateLimitBurst=10000
   ```

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Deep Technical Purpose |
| :--- | :--- | :--- |
| `journalctl -u <unit> -f` | Tail Service Logs | Follows structured events filtered by `_SYSTEMD_UNIT` cgroup matching. |
| `journalctl -p err..emerg` | Priority Filter | Filters events by RFC 5424 syslog severity levels (0=Emergency to 3=Error). |
| `journalctl -b -1` | Previous Boot | Queries logs strictly partitioned by the boot ID `_BOOT_ID` of the prior boot. |
| `journalctl --vacuum-size=2G` | Storage Pruning | Deletes oldest archived `.journal` chunks until total disk footprint is under 2GB. |
| `journalctl --verify` | FSS Audit | Cryptographically verifies all Forward Secure Sealing tags against corruption. |
