# 🛡️ Day 5: Linux Permissions, Inode Bitfields & Security Primitives

> **Zero External Dependency Guarantee**: This document is an exhaustive, encyclopedic masterclass. It contains complete historical context, the Linux inode 16-bit `st_mode` bitfield layout, SUID/SGID/Sticky Bit kernel mechanics, mathematical `umask` derivations, real-world banking lockout post-mortems, and FAANG technical interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & Historical Context

In 1971, when Unix was being deployed across AT&T corporate mainframes, multiple researchers and engineers shared the same physical CPU and hard disk drive.
To protect system stability and maintain confidential data, Dennis Ritchie designed the **Unix Discretionary Access Control (DAC)** model.

Instead of storing access control lists in separate database tables, Ritchie compressed the entire permission model of a file into a single **16-bit integer inside the inode structure on disk**.

---

## 2. Inode Deep-Dive: The 16-Bit `st_mode` Bitfield

Every file on a Linux filesystem (`ext4`, `XFS`, `btrfs`, `ZFS`) has an inode that stores a 16-bit integer field called **`st_mode`**.

```
                           THE 16-BIT `st_mode` BITFIELD
┌──────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│  FILE TYPE (4b)  │ SPECIAL BITS │  USER (3b)   │  GROUP (3b)  │  OTHER (3b)  │
│  [15][14][13][12]│ [11][10][9]  │  [8] [7] [6] │  [5] [4] [3] │  [2] [1] [0] │
└──────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
         │               │              │              │              │
         ▼               ▼              ▼              ▼              ▼
   0100 = Directory   SUID  = 4      r = 4 (100)    r = 4 (100)    r = 4 (100)
   1000 = Regular     SGID  = 2      w = 2 (010)    w = 2 (010)    w = 2 (010)
   1010 = Symlink     Sticky= 1      x = 1 (001)    x = 1 (001)    x = 1 (001)
   0001 = Named Pipe
   1100 = Unix Socket
```

### 1. File Type (Bits 12–15)
The top 4 bits determine what kind of file it is:
* `S_IFREG` (`0100000` octal): Regular text/binary file (displayed as `-` in `ls -l`).
* `S_IFDIR` (`0040000` octal): Directory (displayed as `d`).
* `S_IFLNK` (`0120000` octal): Symbolic link (displayed as `l`).
* `S_IFIFO` (`0010000` octal): Named pipe (displayed as `p`).
* `S_IFSOCK`(`0140000` octal): Unix domain socket (displayed as `s`).

### 2. Special Security Bits (Bits 9–11)
* **Bit 11: Setuid (SUID - Value 4)**: Run as the file's owner.
* **Bit 10: Setgid (SGID - Value 2)**: Run as the file's group.
* **Bit 9: Sticky Bit (Value 1)**: Restricted deletion flag.

### 3. The 9 Permission Bits (Bits 0–8)
Divided into three 3-bit octal digits:
* **User (Owner)**: Bits 6, 7, 8 (`rwx`).
* **Group (Team)**: Bits 3, 4, 5 (`rwx`).
* **Others (World)**: Bits 0, 1, 2 (`rwx`).

---

## 3. The 3 Special Security Bits Explained: SUID, SGID & Sticky Bit

These 3 bits are where junior engineers get confused and senior security architects excel:

### 1. SUID (Set User ID - Octal `4000` / Symbol `s`):
* **The Problem**: Normal users must be able to change their login passwords. But passwords are encrypted inside `/etc/shadow`, which is owned by `root` and has permission `0640` (unreadable by regular users)!
* **The SUID Solution**: When a binary has the SUID bit set (e.g. `/usr/bin/passwd`), whenever an unprivileged user executes it, the Linux kernel **temporarily elevates the process's Effective User ID (EUID) to `root`**!
* In `ls -l`, SUID shows up as an `s` in the user execute position:
  `-rwsr-xr-x 1 root root /usr/bin/passwd`

### 2. SGID (Set Group ID - Octal `2000` / Symbol `s`):
* When set on a **directory**: Any new file created inside that directory automatically inherits the **group ownership of the parent directory**, rather than the primary group of the user who created it!
* **Use Case**: Critical for shared corporate project folders where team members collaborate.

### 3. Sticky Bit (Octal `1000` / Symbol `t`):
* When set on a directory: **Only the owner of a file (or root) can delete or rename that file**, even if everyone else has write permissions on the directory!
* **Why `/tmp` MUST have the Sticky Bit**: The `/tmp` folder has permission **`1777`** (`drwxrwxrwt`). Anyone in the world can write temporary files there. Without the sticky bit, User A could maliciously run `rm /tmp/*` and delete all temporary files belonging to other users!

---

## 4. The Mathematical Law of `umask` (User Mask)

When you create a new file with `touch newfile.txt` or `open()`, why does it automatically get permissions `644` (`rw-r--r--`) rather than `777`?

Because of the **`umask` (User Creation Mask)**!

### The Kernel Calculation:
1. When creating a **Regular File**, the OS starts with maximum permissions: **`0666`** (no execute).
2. When creating a **Directory**, the OS starts with maximum permissions: **`0777`** (needs execute to enter).
3. The kernel applies the bitwise formula:

$$\text{Final Mode} = \text{Base Mode} \ \& \ (\sim\text{umask})$$

```
Base File Mode:   0666  =  110 110 110 (rw- rw- rw-)
Default umask:    0022  =  000 010 010 (----w--w-)
NOT umask:                111 101 101 (rwxr-xr-x)
─────────────────────────────────────────────────────
Bitwise AND (&):          110 100 100 (rw- r-- r--)  ==> 0644!
```

---

## 5. The Directory Execute Trap: The "Invisible Door"

This is a classic question that trips up freshers in technical interviews:

> **The Scenario**:  
> You have a file `/secret/data.csv` with permission `0777` (`rwxrwxrwx` - everyone can read and edit).  
> The parent folder `/secret/` has permission `0644` (`rw-r--r--`).  
> **Can an unprivileged user read `/secret/data.csv`?**

### The Answer: NO! ABSOLUTELY NOT!
* To access any file on a Linux filesystem, the operating system kernel must traverse the directory tree from root (`/`) downwards.
* Traversing into a directory requires the **Execute (`x`) permission** on that directory!
* Because `/secret/` lacks the `x` bit (`rw-`), the kernel immediately throws **`EACCES (Permission denied)`** before it even checks the permissions of `data.csv`!
* **The Rule**: On a directory, `r` lets you read the list of names; **`x` lets you pass through the door!**

---

## 6. Real-World Production War Story: The Accidental `chmod -R 777 /`

### The Incident:
In 2018, a junior systems administrator at a financial institution was attempting to grant permissions to a web server folder at `/var/www/html`.  
The administrator intended to run:
```bash
chmod -R 777 /var/www/html/uploads
```
Due to a space typo in the terminal, the command executed as:
```bash
chmod -R 777 / var/www/html/uploads
```

### What Happened Under the Hood:
The space caused the shell to execute `chmod -R 777` against **the root filesystem (`/`)**!
1. Every file and binary on the operating system had its permissions overwritten to `0777`.
2. **The SUID bits were stripped**: Setting `777` wiped the special SUID bit (`4000`) off `/usr/bin/sudo` and `/usr/bin/su`.
3. OpenSSH immediately detected that `/etc/ssh/ssh_host_rsa_key` was world-readable (`777`) and disabled all SSH daemon connections for security.
4. When the administrators tried to log back in to fix the typo, `sudo` failed with: `"sudo: /usr/bin/sudo must be mode 4755"`.
5. The entire server cluster was unrecoverable and had to be completely rebuilt from bare metal backups.

---

## 7. Staff-Level Technical Interview Deep-Dives

### Question 1: How do you verify and manipulate Access Control Lists (ACLs) beyond traditional Unix permissions?
**Exhaustive Answer**:
* Traditional Unix permissions only allow one user and one group. If you need User A (read), User B (read-write), and Group C (execute), traditional octal permissions fail.
* POSIX Access Control Lists (ACLs) solve this:
  * View ACLs: `getfacl filename`
  * Add specific user permission: `setfacl -m u:alice:rw filename`
  * Add default ACLs to directories: `setfacl -d -m g:marketing:r /data`

### Question 2: What is the difference between Real UID, Effective UID, and Saved UID in Linux processes?
**Exhaustive Answer**:
* **Real UID (RUID)**: Identifies the actual user who spawned the process (the person sitting at the keyboard).
* **Effective UID (EUID)**: The identity used by the Linux kernel to perform **permission checks** for system calls. When a SUID binary runs, EUID is changed to the file's owner (e.g. root).
* **Saved UID (SUID)**: Stores a copy of the EUID prior to privilege dropping. This allows a privileged daemon (like NGINX) to temporarily drop to unprivileged user `www-data` and later regain root privileges to bind to port 80.

---

## 8. Complete Verification Checklist (Zero Gaps)
Before marking Day 5 as completed in your tracker, verify that you can answer these without looking:
- [ ] Can you draw the full 16-bit `st_mode` inode bitfield layout (File type, SUID/SGID/Sticky, User, Group, Other)?
- [ ] Can you explain why `/usr/bin/passwd` requires the SUID bit to function?
- [ ] What is the exact bitwise formula used by `umask` to calculate default file creation permissions?
- [ ] Why can't a user read a `777` file if the parent directory lacks execute (`x`) permissions?
