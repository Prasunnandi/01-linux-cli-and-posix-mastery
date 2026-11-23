# 01-linux-cli-and-posix-mastery

> **Curriculum Track**: Pair 1 (Days 1 - 100) [Primary Track]  
> **Topic**: Linux CLI, POSIX Streams, File Descriptors, Signals & Unix Tools  
> **Target**: 100 Days | Zero Knowledge Gap | Self-Contained Textbook & Simulation Suite

---

## 📌 Executive Summary
Master the Unix terminal from absolute zero. Understand how the Linux kernel exposes hardware and processes through file descriptors, pipes, signals, and POSIX streams. 100% self-contained study material with kernel C structures, mathematical derivations, production war stories, and working code simulation labs.

---

## 🎯 100-Day Milestones
- [x] **Milestone 1 (Days 1–5)**: Streams, File Descriptors, Redirection, Pipes & POSIX Permissions
- [x] **Milestone 2 (Days 6–10)**: Advanced Text Wrangling, External Sorting, procfs, Process States & Signals
- [ ] **Milestone 3 (Days 11–20)**: Memory Management, VFS, Virtual Memory, Inode Allocation & Hard/Soft Links
- [ ] **Milestone 4 (Days 21–40)**: Advanced Bash Scripting, Subshells, Environment & Systemd Daemons
- [ ] **Milestone 5 (Days 41–100)**: Rebuilding a Complete Unix Shell (`minish`), `fork/exec`, and POSIX C Systems Programming

---

## 📚 Curriculum Index (Days 1 – 10)

| Day | Topic | Textbook Notes | Hands-on Simulation Lab | Verification Status |
| :---: | :--- | :--- | :--- | :---: |
| **01** | Standard Streams & Redirection (`stdin`, `stdout`, `stderr`, `dup2`) | [day-01-streams-and-redirection.md](notes/day-01-streams-and-redirection.md) | [streams_demo.py](code/day-01/streams_demo.py) | ✅ Verified |
| **02** | Building `cat` & `wc` from Scratch (Buffer Streaming & Line/Word Math) | [day-02-building-cat-and-wc.md](notes/day-02-building-cat-and-wc.md) | [my_cat.py](code/day-02/my_cat.py) / [my_wc.py](code/day-02/my_wc.py) | ✅ Verified |
| **03** | Searching with `grep` (Thompson NFA Regex & Boyer-Moore String Matching) | [day-03-searching-with-grep.md](notes/day-03-searching-with-grep.md) | [my_grep.py](code/day-03/my_grep.py) | ✅ Verified |
| **04** | Pipes & FIFOs (`struct pipe_inode_info`, Circular Buffers & Atomicity) | [day-04-pipes-and-fifos.md](notes/day-04-pipes-and-fifos.md) | [pipeline_demo.py](code/day-04/pipeline_demo.py) | ✅ Verified |
| **05** | Permissions & Inodes (`st_mode`, Octal Bitmasks, SUID/SGID/Sticky Bits) | [day-05-permissions-and-inodes.md](notes/day-05-permissions-and-inodes.md) | [permission_checker.py](code/day-05/permission_checker.py) | ✅ Verified |
| **06** | Text Wrangling (`cut`, `awk`, `sed`, Pattern Space & Regex Substitutions) | [day-06-text-wrangling-cut-awk-sed.md](notes/day-06-text-wrangling-cut-awk-sed.md) | [log_wrangler.py](code/day-06/log_wrangler.py) | ✅ Verified |
| **07** | Sorting & Deduplication (External K-Way Merge Sort, Min-Heaps & `uniq`) | [day-07-sorting-and-deduplication.md](notes/day-07-sorting-and-deduplication.md) | [external_merge_sort_sim.py](code/day-07/external_merge_sort_sim.py) | ✅ Verified |
| **08** | FHS & Virtual Filesystems (`/proc`, `/sys`, VFS Hooks & `loadavg` EWMA) | [day-08-filesystem-hierarchy-proc.md](notes/day-08-filesystem-hierarchy-proc.md) | [proc_inspector.py](code/day-08/proc_inspector.py) | ✅ Verified |
| **09** | Process Lifecycle (`task_struct`, States `R, S, D, Z, T`, Zombies & Orphans) | [day-09-process-lifecycle-ps-top.md](notes/day-09-process-lifecycle-ps-top.md) | [process_tree_tracer.py](code/day-09/process_tree_tracer.py) | ✅ Verified |
| **10** | POSIX Signals & Shutdowns (`sigaction`, `SIGKILL` vs `SIGTERM`, Draining) | [day-10-signals-and-kill.md](notes/day-10-signals-and-kill.md) | [graceful_shutdown_daemon.py](code/day-10/graceful_shutdown_daemon.py) | ✅ Verified |

---

## 🚀 Daily Study Rule ("Side-by-Side Mode")
- Work on this repository strictly in tandem with its complementary pair repository: [`02-computer-networks-from-scratch`](https://github.com/Prasunnandi/02-computer-networks-from-scratch).
- Block A: Primary Systems (Linux) ~2 hours.
- Block B: Secondary Track (Computer Networks) ~1.5 hours.
- Complete the daily hands-on lab before moving to the next day.
