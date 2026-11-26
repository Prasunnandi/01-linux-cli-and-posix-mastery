# Day 38: Delta File Sync: `scp` vs `rsync`

## 1. Architectural Foundations: Full Copy vs Delta-Transfer
When copying files between two machines over a network, systems administrators historically used `scp` (Secure Copy Protocol).
However, `scp` suffers from a massive architectural limitation:
- `scp` is a "blind dumb copy". If you have a 10 GB database backup file and change 100 bytes inside it, `scp` retransmits the **entire 10 GB** over the wire!
- `scp` has no support for resuming interrupted transfers, no delta detection, and no native stream compression. (OpenSSH recently transitioned the `scp` command line to use the SFTP subsystem under the hood because the legacy SCP wire protocol had multiple security vulnerabilities).

In 1996, Andrew Tridgell and Paul Mackerras published the **rsync algorithm**.
`rsync` transfers **only the differences (deltas)** between local and remote files without requiring both machines to possess copies of each other's files beforehand!

```
+-------------------------------------------------------------------------+
| THE RSYNC ROLLING CHECKSUM DELTA-TRANSFER ALGORITHM                     |
|                                                                         |
| Receiver (Has Old File)                    Sender (Has New File)        |
| 1. Splits file into blocks B (e.g. 4KB)                                 |
| 2. Computes two checksums per block:                                    |
|    - Fast 32-bit Rolling Checksum (Adler-32)                            |
|    - Strong 128-bit Hash (MD5)                                          |
| 3. Sends list of (Adler32, MD5) pairs ---> Receives list of signatures |
|                                            4. Slides rolling window     |
|                                               byte-by-byte through file |
|                                            5. If block matches:         |
|                                               Emits MATCH (Block Index) |
|                                            6. If no match:              |
|                                               Emits RAW BYTE DELTA      |
|                                                                         |
| 7. Reconstructs identical new file <------ Receives Stream of Matches   |
|    from local blocks + raw deltas          and Raw Inserted Bytes       |
+-------------------------------------------------------------------------+
```

---

## 2. Mathematical Foundations: The Adler-32 Rolling Checksum
To find matching blocks at **arbitrary byte offsets** without recalculating hashes from scratch for every byte position, `rsync` uses a rolling checksum based on Mark Adler's Adler-32:

Let a block of bytes be $X_1, X_2, \dots, X_n$.
The checksum consists of two 16-bit sums:
$$A(k, l) = \left( \sum_{i=k}^{l} X_i 
ight) mod M$$
$$B(k, l) = \left( \sum_{i=k}^{l} (l - i + 1) X_i 
ight) mod M$$
where $M = 2^{16} = 65536$.
The 32-bit checksum is:
$$R(k, l) = A(k, l) + (B(k, l) \ll 16)$$

When sliding the window by 1 byte (dropping $X_k$ and adding $X_{l+1}$):
$$A(k+1, l+1) = (A(k, l) - X_k + X_{l+1}) mod M$$
$$B(k+1, l+1) = (B(k, l) - n X_k + A(k+1, l+1)) mod M$$

**Notice**: Computing the new checksum takes **$O(1)$ constant time**! It only requires a few integer additions and subtractions, enabling `rsync` to scan gigabytes of data per second at wire speed.

---

## 3. Essential Command Patterns: `rsync` Production Masterclass

### The Standard Production Backup Flags: `-avzP`
```bash
# -a: Archive mode (Preserves permissions, timestamps, symlinks, owner, group)
# -v: Verbose output
# -z: Compress file data during transfer (gzip stream)
# -P: Equivalent to --partial --progress (Resumes broken transfers + shows ETA)
rsync -avzP /source/data/ user@remote.corp:/destination/data/
```

### The Trailing Slash Trap (`dir` vs `dir/`)
A notorious trap for Linux engineers:
```bash
# WITHOUT trailing slash: Copies folder INTO destination -> /backup/data/
rsync -a /var/data /backup/

# WITH trailing slash: Copies CONTENTS of folder -> /backup/file1, /backup/file2
rsync -a /var/data/ /backup/
```

### Exact Mirroring with `--delete`
```bash
# Deletes files on destination that no longer exist in source (True synchronization!)
rsync -avzP --delete /var/www/html/ web-backup:/var/www/html/

# Dry run mode (Shows what WOULD be copied or deleted without modifying disk!)
rsync -avzP --delete --dry-run /var/www/html/ web-backup:/var/www/html/
```

### Bandwidth Limiting & Custom SSH Port
```bash
# Limit transfer speed to 5 MB/s to prevent choking office internet
rsync -avzP --bwlimit=5000 -e 'ssh -p 2222' /db/backup.sql backup-node:/db/
```

---

## 4. Compilable C Program: Adler-32 Rolling Checksum Engine
```c
/*
 * rolling_checksum_demo.c - Implements rsync-style O(1) rolling Adler-32
 * Compile: gcc -O2 -Wall rolling_checksum_demo.c -o rolling_checksum_demo
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#define MOD_ADLER 65536

typedef struct {
    uint16_t a;
    uint16_t b;
    size_t   len;
} rolling_adler_t;

rolling_adler_t calc_initial(const unsigned char *buf, size_t len) {
    uint32_t a = 0, b = 0;
    for (size_t i = 0; i < len; i++) {
        a = (a + buf[i]) % MOD_ADLER;
        b = (b + (len - i) * buf[i]) % MOD_ADLER;
    }
    rolling_adler_t r = { (uint16_t)a, (uint16_t)b, len };
    return r;
}

rolling_adler_t roll_byte(rolling_adler_t prev, unsigned char old_byte, unsigned char new_byte) {
    rolling_adler_t next;
    next.len = prev.len;
    next.a = (prev.a - old_byte + new_byte) % MOD_ADLER;
    next.b = (prev.b - (prev.len * old_byte) + next.a) % MOD_ADLER;
    return next;
}

int main(void) {
    const char *text = "HELLO_WORLD_RSYNC_DELTA_STREAMING_TEST!";
    size_t block_size = 8;

    printf("=========================================\n");
    printf("RSYNC O(1) ROLLING CHECKSUM DEMO\n");
    printf("=========================================\n");

    /* Initial 8-byte block: "HELLO_WO" */
    rolling_adler_t current = calc_initial((const unsigned char *)text, block_size);
    printf("Block 0 ('%.8s') -> a: %5u, b: %5u | Hash: 0x%08X\n",
           text, current.a, current.b, (current.b << 16) | current.a);

    /* Slide window byte-by-byte */
    for (size_t i = 0; i < 5; i++) {
        unsigned char old_b = text[i];
        unsigned char new_b = text[i + block_size];
        current = roll_byte(current, old_b, new_b);

        /* Verify against full recalculation */
        rolling_adler_t verified = calc_initial((const unsigned char *)(text + i + 1), block_size);
        printf("Slide %zu ('%.8s') -> Hash: 0x%08X (Match: %s)\n",
               i + 1, text + i + 1,
               (current.b << 16) | current.a,
               (current.a == verified.a && current.b == verified.b) ? "VERIFIED O(1)" : "MISMATCH");
    }
    printf("=========================================\n");
    return 0;
}
```

---

## 5. Production War Story: The Disaster of `rsync --delete` on Root
In 2017, a DevOps engineer wrote an automated nightly backup script:
```bash
SRC_DIR="/var/data"
DEST_DIR="/backup/data"
rsync -av --delete $SRC_DIR/ $DEST_DIR/
```
One evening, during an operating system upgrade, the `/var/data` disk mount failed to mount, leaving `/var/data` as an empty directory.
When the nightly cron job executed, `rsync` observed that the source directory was empty.
Because `--delete` was passed, `rsync` faithfully deleted **every single backup on the destination storage array** to make it match the empty source directory!
Fix:
1. Always test directory existence and mount status before running rsync: `[ -d "$SRC_DIR/expected_file" ] || exit 1`.
2. Use rsync's `--max-delete` flag to prevent catastrophic mass deletions: `--max-delete=50`.
---

## 8. Deep Systems Internals: Sparse File Detection & Extended Attributes
When backing up virtual machine disk images (`.raw`, `.qcow2`) or database files:
1. Files often contain multi-gigabyte blocks of pure zero bytes (sparse files).
2. Standard file copy utilities read the zeros and write real physical disk sectors, expanding a 2 GB sparse file into 100 GB of wasted physical disk!
3. `rsync` includes the **`--sparse` (`-S`)** flag:
   - It inspects data blocks for consecutive zero bytes.
   - When zeros are detected, it issues `lseek(fd, offset, SEEK_CUR)` instead of `write()`, creating an efficient filesystem hole and saving massive storage and network transfer time.
4. To preserve Linux Access Control Lists (ACLs) and Extended Attributes (xattrs) like SELinux labels, pass `-A` and `-X`:
```bash
rsync -avzPAX /data/ remote:/backup/
```
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `rsync` fails with `rsync: connection unexpectedly closed`**:
   - Root Cause: The remote shell printed non-standard greeting messages in `.bashrc` (e.g. `echo "Welcome!"`), corrupting rsync's binary protocol handshake!
   - Fix: Ensure all interactive echos in `~/.bashrc` are wrapped in `[ -z "$PS1" ] && return` so non-interactive SSH sessions output zero text.
2. **Symptom: `rsync` retransmits identical files every time**:
   - Root Cause: Timestamps or filesystem precision mismatch (e.g. FAT32 2-second timestamp resolution vs ext4 nanosecond timestamps).
   - Fix: Pass `--modify-window=1` or use checksum mode `-c` (`--checksum`).
3. **Symptom: `rsync` runs out of memory on millions of tiny files**:
   - In older rsync versions, the entire file list was buffered in RAM before transfer.
   - Fix: Use modern rsync (3.0+) which enables incremental recursion by default.
---

## 10. Advanced Security Auditing: Restricted `rsync` with `rrsync`
When granting third parties or backup servers SSH access to run `rsync`, do not give them full interactive shell access!
OpenSSH provides **`rrsync` (Restricted rsync)**:
In `~/.ssh/authorized_keys` on the backup target:
```ssh-config
command="/usr/bin/rrsync -ro /backups/client1/",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc ssh-ed25519 AAAAC3NzaC1lZDI1NTE5... backup-client
```
This forces the SSH session to:
1. Lock the client strictly inside the `/backups/client1/` directory.
2. Enforce read-only (`-ro`) or write-only mode.
3. Disable all interactive shells, port forwardings, and agent access.
---

## 11. The Rsync Remote Shell Protocol & Pipeline Trace
How does `rsync` communicate with remote servers over SSH?
1. The local `rsync` client invokes:
   `ssh remote_host rsync --server -logDtprze.iLsfxCIvu . /destination/data/`
2. It spawns an identical `rsync` process in "server mode" on the remote machine.
3. The two `rsync` processes establish a binary protocol exchange over standard input and standard output piped through the encrypted SSH transport.
4. Because the protocol uses raw binary encoding and pipelined streaming, `rsync` transmits deltas without the per-packet round-trip delays that cripple older interactive protocols.
