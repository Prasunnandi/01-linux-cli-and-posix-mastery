# 🔗 Day 4: Pipes (`|`), Named FIFOs & IPC Internals

> **Zero External Dependency Guarantee**: This document is an exhaustive, encyclopedic masterclass. It contains complete historical context, Linux kernel C structures (`struct pipe_inode_info`), `PIPE_BUF` atomicity mathematical proofs, the classic pipe deadlock bug, production CI/CD freeze post-mortems, and FAANG technical interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & Historical Context

In 1973, Douglas McIlroy invented the **Unix Pipe (`|`)** at Bell Laboratories.
Prior to this, joining two programs required saving the intermediate output to a physical disk file:
```bash
# The Dark Ages (Slow, wears down disks, manual cleanup required):
program1 > temp_data.txt
program2 < temp_data.txt
rm temp_data.txt
```
McIlroy asked: *"Why write temporary bytes to a spinning magnetic platter when both programs are running concurrently in RAM?"*

He created the Pipe: a unidirectional inter-process communication (IPC) channel managed directly by the operating system kernel. The Unix pipe was so revolutionary that it was immediately integrated into the Unix kernel in a single weekend by Ken Thompson, forever changing the architecture of modern operating systems.

---

## 2. Kernel Architecture: How Linux Implements Pipes in Physical RAM

When you execute a pipe in Linux, **no disk files are created**. The kernel allocates a dedicated data structure in physical memory.

```
                                  LINUX KERNEL MEMORY SPACE
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                               struct pipe_inode_info                                      │
│                                                                                           │
│   ├── head = 4  (Index where WRITER puts new bytes)                                       │
│   ├── tail = 1  (Index where READER consumes bytes)                                       │
│   ├── max_usage = 16 (Number of memory pages allocated)                                   │
│   │                                                                                       │
│   └── struct pipe_buffer bufs[16]  (CIRCULAR ARRAY OF MEMORY PAGES)                       │
│       ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐   │
│       │ Page 0  │ Page 1  │ Page 2  │ Page 3  │ Page 4  │ Page 5  │ ....... │ Page 15 │   │
│       │ (4 KB)  │ (4 KB)  │ (4 KB)  │ (4 KB)  │ (4 KB)  │ (4 KB)  │         │ (4 KB)  │   │
│       └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘   │
│                      ▲                             ▲                                      │
│                      │                             │                                      │
└──────────────────────┼─────────────────────────────┼──────────────────────────────────────┘
                       │                             │
                read() │                             │ write()
                       │                             │
             ┌─────────────────┐             ┌─────────────────┐
             │   PROCESS B     │             │   PROCESS A     │
             │    (grep)       │             │     (cat)       │
             │ stdin = FD 0    │             │ stdout = FD 1   │
             └─────────────────┘             └─────────────────┘
```

### The Anatomy of `struct pipe_inode_info`:
Inside the Linux kernel source (`include/linux/pipe_fs_i.h`), a pipe is managed as a **Circular Ring Buffer of Memory Pages**:
1. **Pages in RAM**: Linux allocates an array of `struct pipe_buffer` entries. Each entry references a physical 4KB memory page (`PAGE_SIZE = 4096 bytes`).
2. **Standard Capacity**: On modern Linux (version 2.6.11+), a pipe defaults to **16 pages = 64 Kilobytes** (`65,536 bytes`).
3. **Head and Tail Pointers**:
   * The writing process pushes bytes to `head`.
   * The reading process consumes bytes from `tail`.
4. **Automatic Sleep & Wakeup (Zero CPU Polling)**:
   * **When the Pipe is Full (64KB buffered)**: If Process A writes faster than Process B can read, the kernel puts Process A to sleep (`TASK_INTERRUPTIBLE`) on a wait queue.
   * **When the Pipe is Empty (0 bytes buffered)**: If Process B tries to read, the kernel puts Process B to sleep until Process A writes at least 1 byte!
   * Neither process wastes CPU cycles in a spin-lock polling loop.

---

## 3. The `PIPE_BUF` Law: Atomicity Guarantees

In multithreaded or multi-process systems, multiple processes can write to the same pipe simultaneously.  
What prevents their messages from being scrambled together like: `HWeolrllod`?

### The POSIX `PIPE_BUF` Specification:
* **The Law**: Writes of **up to `PIPE_BUF` bytes** are guaranteed by the operating system kernel to be **atomic**.
* On Linux, `PIPE_BUF` is strictly **4,096 bytes** (4KB).
* **What this means in practice**:
  * If Process 1 writes a 2KB message, and Process 2 writes a 3KB message: The kernel guarantees that one message will appear completely, followed by the other message. They will **never** be interleaved!
  * If Process 1 writes **10KB** ($> \text{PIPE\_BUF}$): The kernel may break the message into chunks, and Process 2's bytes may be interleaved into the middle of Process 1's data!

---

## 4. Anonymous Pipes vs Named Pipes (FIFOs)

POSIX provides two distinct flavors of pipes:

```
┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
│            ANONYMOUS PIPES (`|`)             │             NAMED PIPES (FIFOs)              │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Created in code via `pipe()` syscall         │ Created on disk via `mkfifo my_pipe`         │
│ Has no name or presence on the filesystem    │ Exists as a special inode on disk (`p` flag) │
│ Can ONLY connect Parent & Child processes    │ Can connect completely unrelated processes   │
│ Destroyed automatically when processes exit  │ Persists on disk until explicitly deleted    │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

### How to Use a Named FIFO in Terminal:
```bash
# Terminal 1: Create the named pipe and wait for data
mkfifo /tmp/event_stream
cat < /tmp/event_stream

# Terminal 2: In a completely separate window or script:
echo "Important Event Alert!" > /tmp/event_stream
```
* Notice: The writing process in Terminal 2 will block and wait until Terminal 1 opens the read end. As soon as both ends are open, bytes flow through RAM and Terminal 1 prints the message!

---

## 5. The Dreaded Pipe Deadlock Bug (The Zombie Hang)

This is the single most common bug written by junior systems engineers when implementing sub-processes:

```
   PARENT PROCESS                                CHILD PROCESS
 (Spawns Child)                                 (Executes cat)
       │                                               │
       ├── Calls pipe(fds) ──► Creates FD 3 & FD 4     │
       ├── Calls fork()    ──► Inherits FD 3 & FD 4 ───┤
       │                                               │
       │                                               ▼
       │                                         Rewires FD 3 to stdin
       │                                         Closes FD 4 (write end)
       │                                         Starts reading from stdin...
       ▼                                               │
  FORGETS TO CLOSE FD 4!                               ▼
  Calls waitpid(child)...                              Wants to reach EOF (read() == 0)...
  [PARENT SLEEPS FOREVER]                              BUT FD 4 IS STILL OPEN IN PARENT!
                                                       [CHILD WAITS ON READ() FOREVER!]
                                                       
                             ★★★ DEADLOCK! ★★★
```

### Why Did This Freeze?
* A reader process only receives **End-of-File (`read() == 0`)** when **ALL open write descriptors across the entire operating system are closed**.
* Because the parent forgot to call `close(pipefd[1])`, the operating system assumes the parent might write more bytes in the future.
* The child waits on `read()` forever. The parent waits on `waitpid()` for the child to exit. **The system is deadlocked and freezes permanently!**

---

## 6. The `SIGPIPE` Signal & Broken Pipes

What happens if a program tries to write to a pipe whose reading process has already died or closed its file descriptor?

1. If you run: `cat /dev/urandom | head -n 1`
2. `head -n 1` reads the first line and immediately exits. Its file descriptors are closed by the kernel.
3. `cat` tries to write another chunk of bytes to the pipe.
4. The Linux kernel detects that the read-end of the pipe has 0 open descriptors.
5. The kernel generates a **`SIGPIPE` (Signal 13 - Broken Pipe)** and sends it to `cat`, terminating it instantly!
6. If the process has ignored `SIGPIPE` via `signal(SIGPIPE, SIG_IGN)`, the `write()` system call fails and sets `errno = EPIPE`.

---

## 7. Real-World Production War Story: The 6-Hour CI/CD Build Freeze

### The Incident:
In 2021, an automated continuous integration (CI/CD) worker cluster at a financial software firm began freezing randomly on large pull requests. Builds that normally took 3 minutes hung for 6 hours until killed by timeouts.

### What Happened Under the Hood:
A test script executed a background subprocess:
```python
proc = subprocess.Popen(["mvn", "test"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
# The developer read stdout first:
stdout_data = proc.stdout.read()
# Then read stderr:
stderr_data = proc.stderr.read()
```
The test suite produced heavy logging. The Java process outputted **70 Kilobytes of error warnings** to `stderr`.  
Because the Linux kernel pipe buffer is strictly **64 Kilobytes**, once `stderr` reached 64KB, the kernel put the Java process to sleep waiting for someone to read `stderr`.  
Meanwhile, the Python script was blocked waiting for `stdout.read()` to finish!  
Python was waiting for Java to exit; Java was waiting for Python to read `stderr`. **A classic dual-pipe buffer deadlock!**

### The Production Fix:
Never read independent standard streams sequentially in a blocking fashion! Use `proc.communicate()` (which uses background threads or `select()`/`epoll` to drain both buffers concurrently) or merge them with `stderr=subprocess.STDOUT`.

---

## 8. Staff-Level Technical Interview Deep-Dives

### Question 1: How do you change the buffer size of a pipe in Linux programmatically?
**Exhaustive Answer**:
* Using the `fcntl()` system call with the `F_SETPIPE_SZ` command:
  ```c
  int new_size = fcntl(pipefd[0], F_SETPIPE_SZ, 1048576); // Set to 1MB
  ```
* The size must be a power of 2. An unprivileged user can increase the pipe capacity up to the limit set in `/proc/sys/fs/pipe-max-size` (typically 1MB). Only `root` can exceed this limit.

### Question 2: What is the difference between a Unix Domain Socket and a Named Pipe (FIFO)?
**Exhaustive Answer**:
* **Directionality**: A pipe (or FIFO) is strictly **unidirectional** (simplex). Two-way communication requires opening two separate pipes. A Unix Domain Socket (`AF_UNIX`) is fully **bidirectional** (full-duplex).
* **Connection Model**: Unix Domain Sockets support client-server connection lifecycles (`listen()`, `accept()`, `connect()`) and can pass open file descriptors and OS user credentials (`SO_PEERCRED`) between processes, which pipes cannot do.

---

## 9. Complete Verification Checklist (Zero Gaps)
Before marking Day 4 as completed in your tracker, verify that you can answer these without looking:
- [ ] Can you explain the internal structure of `struct pipe_inode_info` and the 64KB circular page buffer?
- [ ] What is the POSIX `PIPE_BUF` atomicity guarantee, and what happens to writes larger than 4KB?
- [ ] Can you explain the exact mechanism of the classic Pipe Deadlock bug where parent and child sleep forever?
- [ ] What triggers the `SIGPIPE` signal and what error code does `write()` return when `SIGPIPE` is ignored?
