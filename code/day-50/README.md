# Day 50: POSIX chroot Isolation & Security Boundary Engine

## 1. What Are We Building & Why Does It Matter?
In Linux emergency rescue workflows, when a system fails to boot, you boot from a rescue USB, mount the broken disk to `/mnt`, and enter it via `chroot /mnt`.
- `chroot` changes the root directory path resolution anchor (`/`) for the current process and its children.
- To repair a system inside a chroot jail (running `grub-install` or `apt`), you **must bind-mount the 4 virtual pseudo-filesystems**: `/dev`, `/proc`, `/sys`, and `/run`.
- Crucially, **`chroot` is an administrative rescue tool, NOT a security sandbox**. If a process inside a chroot runs as root (`UID 0`), it can easily escape using the classic directory file descriptor leak exploit!

In this lab, we build a **chroot Isolation and Escape Simulation Engine** in pure Python that models virtual path anchoring, bind-mount virtualization, and escape mechanics.

---

## 2. Python Concepts for Beginners

### A. Path String Manipulation
To safely join paths and prevent double-slash artifacts (`//`):
```python
clean_path = (root.rstrip('/') + '/' + path.lstrip('/')).replace('//', '/')
```

### B. Python Dictionaries for Mount Tables
We model the Linux kernel's VFS mount table using a dictionary mapping target directories to source device nodes:
```python
mounts = {"/mnt/proc": "/proc", "/mnt/dev": "/dev"}
```

### C. Exploit Modeling with Assertions
We prove security theorems using `assert`. In our escape demonstration, we assert that the attacker's resolved path does *not* contain the jail path, mathematically proving that the boundary was breached!

---

## 3. Step-by-Step Code Walkthrough

1. **`SimulatedVFS`**: Models the virtual filesystem with root anchor (`root_anchor`), current working directory (`cwd`), and mount table.
2. **`resolve_path()`**: Prepends the active root anchor to absolute paths.
3. **`ChrootEscapeSimulator`**: Simulates the classic CWD leak exploit where a process calls `chroot()` without updating its current working directory, allowing it to traverse upward into the host system.
4. **`main()` Function**: Validates anchored path resolution, bind-mount tables, and executes the escape vector simulation.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-50/chroot_jail_isolation_engine.py
```

Expected output:
```text
====================================================
DAY 50: POSIX chroot ISOLATION & ESCAPE SIMULATOR
====================================================
1. Path Resolution inside Jail:
   Requested Path : /etc/nginx/nginx.conf
   Resolved Path  : /srv/chroot/web/etc/nginx/nginx.conf
   [PASS] Path successfully anchored inside chroot directory.

2. Active Bind Mounts inside Jail:
   /dev -> /srv/chroot/web/dev
   /proc -> /srv/chroot/web/proc
   [PASS] Pseudo-filesystems (/proc, /dev) virtually bind-mounted.

3. Simulating Classic chroot Escape Vector:
   1. Host establishes chroot jail at: /tmp/guest_jail
   2. Bind-mounted essential pseudo-filesystems: /dev, /proc
   3. Process entered chroot jail, but CWD remained pointing outside the jail anchor!
   4. Attacker resolved path: '../etc/shadow' -> '/outside_leak/../etc/shadow'
   5. [EXPLOIT SUCCESS] Attacker accessed host filesystem outside chroot jail!

[VERIFIED] chroot isolation and security boundary simulation passed 100%!
```

---

## 5. Common Python Errors & Troubleshooting

- **Trailing Slash Bugs**: Path concatenation without `.rstrip('/')` results in paths like `/jail//etc/passwd`. Our helper strips redundant slashes.
- **Why Containers Use Namespaces**: Modern container runtimes (Docker, containerd) do not rely on `chroot`; they use Linux Mount Namespaces (`CLONE_NEWNS`) and Pivot Root (`pivot_root`) which cannot be escaped via CWD leaks.

---

## 6. Beginner Exercises & Challenges

1. **Secure chroot Wrapper**: Write a function `secure_chroot(target)` that calls `chroot()` and immediately enforces `chdir('/')`, closing the CWD leak vector.
2. **Automate Mount Script**: Write a function that outputs the exact `mount --bind` shell commands required to prepare `/mnt` for emergency recovery.
3. **Unmount Cleanup**: Write an `unmount_all()` function that tears down mounts in reverse order before exiting.
