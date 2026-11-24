# Day 12: Inodes, Hard Links vs Soft Links (stat, ln)

## 1. Architectural Foundations: The Inode (Index Node)

In the Unix philosophy, "everything is a file." However, the operating system kernel does not recognize human-readable filenames like `financial_report.csv`. Internally, the Linux Virtual Filesystem (VFS) and storage engines (such as ext4 and XFS) identify every object using a numerical metadata structure known as the **Index Node** or **Inode**.

An Inode stores all metadata describing a file, **except its filename and actual data content**.

```
+-------------------------------------------------------------------------+
|                  ext4 Inode On-Disk Structure (256 Bytes)               |
+-------------------------------------------------------------------------+
| Field               | Size    | Description                             |
+---------------------+---------+-----------------------------------------+
| i_mode              | 2 bytes | File Type (regular, dir, symlink) + ACL |
| i_uid / i_gid       | 4 bytes | Owner User ID and Group ID              |
| i_size_lo / hi      | 8 bytes | File Size in Bytes (supports 64-bit)    |
| i_atime             | 4 bytes | Last Access Time                        |
| i_ctime             | 4 bytes | Last Status Change Time (metadata)      |
| i_mtime             | 4 bytes | Last Modification Time (content)        |
| i_dtime             | 4 bytes | Deletion Time                           |
| i_links_count       | 2 bytes | Reference Count of Hard Links           |
| i_blocks_lo / hi    | 8 bytes | Number of 512-Byte Storage Blocks       |
| i_flags             | 4 bytes | Ext4 Flags (immutable, append-only)     |
| i_block[EXT4_N_BLKS]| 60 bytes| Extent Tree Root or Block Pointers      |
| i_extra_isize       | 2 bytes | Extra Inode Size for Nanosecond Timestamps|
+---------------------+---------+-----------------------------------------+
```

### 1.1 How Filenames Work: Directory Entries (Dentries)
A directory in Linux is fundamentally just a specialized file whose payload is a list of directory entries (**dentries**). Each dentry maps a string filename to an Inode number:

```
Directory File: /home/alice
+-------------------+----------------+
| Inode Number      | Filename       |
+-------------------+----------------+
| 1441792           | .              |
| 2                 | ..             |
| 1441795           | document.txt   |
| 1441799           | script.sh      |
+-------------------+----------------+
```

When a process calls `open("/home/alice/document.txt", O_RDONLY)`:
1. The VFS reads root Inode `2` to find the location of `/`.
2. It parses `/` directory blocks to find entry `home` (Inode `524288`).
3. It parses `/home` directory blocks to find entry `alice` (Inode `1441792`).
4. It parses `/home/alice` directory blocks to find entry `document.txt`, discovering Inode `1441795`.
5. It inspects Inode `1441795` for read permissions and loads data blocks into the Page Cache.

---

## 2. Hard Links vs Symbolic (Soft) Links

Linux provides two distinct mechanisms for referencing files: **Hard Links** and **Symbolic Links**. Understanding their kernel representation is essential for systems programming and data integrity.

```
                    +---------------------------------------+
                    |           HARD LINK MECHANICS         |
                    +---------------------------------------+
                    
   Dentry: "file1.txt"                  Dentry: "file1_hard.txt"
   Inode Ref: 881204                    Inode Ref: 881204
            \                                  /
             \                                /
              v                              v
            +----------------------------------+
            |        Inode Number 881204       |
            | - Size: 4096 bytes               |
            | - Links Count: 2                 |
            | - Data Block Pointer: Block 9912 |
            +----------------------------------+
                             |
                             v
                    [ Data Block 9912 ]
                    "Hello Production!"


                    +---------------------------------------+
                    |         SOFT (SYMBOLIC) LINK          |
                    +---------------------------------------+

   Dentry: "file1.txt"                  Dentry: "file1_sym.lnk"
   Inode Ref: 881204                    Inode Ref: 994511
            |                                    |
            v                                    v
   +------------------+                 +------------------+
   |   Inode 881204   |                 |   Inode 994511   |
   | Links Count: 1   |                 | File Type: Symlink|
   | Block: 9912      |                 | Target: file1.txt|
   +------------------+                 +------------------+
            |
            v
   [ Data Block 9912 ]
```

### 2.1 Technical Comparison Table

| Attribute | Hard Link (`ln target link`) | Soft/Symbolic Link (`ln -s target link`) |
| :--- | :--- | :--- |
| **Inode Number** | Identical to target file Inode | Brand new, unique Inode allocated |
| **Storage Usage** | Zero additional disk blocks (new dentry only) | Uses small inode/block storage to store path |
| **Cross-Filesystem**| **IMPOSSIBLE** (Inodes are local to partition) | **POSSIBLE** (Stores path string) |
| **Link to Directory**| Forbidden in Linux (prevents cycles/loops) | Permitted |
| **Target Deleted** | File data preserved; link count decremented | Becomes a **Dangling Link** (Broken reference)|
| **Permissions** | Shared with target (same inode) | `lrwxrwxrwx` (Kernel evaluates target permissions)|
| **System Calls** | `link()` | `symlink()` |

### 2.2 Mathematical Proof: Why Hard Links Cannot Cross Filesystems
Every storage partition format (e.g. `/dev/sda1` on `/` vs `/dev/sdb1` on `/data`) initializes its own independent **Inode Table**.
- In `/dev/sda1`, Inode `105` may reference `/etc/passwd`.
- In `/dev/sdb1`, Inode `105` may reference an arbitrary database block or picture.

Because a directory entry only records an integer Inode number, creating a hard link across filesystems would point to an arbitrary, uncoordinated Inode on the target filesystem. Hence, the VFS checks `old_dentry->d_sb == new_dentry->d_sb`. If the superblock pointers differ, the kernel immediately aborts with `EXDEV` (**Invalid cross-device link**).

---

## 3. Dissecting `stat` and Inode Exhaustion

The `stat` utility directly reads an Inode's metadata fields using the `statx()` or `stat()` system call:

```bash
$ stat production.log
  File: production.log
  Size: 10485760   	Blocks: 20480      IO Block: 4096   regular file
Device: 801h/2049d	Inode: 2883921     Links: 1
Access: (0644/-rw-r--r--)  Uid: ( 1000/   alice)   Gid: ( 1000/   alice)
Access: 2026-11-23 08:30:00.124589123 +0000
Modify: 2026-11-23 08:29:55.981245100 +0000
Change: 2026-11-23 08:29:55.981245100 +0000
 Birth: 2026-11-23 08:00:00.000000000 +0000
```

### Understanding Timestamps:
- **`Access` (`atime`)**: Last time the file was read via `read()` or `execve()`. (Frequently configured with `noatime` or `relatime` in `/etc/fstab` to eliminate write amplification).
- **`Modify` (`mtime`)**: Last time file *content* was modified via `write()` or `truncate()`.
- **`Change` (`ctime`)**: Last time file *metadata or inode properties* were changed (e.g. `chmod`, `chown`, link count change). **`ctime` cannot be forged by user processes.**
- **`Birth` (`crtime`)**: Creation timestamp (supported in ext4 and Btrfs via `statx`).

### 3.1 The "Disk Full" Inode Exhaustion Catastrophe
A filesystem can completely run out of space even if terabytes of free disk space remain!
When ext4 is formatted via `mkfs.ext4`, it preallocates a fixed number of Inodes based on partition size. If an application generates millions of zero-byte or tiny files (e.g. unpruned PHP session files or microservice logs), every Inode is consumed.

```bash
# Check block space usage:
$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   12G   38G  24% /

# Check Inode usage:
$ df -i /
Filesystem      Inodes   IUsed   IFree IUse% Mounted on
/dev/sda1      3276800 3276800       0  100% /   <-- DISK IS FULL!
```
When Inode utilization reaches $100\%$, any attempt to create a file (`touch`, `mkdir`, `creat()`) fails with `ENOSPC` (**No space left on device**), crashing databases and daemons.

---

## 4. Production War Story: The Unlinked Open File Disk Leak

A high-frequency trading platform reported that its `/var/log` partition was running out of disk space (`98%` capacity). SREs ran `rm /var/log/trading_engine.log` to delete a $40\text{ GB}$ log file. 

### The Mystery
Running `df -h /var/log` still showed $98\%$ disk utilization! However, running `ls -l /var/log/` showed that the file was completely gone. Where did the $40\text{ GB}$ go?

### Kernel Mechanics Explained
When `rm` is executed, it calls the `unlink()` system call. `unlink()` removes the directory entry mapping and decrements the Inode's `i_links_count`. However:
**The Linux kernel will NOT deallocate a file's physical data blocks while any process holds an active open File Descriptor pointing to that Inode!**

Because the trading engine daemon was still running and writing to file descriptor `3`, `i_links_count` dropped from $1$ to $0$, but the kernel kept the data blocks allocated on disk.

### The Diagnostic & Resolution
1. **Find Unlinked Open Files**:
   ```bash
   lsof | grep deleted
   trading_e  4812  root    3w   REG  8,1  42949672960  184912 /var/log/trading_engine.log (deleted)
   ```
2. **Reclaim Disk Space Without Stopping Daemon**:
   Truncate the unlinked file through the `/proc` virtual filesystem:
   ```bash
   : > /proc/4812/fd/3
   ```
   The kernel immediately truncated the allocated ext4 extent blocks to $0$ bytes, freeing $40\text{ GB}$ instantly while allowing the production daemon to continue operating uninterrupted.
