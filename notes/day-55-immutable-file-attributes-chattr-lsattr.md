# Day 55: Immutable File Attributes: chattr, lsattr, ext4 Inode Flags, and WORM Semantics

Discretionary Access Control (DAC) and POSIX ACLs share a fundamental security assumption: the superuser (`UID 0`) can bypass all permission checks. When a system is compromised or an errant recursive script (`rm -rf`) executes, standard UNIX permissions offer zero resistance. Immutable and Append-Only file attributes implemented within the Virtual Filesystem (VFS) and filesystem drivers (`ext4`, `xfs`) enforce Write-Once-Read-Many (WORM) semantics that halt even root-level modifications.

---

## 1. Filesystem Inode Flags & The VFS Interface

Linux filesystems store operational flags directly inside the on-disk inode structure. For `ext4`, this is represented within `struct ext4_inode` defined in `fs/ext4/ext4.h`.

### Kernel Inode Flag Bitmasks
```c
/* ext4 on-disk inode flags (stored in i_flags) */
#define EXT4_SECRM_FL        0x00000001 /* Secure deletion */
#define EXT4_UNRM_FL         0x00000002 /* Undelete */
#define EXT4_COMPR_FL        0x00000004 /* Compress file */
#define EXT4_SYNC_FL         0x00000008 /* Synchronous updates */
#define EXT4_IMMUTABLE_FL    0x00000010 /* Immutable file (+i) */
#define EXT4_APPEND_FL       0x00000020 /* Append-only writes (+a) */
#define EXT4_NODUMP_FL       0x00000040 /* Do not dump file */
#define EXT4_NOATIME_FL      0x00000080 /* Do not update atime */
```

### VFS Permission Verification
When any process (including UID 0) invokes `unlink()`, `truncate()`, `open(..., O_WRONLY)`, or `rename()`, the kernel passes through `inode_permission()` in `fs/namei.c`. If `EXT4_IMMUTABLE_FL` (or the generic VFS flag `S_IMMUTABLE`) is asserted:

```c
/* Kernel VFS enforcement check in fs/namei.c */
static inline int may_delete(struct user_namespace *mnt_userns,
                             struct inode *dir, struct dentry *victim, int isdir) {
    if (IS_APPEND(dir) || IS_IMMUTABLE(dir))
        return -EPERM;
    if (IS_APPEND(d_backing_inode(victim)) || IS_IMMUTABLE(d_backing_inode(victim)))
        return -EPERM;
    /* ... DAC checks continue ... */
}
```
The kernel returns `-EPERM` (Operation not permitted) immediately. DAC algorithms are not even consulted.

---

## 2. Inode Immutability Transitions & Boolean Algebra

Immutability forms a strict state-transition lattice. Modifying inode flags requires the Linux capability `CAP_LINUX_IMMUTABLE`.

### Mathematical Inode State Machine
Let $I$ be the Immutable bit (`+i`), $A$ be the Append-Only bit (`+a`), and $W$ be write authorization:

$$W_{\text{allow}} = \begin{cases}
\text{Write} \land \text{Truncate} \land \text{Delete} & \text{if } \neg I \land \neg A \\
\text{Append Only} (O\_APPEND) & \text{if } \neg I \land A \\
\emptyset (\text{Complete Freeze}) & \text{if } I
\end{cases}$$

Notice that $I$ strictly dominates $A$:
$$I \implies \neg W_{\text{any}}$$

```text
               [Standard Inode (rwx DAC)]
                         |
           +-------------+-------------+
           | (+a)                      | (+i)
           v                           v
   [Append-Only Mode]          [Immutable Mode]
   - O_APPEND Allowed          - Zero Writes Allowed
   - No Truncation             - No Rename / No Link
   - No Deletion               - No Deletion
           |                           ^
           +------------(+i)-----------+
```

---

## 3. Compilable C Implementation: Manipulating Inode Flags via `ioctl(FS_IOC_SETFLAGS)`

Userspace tools (`chattr`, `lsattr`) do not rely on standard POSIX syscalls; they communicate directly with the underlying filesystem driver via the generic filesystem `ioctl` interface (`FS_IOC_GETFLAGS` and `FS_IOC_SETFLAGS`).

Compile with: `gcc -O2 -Wall -Wextra toggle_immutable.c -o toggle_immutable`

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <errno.h>

void display_flags(int flags) {
    printf("Active flags (0x%08X): ", flags);
    if (flags & FS_IMMUTABLE_FL) printf("[IMMUTABLE (+i)] ");
    if (flags & FS_APPEND_FL)    printf("[APPEND-ONLY (+a)] ");
    if (flags & FS_NODUMP_FL)    printf("[NODUMP (+d)] ");
    if (flags & FS_SYNC_FL)      printf("[SYNC (+S)] ");
    printf("\n");
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        printf("Usage: %s <file> <enable_i|disable_i|enable_a|disable_a>\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *filepath = argv[1];
    const char *action = argv[2];

    int fd = open(filepath, O_RDONLY);
    if (fd < 0) {
        perror("open failed");
        return EXIT_FAILURE;
    }

    int flags = 0;
    /* Step 1: Read current on-disk inode flags */
    if (ioctl(fd, FS_IOC_GETFLAGS, &flags) < 0) {
        perror("ioctl(FS_IOC_GETFLAGS) failed");
        close(fd);
        return EXIT_FAILURE;
    }

    printf("Prior to mutation: ");
    display_flags(flags);

    /* Step 2: Mutate bitmask based on command */
    if (strcmp(action, "enable_i") == 0) {
        flags |= FS_IMMUTABLE_FL;
    } else if (strcmp(action, "disable_i") == 0) {
        flags &= ~FS_IMMUTABLE_FL;
    } else if (strcmp(action, "enable_a") == 0) {
        flags |= FS_APPEND_FL;
    } else if (strcmp(action, "disable_a") == 0) {
        flags &= ~FS_APPEND_FL;
    } else {
        fprintf(stderr, "Unknown action: %s\n", action);
        close(fd);
        return EXIT_FAILURE;
    }

    /* Step 3: Write updated inode flags back to disk (Requires CAP_LINUX_IMMUTABLE) */
    if (ioctl(fd, FS_IOC_SETFLAGS, &flags) < 0) {
        perror("ioctl(FS_IOC_SETFLAGS) failed (Need root / CAP_LINUX_IMMUTABLE)");
        close(fd);
        return EXIT_FAILURE;
    }

    printf("Successfully updated on-disk inode: ");
    display_flags(flags);

    close(fd);
    return EXIT_SUCCESS;
}
```

---

## 4. Operational Comparison: chmod vs setfacl vs chattr

| Dimension | Standard DAC (`chmod`) | POSIX ACLs (`setfacl`) | Extended Inode Attributes (`chattr`) |
| :--- | :--- | :--- | :--- |
| **Enforcement Layer** | VFS user/group permission check | VFS extended attribute check | Filesystem driver & VFS pre-check |
| **Affects Root (UID 0)?**| **NO** (Bypassed via `CAP_DAC_OVERRIDE`) | **NO** (Bypassed via `CAP_DAC_OVERRIDE`) | **YES** (Root cannot write/delete `+i`) |
| **Prevents Deletion?** | Only if directory lacks `w` bit | Only if directory lacks `w` bit | **YES** (`+i` and `+a` block `unlink`/`rename`) |
| **Required Capability**| Owning User or `CAP_FOWNER` | Owning User or `CAP_FOWNER` | `CAP_LINUX_IMMUTABLE` (Root only) |
| **Storage Location** | Inode `i_mode` (16-bit integer) | Inode Extended Attributes (`xattr`) | Inode `i_flags` (32-bit bitfield) |

---

## 5. Production Post-Mortem: Rootkit Persistence & Ansible Deployment Deadlock

### Incident Overview
A financial technology company deployed `chattr +i` across all production server configuration files (`/etc/resolv.conf`, `/etc/sudoers`, `/etc/pam.d/*`, `/etc/shadow`) as a defensive measure against malicious tamper scripts.

Weeks later, a scheduled zero-downtime OS security patching workflow managed via Ansible ground to a complete halt:
1. **Package Upgrade Failure**: The glibc update package attempted to update `/etc/nsswitch.conf` and `/etc/resolv.conf`. The `dpkg` unpack routine failed with `EPERM (Operation not permitted)`.
2. **Deadlocked Daemons**: Because the package manager aborted in an unrecoverable state, `dpkg` locked its database (`/var/lib/dpkg/lock-frontend`), aborting kernel patch installations across 1,200 production nodes.
3. **Misattributed RCA**: Engineers assumed the storage SAN was experiencing filesystem read-only remounts (`ro` mode) due to I/O corruption, wasting 6 hours on storage hardware diagnostics.

### Rootkit Use of Immutability
Conversely, sophisticated userland rootkits routinely leverage `chattr +i`:
- Attackers drop a malicious shared library in `/lib/x86_64-linux-gnu/libselinux.so` and apply `chattr +i`.
- When incident response teams execute `rm -f` or attempt to replace the compromised binary with clean package archives, `rm` fails with `Operation not permitted`.
- Always inspect inode attributes during forensic incident response via:
```bash
lsattr -R /etc /bin /sbin /usr/bin /lib 2>/dev/null | grep -E '^....i'
```
---

## 6. On-Disk Inode Byte Alignment & Ext4 Binary Offsets

In the `ext4` filesystem driver, every on-disk inode occupies either 128 bytes (legacy format) or 256 bytes (modern Linux standard). The `i_flags` field is located at a fixed 32-bit offset within the binary header:

```c
/* Ext4 on-disk inode structure binary layout */
struct ext4_inode_disk {
    __le16  i_mode;        /* 0x00: File mode and type */
    __le16  i_uid;         /* 0x02: Low 16 bits of Owner UID */
    __le32  i_size_lo;     /* 0x04: Lower 32 bits of file size */
    __le32  i_atime;       /* 0x08: Access time */
    __le32  i_ctime;       /* 0x0C: Inode change time */
    __le32  i_mtime;       /* 0x10: Modification time */
    __le32  i_dtime;       /* 0x14: Deletion Time */
    __le16  i_gid;         /* 0x18: Low 16 bits of Group GID */
    __le16  i_links_count; /* 0x1A: Hard links count */
    __le32  i_blocks_lo;   /* 0x1C: Lower 32 bits of 512-byte blocks count */
    __le32  i_flags;       /* 0x20: EXT4 INODE FLAGS (32-bit bitfield) */
    /* ... extents tree root, extended attributes, checksum ... */
};
```

### Forensic Inode Inspection with `debugfs`
When an administrative shell loses the `chattr` utility or during low-level disk forensics, systems programmers inspect and manipulate inode flags directly using `debugfs`:

```bash
# Open unmounted or read-only filesystem
debugfs -w /dev/sda1

# Locate inode number of target asset
debugfs:  stat /etc/resolv.conf
# Output displays: Inode: 131075 ... Flags: 0x10 (immutable)

# Clear immutable bit directly at raw block layer
debugfs:  set_inode_field /etc/resolv.conf flags 0x00000000
```

---

## 7. Extended Inode Flags Reference Catalog

Beyond `+i` (Immutable) and `+a` (Append-Only), Linux filesystems support specialized flags governing physical storage behavior:

1. **`+d` (No Dump / `EXT4_NODUMP_FL`)**: Directs the UNIX `dump(8)` backup utility to omit the designated file or directory tree from backup archives.
2. **`+S` (Synchronous Updates / `EXT4_SYNC_FL`)**: Forces synchronous writes directly to physical storage media upon every `write()` syscall, bypassing page cache dirty writeback.
3. **`+A` (No Atime Updates / `EXT4_NOATIME_FL`)**: Suppresses disk I/O write operations to the inode's `i_atime` field during read operations, reducing flash memory wear and improving database read latency.
4. **`+c` (Compressed / `EXT4_COMPR_FL`)**: Requests transparent on-disk kernel compression (subject to kernel configuration and filesystem features).
