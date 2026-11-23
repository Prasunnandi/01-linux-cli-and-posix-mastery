# Day 05: POSIX Security Architecture: Inode `st_mode` Bitfield, Octal Math, SUID/SGID & TOCTOU Physics

> **Zero External Dependency Guarantee**: This document is an encyclopedic, self-contained masterclass. It contains complete historical context, Linux inode permission bitfield structures, mathematical `umask` boolean proofs, SUID/SGID execution mechanics, C system calls, real-world privilege escalation post-mortems, and FAANG staff-level interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & Historical Origins

In the early 1970s, Unix introduced a multi-user security model that remains the foundation of all modern operating systems. Instead of complex access control lists consuming precious disk sectors on PDP-11 computers, Ken Thompson and Dennis Ritchie encoded all file metadata, types, and permissions into a single, compact **16-bit integer** inside the filesystem inode: the **`st_mode` bitfield**.

```
THE 16-BIT INODE `st_mode` BITFIELD LAYOUT:
Bit Index: 15 14 13 12 | 11 10  9 |  8  7  6 |  5  4  3 |  2  1  0
Field:     [File Type] | [Special]| [ User  ] | [ Group ] | [ Others]
                       | SUID     |   r  w  x |   r  w  x |   r  w  x
                       | SGID     |           |           |
                       | Sticky   |           |           |
```

Every permission query, execution request, and file modification in Linux traverses this 16-bit structure.

---

## 2. In-Depth Binary Anatomy of the 16-bit `st_mode`

Defined in `<sys/stat.h>`:

### 2.1 The File Type Mask: Bits 12 to 15 (`S_IFMT = 0170000` Octal)
The highest 4 bits define what kind of filesystem object this inode represents:

| Object Type | POSIX Constant | Octal Value | Bit Pattern (15-12) | `ls -l` Prefix Character |
| :--- | :--- | :--- | :--- | :---: |
| **Regular File** | `S_IFREG` | `0100000` | `1000` | `-` |
| **Directory** | `S_IFDIR` | `0040000` | `0100` | `d` |
| **Symbolic Link**| `S_IFLNK` | `0120000` | `1010` | `l` |
| **Block Device** | `S_IFBLK` | `0060000` | `0110` | `b` |
| **Char Device**  | `S_IFCHR` | `0020000` | `0010` | `c` |
| **FIFO / Pipe**  | `S_IFIFO` | `0010000` | `0001` | `p` |
| **UNIX Socket**  | `S_IFSOCK`| `0140000` | `1100` | `s` |

To extract the file type in C:
```c
if ((statbuf.st_mode & S_IFMT) == S_IFDIR) {
    // Inode is a directory!
}
```

### 2.2 The Special Bits: Bits 9 to 11 (`07000` Octal)
These three bits alter process execution privileges and directory file deletion rules:

1. **SUID (Set User ID, Bit 11, `04000`, `S_ISUID`)**:
   - When an executable binary with SUID is run, the operating system sets the process's **Effective UID (EUID)** to the **owner of the file**, NOT the user running the command!
   - Example: `/usr/bin/passwd` is owned by `root`. When a regular user executes it, the process gains root privileges to modify `/etc/shadow`.
2. **SGID (Set Group ID, Bit 10, `02000`, `S_ISGID`)**:
   - On an executable: Sets Effective GID to the file's group.
   - On a directory: Any new files created inside automatically inherit the **group ownership of the parent directory**, rather than the primary group of the creating user. Critical for shared team collaboration directories!
3. **Sticky Bit (Restricted Deletion Flag, Bit 9, `01000`, `S_ISVTX`)**:
   - On a directory (e.g., `/tmp`): Any user can create files, but a user can **only delete or rename files that they personally own**, even if the directory has global write permissions (`0777`)!

### 2.3 Standard Permission Bits: Bits 0 to 8
* **User (Bits 6-8)**: `r` (4), `w` (2), `x` (1).
* **Group (Bits 3-5)**: `r` (4), `w` (2), `x` (1).
* **Others / World (Bits 0-2)**: `r` (4), `w` (2), `x` (1).

---

## 3. Mathematical Algebra of `umask`

The `umask` (User Mask) is a 9-bit bitmask that filters out permission bits during file and directory creation.

### 3.1 The Boolean Formulation
When an application calls `open("new_file.txt", O_CREAT, 0666)`, the kernel does **not** simply subtract the umask. It applies a **bitwise AND with the one's complement of the mask**:

$$\mathbf{Final\ Permissions} = \mathbf{Requested\ Mode} \ \& \ (\sim\mathbf{umask})$$

```
WORKED EXAMPLE: umask = 027 (Octal)
Requested Mode:  0666 = 110 110 110  (rw- rw- rw-)
umask:           0027 = 000 010 111  (--- -w- rwx)
~umask:          0750 = 111 101 000  (rwx r-x ---)

Bitwise AND:
  110 110 110  (0666)
& 111 101 000  (~0027)
-----------------------
  110 100 000  = 0640  (rw- r-- ---)
Result: Owner gets Read/Write, Group gets Read, World gets NOTHING!
```

---

## 4. Process Credentials: Real vs. Effective vs. Saved UID

Every Linux process maintains four distinct User ID credentials in `struct cred`:

```
PROCESS CREDENTIAL HIERARCHY:
+-------------------+---------------------------------------------------------+
| Credential Name   | Architectural Purpose                                   |
+-------------------+---------------------------------------------------------+
| Real UID (RUID)   | Identifies the physical user who launched the process.  |
| Effective UID     | Evaluated by kernel VFS for all filesystem permission checks!|
| Saved UID (SUID)  | Stores previous EUID to allow dropping and resuming privs.|
| Filesystem UID    | Linux-specific ID used for NFS and file permission checks.|
+-------------------+---------------------------------------------------------+
```

### 4.1 Dropping and Restoring Privileges Safely in C
```c
#include <unistd.h>

// Drop root privileges temporarily to unprivileged UID 1001:
seteuid(1001); // EUID becomes 1001, but Saved UID remains 0 (root)

// Perform untrusted user operations safely...

// Restore root privileges:
seteuid(0);    // Restores EUID to root using Saved UID!
```

---

## 5. Complete C Implementation: Inode Permission Inspector

```c
/**
 * perm_inspector.c - Low-level POSIX inode mode bitfield inspector.
 * Compile: gcc -Wall -Wextra -O2 perm_inspector.c -o perm_inspector
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

void inspect_permissions(const char *path) {
    struct stat st;
    if (stat(path, &st) < 0) {
        perror(path);
        return;
    }

    printf("File: %s\n", path);
    printf("Raw st_mode: 0%o (Octal)\n", st.st_mode);

    /* 1. File Type Decoding */
    printf("File Type: ");
    if (S_ISREG(st.st_mode))  printf("Regular File\n");
    else if (S_ISDIR(st.st_mode))  printf("Directory\n");
    else if (S_ISLNK(st.st_mode))  printf("Symbolic Link\n");
    else if (S_ISCHR(st.st_mode))  printf("Character Device\n");
    else if (S_ISBLK(st.st_mode))  printf("Block Device\n");
    else if (S_ISFIFO(st.st_mode)) printf("FIFO / Pipe\n");
    else if (S_ISSOCK(st.st_mode)) printf("UNIX Socket\n");

    /* 2. Special Bits */
    printf("Special Bits:\n");
    printf("  SUID:   %s\n", (st.st_mode & S_ISUID) ? "ACTIVE (Set-UID)" : "Off");
    printf("  SGID:   %s\n", (st.st_mode & S_ISGID) ? "ACTIVE (Set-GID)" : "Off");
    printf("  Sticky: %s\n", (st.st_mode & S_ISVTX) ? "ACTIVE (Sticky Bit)" : "Off");

    /* 3. Formatted rwxrwxrwx String */
    char p[10];
    p[0] = (st.st_mode & S_IRUSR) ? 'r' : '-';
    p[1] = (st.st_mode & S_IWUSR) ? 'w' : '-';
    p[2] = (st.st_mode & S_ISUID) ? ((st.st_mode & S_IXUSR) ? 's' : 'S') : ((st.st_mode & S_IXUSR) ? 'x' : '-');
    p[3] = (st.st_mode & S_IRGRP) ? 'r' : '-';
    p[4] = (st.st_mode & S_IWGRP) ? 'w' : '-';
    p[5] = (st.st_mode & S_ISGID) ? ((st.st_mode & S_IXGRP) ? 's' : 'S') : ((st.st_mode & S_IXGRP) ? 'x' : '-');
    p[6] = (st.st_mode & S_IROTH) ? 'r' : '-';
    p[7] = (st.st_mode & S_IWOTH) ? 'w' : '-';
    p[8] = (st.st_mode & S_ISVTX) ? ((st.st_mode & S_IXOTH) ? 't' : 'T') : ((st.st_mode & S_IXOTH) ? 'x' : '-');
    p[9] = '\0';

    printf("Permissions: %s (Octal: 0%o)\n\n", p, st.st_mode & 07777);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        inspect_permissions("/etc/passwd");
        inspect_permissions("/tmp");
    } else {
        for (int i = 1; i < argc; i++) {
            inspect_permissions(argv[i]);
        }
    }
    return EXIT_SUCCESS;
}
```

---

## 6. Real-World Security War Stories

### 6.1 War Story 1: The TOCTOU Symlink Vulnerability in `/tmp`
* **The Vulnerability**: An administrative backup daemon ran as `root`. Every midnight, it verified whether `/tmp/report.txt` existed using `access()`. If it did not exist, it opened the file and wrote sensitive database encryption keys:
  ```c
  // FATAL TOCTOU RACE CONDITION:
  if (access("/tmp/report.txt", F_OK) != 0) {
      // TIME GAP: Attacker creates a symlink right here!
      int fd = open("/tmp/report.txt", O_CREAT | O_WRONLY, 0666);
      write(fd, secret_key, sizeof(secret_key));
  }
  ```
* **The Exploit**: A malicious local user executed an exploit script in a tight loop. During the microsecond gap between `access()` and `open()`, the attacker created a symbolic link pointing to `/etc/shadow`:
  `ln -s /etc/shadow /tmp/report.txt`
* **The Disaster**: The root process opened the symlink and overwrote the system `/etc/shadow` file, destroying system authentication!
* **The Fix**: Never use `access()` before `open()`. Use atomic flags:
  `open("/tmp/report.txt", O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW, 0600);`

---

## 7. Staff-Level Technical Interview Deep-Dives

### Question 1: What is the exact difference between `chmod 0755` and `chmod 1755` on a directory?
**Exhaustive Answer**:
* `0755` grants Owner Read/Write/Execute (`rwx`), Group Read/Execute (`r-x`), and World Read/Execute (`r-x`). Any user with write permissions in a directory can delete any file within that directory, regardless of who owns the file!
* `1755` activates the **Sticky Bit (`S_ISVTX`, octal 1000)**. When set on a directory, the kernel restricts file deletion and renaming: a user can only delete or rename a file if they are the **owner of the file**, the **owner of the directory**, or `root`. This prevents users from deleting each other's files in public shared directories like `/tmp`.

### Question 2: Why is the `umask` formula NOT simple subtraction?
**Exhaustive Answer**:
* If `umask` were subtraction, subtracting `027` from `0666` would mathematically yield `0639`. But `9` is an invalid octal digit (octal only allows 0 through 7)!
* Even if individual digits were clamped, subtracting `022` from `0644` would yield `0622`. However, subtracting write permissions from a file that never had write permissions would corrupt the other permission bits.
* The true POSIX operation is bitwise masking: `Mode & (~umask)`. It only turns bits OFF; it never turns bits on or borrows across octal columns.

---

## 8. Complete Verification Checklist (Zero Gaps)
- [ ] Draw the 16-bit layout of `st_mode` and identify the bits for file types vs SUID/SGID.
- [ ] What is the exact bitwise operation used to compute final permissions with `umask`?
- [ ] Explain how SUID binaries switch Effective UID while preserving Real UID.
- [ ] Why is `/tmp` configured with permission `1777` instead of `0777`?
- [ ] What is a TOCTOU race condition and how does `open(..., O_CREAT | O_EXCL)` prevent it?
