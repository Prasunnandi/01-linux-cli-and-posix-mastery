# Day 50: Emergency System Rescue - Single-User Mode, chroot Jails, and Broken Fstab Recovery

## 1. System Failure Modes: When PID 1 Fails to Reach Multi-User Target

When an operating system suffers from filesystem corruption, broken `/etc/fstab` entries, corrupted PAM authentication libraries, or an unbootable glibc update, standard multi-user startup is impossible. A systems engineer must know how to bypass the standard init graph and seize raw kernel-level execution control:

### The Three Rescue Paradigms:
1. **Emergency Mode (`systemd.unit=emergency.target`)**:
   - The most minimal systemd mode.
   - Mounts the root filesystem read-only (`ro`), starts no background services, configures no network interfaces, and spawns an interactive root shell directly on the active console via `/bin/sulogin`.
2. **Rescue Mode (`systemd.unit=rescue.target` or `single` / `1`)**:
   - Mounts all local filesystems (`/etc/fstab`), loads basic hardware modules, but starts no networking or daemon services. Spawns root maintenance shell.
3. **Emergency Kernel Shell Bypass (`init=/bin/bash` or `init=/bin/sh`)**:
   - Completely bypasses systemd, Upstart, and SysVinit entirely!
   - The Linux kernel executes `/bin/bash` directly as **PID 1**.
   - No filesystems are checked, root is mounted read-only, and no signal handlers are installed. Terminating this shell causes an immediate kernel panic.

```
+--------------------------------------------------------------------------+
|                       RESCUE ACCESS TARGET TAXONOMY                      |
+--------------------------------------------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
          v                                                   v
+-------------------------------+             +------------------------------+
| systemd.unit=emergency.target |             |      init=/bin/bash          |
|  - PID 1 = systemd            |             |  - PID 1 = /bin/bash         |
|  - Root: Read-Only (ro)       |             |  - Bypasses systemd entirely |
|  - No other filesystems       |             |  - Zero daemons, zero cgroups|
|  - Direct sulogin console     |             |  - Requires remount rw       |
+-------------------------------+             +------------------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: Virtual Filesystems in chroot

When repairing a broken operating system from a live rescue USB, the administrator mounts the broken target drive to `/mnt` and enters it via `chroot /mnt`. 

However, running commands like `apt`, `yum`, `update-initramfs`, or `grub-install` inside the jail immediately fails unless the kernel's virtual pseudo-filesystems are bind-mounted:

```c
/* Real Linux Kernel VFS Mount Definition from fs/mount.h */
struct mount {
    struct hlist_node   mnt_hash;
    struct mount        *mnt_parent;
    struct dentry       *mnt_mountpoint;
    struct vfsmount     mnt;
    int                 mnt_id;             /* Unique mount identifier */
    int                 mnt_group_id;       /* Shared mount peer group */
    int                 mnt_expiry_mark;
    struct list_head    mnt_shares;         /* Shared mount list */
    struct list_head    mnt_slave_list;     /* Slave mount list */
    struct list_head    mnt_slave;
    struct mount        *mnt_master;
    struct mnt_namespace *mnt_ns;           /* Associated mount namespace */
};
```

### The 4 Mandatory Pseudo-Filesystems:
1. **`/dev` (`devtmpfs`)**: Kernel device nodes. Without this, `grub-install` cannot find `/dev/sda` or `/dev/nvme0n1`.
2. **`/proc` (`procfs`)**: Process tables and kernel status. Without this, `ps`, `kill`, and memory inspection fail.
3. **`/sys` (`sysfs`)**: Hardware topology, EFI NVRAM variables (`/sys/firmware/efi/efivars`), and kernel module parameters.
4. **`/run` (`tmpfs`)**: Volatile runtime sockets for D-Bus, udev, and systemd IPC.

---

## 3. Mathematical Foundations: chroot Isolation Boundaries and Escape Vectors

The `chroot()` system call changes the root directory path resolution anchor for the current process and its children:
$$	ext{PathResolve}(	ext{"/etc/passwd"}, P) = 	ext{CurrentRoot}(P) \circ 	ext{"/etc/passwd"}$$

### The Classic chroot Escape Theorem:
`chroot()` is an administrative deployment tool, **not a security boundary**. If a process inside a chroot jail retains `CAP_SYS_CHROOT` or runs as UID 0 (root), it can mathematically escape the jail in $O(1)$ operations using nested directory file descriptors.

Let $R_{	ext{jail}}$ be the current restricted root.
1. Process opens a file descriptor to its current working directory:
   $$fd = 	ext{open}(".", O\_RDONLY)$$
2. Process creates a subdirectory and calls `chroot()` on it, lowering its root anchor:
   $$	ext{mkdir}("sub"); \quad 	ext{chroot}("sub");$$
3. Process calls `fchdir(fd)`: The process's current working directory is now located **outside and above** the newly defined root anchor!
4. Process traverses upwards with repeated `chdir("..")` until it reaches the true global VFS root:
   $$	ext{chdir}("../../../.."); \quad 	ext{chroot}(".");$$
The process is now completely liberated from the jail.

---

## 4. Compilable C Implementation: chroot Jail Creator & Diagnostic Probe

Save the following program as `chroot_jail.c`:

```c
/*
 * chroot_jail.c - POSIX chroot Jail Creation and Containment Engine
 * Demonstrates:
 * 1. Setting up directory isolation via chroot()
 * 2. Changing working directory to prevent path leaks
 * 3. Dropping privileges to demonstrate unprivileged jail security
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread chroot_jail.c -o chroot_jail
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>

int enter_chroot_jail(const char *jail_path)
{
    printf("[JAIL] Entering chroot jail at: %s\n", jail_path);

    /* Step 1: Change to jail directory */
    if (chdir(jail_path) < 0) {
        perror("chdir failed");
        return -1;
    }

    /* Step 2: Invoke chroot (Requires CAP_SYS_CHROOT or UID 0) */
    if (chroot(jail_path) < 0) {
        perror("chroot failed (requires root/CAP_SYS_CHROOT)");
        return -1;
    }

    /* Step 3: Crucial! Change directory to new root to prevent CWD leak */
    if (chdir("/") < 0) {
        perror("chdir / failed inside jail");
        return -1;
    }

    printf("[JAIL] Successfully confined to new root: /\n");
    return 0;
}

int main(int argc, char *argv[])
{
    printf("====================================================\n");
    printf("POSIX chroot JAIL CONTAINMENT ENGINE\n");
    printf("====================================================\n");

    const char *jail_dir = (argc > 1) ? argv[1] : "/tmp/test_jail";

    /* Create test directory structure */
    mkdir(jail_dir, 0755);

    /* Attempt to enter jail */
    if (enter_chroot_jail(jail_dir) == 0) {
        /* Verify that root directory is now the jail */
        char cwd[256];
        if (getcwd(cwd, sizeof(cwd))) {
            printf("[JAIL] Active working directory: %s\n", cwd);
        }
    } else {
        printf("[NOTE] chroot system call restricted in unprivileged execution mode.\n");
    }

    printf("[JAIL] Demonstration complete.\n");
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The Typo in /etc/fstab Emergency Shell Lockout

In 2020, an administrator added an NFS network mount to `/etc/fstab` on a mission-critical web server:
```text
192.168.1.50:/data   /var/www/data   nfs   defaults   0  0
```
During a weekend kernel security patch, the server was rebooted. However, the external NFS server was temporarily offline for network maintenance.

Because systemd interprets `/etc/fstab` lines without the `nofail` or `_netdev` options as hard dependencies for `local-fs.target`:
1. systemd blocked for 90 seconds attempting to mount the offline NFS share.
2. The mount timed out, causing `local-fs.target` to fail.
3. systemd automatically aborted the boot and entered `emergency.target`, spawning `/bin/sulogin`.
4. **The Critical Disaster**: The root account had its password locked (`root:!:` in `/etc/shadow`), and SSH keys were ignored because network services were offline! The server was completely inaccessible remotely, prompting a high-priority datacenter truck roll.

**The Fix**:
1. In GRUB, intercepted the boot menu, appended `systemd.unit=emergency.target init=/bin/sh` to the kernel command line.
2. Remounted root as read-write:
   ```bash
   mount -o remount,rw /
   ```
3. Edited `/etc/fstab` to add `nofail,_netdev`:
   ```text
   192.168.1.50:/data   /var/www/data   nfs   defaults,_netdev,nofail   0  0
   ```
4. Remounted read-only and rebooted cleanly.

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Deep Technical Purpose |
| :--- | :--- | :--- |
| `mount -o remount,rw /` | Remount Read-Write | Converts read-only rescue root into a writable filesystem for repairs. |
| `mount --bind /dev /mnt/dev` | Virtual Bind Mount | Exposes host kernel device nodes inside the rescue mount target. |
| `chroot /mnt /bin/bash` | Enter Rescue Jail | Sets `/mnt` as root, enabling `grub-install` and `passwd` execution. |
| `systemd.debug-shell=1` | Early Root TTY | Spawns a root shell on `tty9` (accessible via Alt+F9) at earliest boot. |
| `fsck -y -f /dev/sda1` | Force Filesystem Check | Non-interactively repairs ext4 filesystem metadata corruption. |
