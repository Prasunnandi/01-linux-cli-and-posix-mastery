# Day 12: Inodes, Hard Links vs Soft Links (stat, ln)

## 1. Architectural Foundations: The Virtual Filesystem (VFS) Layer
In the Unix file system design, a file's name and location in the directory tree are completely decoupled from its metadata and storage blocks. The abstraction that bridges human-readable pathnames and physical disk storage consists of three fundamental kernel data structures:

```
+----------------------------------------------------------------------------+
|                         VFS (Virtual Filesystem)                           |
+----------------------------------------------------------------------------+
       |                                                |
       v                                                v
+-------------------+                            +-------------------+
| struct dentry     |                            | struct dentry     |
| d_name = "file.txt"                            | d_name = "hardlink"
| d_inode ---------\                            / | d_inode ----------+
+-------------------\--------------------------/---------------------+
                     |                        |
                     v                        v
            +---------------------------------------+
            | struct inode                          |
            | i_ino = 142981                        |
            | i_nlink = 2                           |
            | i_mode = 0100644 (S_IFREG | 0644)     |
            | i_uid = 1000, i_gid = 1000            |
            | i_size = 4096 bytes                   |
            | i_blocks = 8 (512-byte sectors)       |
            | i_atime, i_mtime, i_ctime             |
            | Direct & Extent Tree Pointers ------> [ Data Blocks on Disk ]
            +---------------------------------------+
```

### The Inode (`struct inode`)
The index node (inode) represents a unique filesystem object. It contains all metadata describing the file EXCEPT its name:
- **Inode Number (`i_ino`)**: An unsigned 32-bit or 64-bit integer unique within the filesystem superblock.
- **Link Count (`i_nlink`)**: The number of directory entries (`dentry`) that point to this inode. A file's storage blocks are not deallocated until `i_nlink == 0` AND all open file descriptors referencing the inode are closed.
- **Type and Permissions (`i_mode`)**: Encodes the file type (regular file `S_IFREG`, directory `S_IFDIR`, symlink `S_IFLNK`, block device `S_IFBLK`, character device `S_IFCHR`, FIFO `S_IFIFO`, or socket `S_IFSOCK`) and POSIX permission bits (rwxrwxrwx).
- **Ownership (`i_uid`, `i_gid`)**: Numeric user and group IDs.
- **Size (`i_size`)**: Logical file size in bytes.
- **Allocated Disk Blocks (`i_blocks`)**: Number of 512-byte blocks allocated on disk (distinguishing sparse files from dense files).
- **Timestamps**:
  - `atime` (Access Time): Last time file contents were read.
  - `mtime` (Modification Time): Last time file contents were altered.
  - `ctime` (Change Time): Last time inode metadata or permissions were modified (cannot be manually forged with `utime()`).

### The Directory Entry (`struct dentry`)
A directory is simply a special file containing an array of directory entries. Each entry is a mapping:
$$\text{Dentry} = (\text{filename}, \text{inode\_number})$$
When a process opens `/home/user/data.csv`, the kernel traverses the directory tree starting from root (`/`, inode 2 in ext4), reading dentries at each path component until the final inode is resolved.

---

## 2. Hard Links vs Symbolic (Soft) Links

| Metric / Property | Hard Link (`ln target link`) | Symbolic Link (`ln -s target link`) |
| :--- | :--- | :--- |
| **Inode Identity** | Identical inode number (`link.i_ino == target.i_ino`) | Distinct new inode allocated (`link.i_ino != target.i_ino`) |
| **Link Count (`i_nlink`)** | Increments target inode's `i_nlink` by 1 | Target inode `i_nlink` is unchanged; symlink inode has `i_nlink = 1` |
| **Cross-Filesystem** | **IMPOSSIBLE**. Inode numbers are only local to a superblock. | **POSSIBLE**. Contains arbitrary text pathname string. |
| **Directories** | Forbidden to userspace (prevents cycles in DAG). | Allowed (can point to directories). |
| **Target Deletion** | Target data remains accessible via link; blocks intact. | Becomes dangling / broken link (points to non-existent path). |
| **Storage Overhead** | Exactly 0 extra disk blocks (adds one dentry to directory). | Fast symlink: 0 blocks (< 60 bytes stored in inode `i_block`). Slow: 1 block. |
| **Kernel Resolution** | Direct dereference via dentry cache. | Kernel must resolve path string recursively (up to `SYMLOOP_MAX = 40`). |

### Fast Symlinks vs Slow Symlinks
In ext4 filesystems, an inode has a 60-byte data field (`i_block` array) originally used for direct and indirect block pointers.
- **Fast Symlink**: If the symlink target pathname is less than 60 bytes (including the null terminator), ext4 stores the target string directly inside the inode's `i_block` array. Zero data blocks are allocated on disk!
- **Slow Symlink**: If the target pathname is $\ge 60$ bytes, ext4 allocates a dedicated data block on disk, writes the path string there, and points the inode's extent tree to that block.

### Directory Link Count Rules
For any directory `mydir`:
$$i\_nlink(\text{mydir}) = 2 + \text{Number of Immediate Subdirectories}$$
Why?
1. The parent directory contains an entry for `mydir` ($+1$).
2. The directory `mydir` contains an entry pointing to itself: `.` ($+1$).
3. Every immediate subdirectory inside `mydir` contains an entry pointing back to the parent: `..` ($+1$ for each).

---

## 3. POSIX System Calls: stat(), lstat(), readlink(), link(), unlink()

```c
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

struct stat {
    dev_t     st_dev;     /* ID of device containing file */
    ino_t     st_ino;     /* Inode number */
    mode_t    st_mode;    /* File type and mode */
    nlink_t   st_nlink;   /* Number of hard links */
    uid_t     st_uid;     /* User ID of owner */
    gid_t     st_gid;     /* Group ID of owner */
    dev_t     st_rdev;    /* Device ID (if special file) */
    off_t     st_size;    /* Total size, in bytes */
    blksize_t st_blksize; /* Block size for filesystem I/O */
    blkcnt_t  st_blocks;  /* Number of 512B blocks allocated */
    struct timespec st_atim;  /* Time of last access */
    struct timespec st_mtim;  /* Time of last modification */
    struct timespec st_ctim;  /* Time of last status change */
};
```
- `stat(pathname, &sb)`: Dereferences symbolic links. If `pathname` is a symlink, returns the metadata of the file the symlink points to.
- `lstat(pathname, &sb)`: Does NOT dereference symbolic links. Returns the metadata of the symlink file itself!
- `readlink(pathname, buf, bufsiz)`: Reads the content (target path) of a symbolic link without following it.
- `link(oldpath, newpath)`: Creates a hard link pointing to the inode of `oldpath`.
- `unlink(pathname)`: Removes a dentry. Decrements the referenced inode's `i_nlink`. If `i_nlink == 0` and no process has it open, the kernel frees the blocks.

---

## 4. Production Masterclass: Compilable C Program

Save as `inode_inspector.c` and compile with `gcc -Wall -Wextra -O2 inode_inspector.c -o inode_inspector`:

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <time.h>

void print_file_stat(const char *label, const char *path) {
    struct stat sb;
    if (lstat(path, &sb) == -1) {
        fprintf(stderr, "[-] lstat failed on %s: %s\\n", path, strerror(errno));
        return;
    }

    printf("====================================================\\n");
    printf("STAT REPORT: %s (%s)\\n", label, path);
    printf("====================================================\\n");
    printf("  Device ID (st_dev)    : Major=%ld, Minor=%ld\\n",
           (long)major(sb.st_dev), (long)minor(sb.st_dev));
    printf("  Inode Number (st_ino) : %llu\\n", (unsigned long long)sb.st_ino);
    printf("  Hard Link Count       : %lu\\n", (unsigned long)sb.st_nlink);
    printf("  Logical Size          : %lld bytes\\n", (long long)sb.st_size);
    printf("  Disk Blocks (512B)    : %lld blocks (%lld physical bytes)\\n",
           (long long)sb.st_blocks, (long long)sb.st_blocks * 512);

    // Decode File Type
    const char *ftype = "Unknown";
    if (S_ISREG(sb.st_mode))  ftype = "Regular File";
    else if (S_ISDIR(sb.st_mode))  ftype = "Directory";
    else if (S_ISLNK(sb.st_mode))  ftype = "Symbolic Link";
    else if (S_ISCHR(sb.st_mode))  ftype = "Character Device";
    else if (S_ISBLK(sb.st_mode))  ftype = "Block Device";
    else if (S_ISFIFO(sb.st_mode)) ftype = "FIFO/Named Pipe";
    else if (S_ISSOCK(sb.st_mode)) ftype = "Socket";

    printf("  File Type             : %s\\n", ftype);
    printf("  POSIX Permissions     : %04o\\n", sb.st_mode & 07777);

    // If symlink, inspect its raw target
    if (S_ISLNK(sb.st_mode)) {
        char link_target[1024];
        ssize_t len = readlink(path, link_target, sizeof(link_target) - 1);
        if (len != -1) {
            link_target[len] = '\\0';
            printf("  Symlink Points To     : \"%s\"\\n", link_target);
            printf("  Storage Location      : %s\\n",
                   sb.st_blocks == 0 ? "Fast Symlink (inside inode i_block)" : "Slow Symlink (data block)");
        }
    }
}

int main(void) {
    const char *orig_file = "test_original.bin";
    const char *hard_link = "test_hardlink.bin";
    const char *soft_link = "test_softlink.bin";

    // Clean up any stale artifacts
    unlink(orig_file);
    unlink(hard_link);
    unlink(soft_link);

    printf("[+] Step 1: Creating original file '%s' (8192 bytes)...\\n", orig_file);
    int fd = open(orig_file, O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd < 0) { perror("open"); return 1; }
    char buffer[4096];
    memset(buffer, 0xAA, sizeof(buffer));
    write(fd, buffer, sizeof(buffer));
    write(fd, buffer, sizeof(buffer));
    close(fd);

    print_file_stat("Original File Initial", orig_file);

    printf("\\n[+] Step 2: Creating hard link '%s' -> '%s'...\\n", hard_link, orig_file);
    if (link(orig_file, hard_link) == -1) {
        perror("link");
    }
    print_file_stat("Original File After Hardlink", orig_file);
    print_file_stat("Hard Link", hard_link);

    printf("\\n[+] Step 3: Creating symbolic link '%s' -> '%s'...\\n", soft_link, orig_file);
    if (symlink(orig_file, soft_link) == -1) {
        perror("symlink");
    }
    print_file_stat("Original File After Symlink", orig_file);
    print_file_stat("Symbolic Link", soft_link);

    printf("\\n[+] Step 4: Deleting (unlinking) original file '%s'...\\n", orig_file);
    unlink(orig_file);

    print_file_stat("Hard Link After Original Unlinked", hard_link);
    print_file_stat("Symbolic Link After Original Unlinked (Dangling)", soft_link);

    // Clean up
    unlink(hard_link);
    unlink(soft_link);
    printf("\\n[+] Demonstration successfully concluded.\\n");
    return 0;
}
```

---

## 5. Production Post-Mortem: The Ghost Disk Full Incident
### The Outage
A high-throughput Cassandra cluster node triggered an emergency alert: `Disk Space Usage: 100% (/var/log partition)`.
An on-call engineer connected to the node, ran `du -sh /var/log/*`, and observed only 1.2 GB of disk usage. Yet `df -h /var/log` reported:
```
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p2  200G  198G     0 100% /var/log
```
The engineer ran `rm -f /var/log/cassandra/system.log`, expecting 50 GB to be reclaimed immediately. Nothing changed: `df -h` still showed 100% full. New database writes stalled, and the node collapsed into a crash loop.

### Root Cause Analysis
The filesystem releases an inode's storage blocks if and only if two conditions are met simultaneously:
1. `inode->i_nlink == 0` (all directory entries have been unlinked).
2. `inode->i_count == 0` (the kernel reference count in the open file table reaches zero, meaning no active processes have open file descriptors to the inode).

The engineer used `rm`, which invokes `unlink("/var/log/cassandra/system.log")`. This successfully decremented `i_nlink` from 1 to 0 and removed the dentry from the directory tree. Consequently, `du` (which traverses the directory tree using `opendir`/`readdir`) could no longer see the file!
However, the active Cassandra JVM process still held an open file descriptor (`fd = 19`) to that unlinked inode. The inode remained pinned in kernel memory, and the 50 GB of disk blocks remained reserved and active!

### Diagnostic Verification
```bash
# Locate all open file descriptors referencing deleted inodes
lsof +L1 /var/log
# OR via procfs:
ls -l /proc/*/fd/* | grep '(deleted)'
```
Output:
```
COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF   NODE NAME
java    18241 cass   19w   REG  259,2 52428800000 142091 /var/log/cassandra/system.log (deleted)
```

### Remediation & Permanent Architectural Fix
1. **Immediate Zero-Downtime Release**: Instead of attempting to kill the critical service, truncate the unlinked file through `/proc`:
   ```bash
   # Truncate the file via the process's file descriptor entry in procfs:
   : > /proc/18241/fd/19
   ```
   This invokes `ftruncate()`, releasing all extents back to the free block bitmap without restarting Cassandra.
2. **Proper Log Rotation Architecture**:
   Never use `rm` on active log files. Use `logrotate` with `copytruncate` or configure services to respond to `SIGHUP` (e.g. Nginx `kill -USR1`) to reopen their file descriptors after rename.
