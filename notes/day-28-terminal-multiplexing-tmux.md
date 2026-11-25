# Day 28: Terminal Multiplexing: tmux Sessions & Panes

## 1. Architectural Foundations: The Pseudo-Terminal (PTY) Subsystem
To understand how terminal multiplexers like `tmux` decouple running programs from active SSH connections, one must understand the Linux **Pseudo-Terminal (PTY)** pair.

A PTY consists of two connected bidirectional character devices:
1. **PTY Master (`/dev/ptmx`)**: Controlled by the terminal emulator or daemon (e.g. `tmux` or `sshd`).
2. **PTY Slave (`/dev/pts/N`)**: Emulates a real hardware terminal. Programs like Bash, Vim, and SSH read input from and write output to this device.

```
[ Physical SSH Client ]
          |
     (TCP Network)
          v
[ sshd Daemon (Holds PTY Master 1) ] <----> [ /dev/pts/1 (Runs tmux client) ]
                                                            |
                                               (UNIX Domain Socket: /tmp/tmux-UID/default)
                                                            v
                                            [ tmux Server Daemon (Background) ]
                                                   |                     |
                                      (PTY Master A)              (PTY Master B)
                                             v                           v
                                      [ /dev/pts/10 ]             [ /dev/pts/11 ]
                                      (Runs vim in Pane 1)        (Runs htop in Pane 2)
```

---

## 2. tmux Architecture: Server, Clients, Sessions, Windows, Panes
- **tmux Server**: A persistent daemon that runs in the background. It manages PTY master devices for every window and pane.
- **tmux Client**: A lightweight program running inside your active terminal that renders the visual screen and forwards keyboard input to the tmux server via a local UNIX domain socket.
- **Detach (`Ctrl-b d`)**: Closes the tmux client and disconnects from the SSH terminal. The **tmux server and all running child processes continue executing uninterrupted**!
- **Attach (`tmux attach -t name`)**: Spawns a new client, connects to the server socket, and instantly restores the entire visual layout, scrollback history, and running programs.

---

## 3. Automation with Headless tmux
`tmux` can be fully scripted from Bash without interactive user intervention:

```bash
# 1. Start a new detached session running an API server:
tmux new-session -d -s prod_api "python3 -m http.server 8080"

# 2. Split window horizontally to run log monitoring:
tmux split-window -h -t prod_api "tail -f /var/log/syslog"

# 3. Send keystrokes directly into a running pane:
tmux send-keys -t prod_api:0.0 "ls -la" C-m

# 4. Capture text output from a pane for automated validation:
tmux capture-pane -pt prod_api:0.0 > /tmp/pane_dump.txt
```

---

## 4. Production Masterclass: Compilable C UNIX Domain Socket Client (Mock tmux Protocol)

Save as `mux_socket_client.c` and compile with `gcc -Wall -Wextra -O2 mux_socket_client.c -o mux_socket_client`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SOCKET_PATH "/tmp/mock_tmux.sock"

int main(void) {
    printf("====================================================\n");
    printf("TERMINAL MULTIPLEXER UNIX DOMAIN SOCKET CLIENT\n");
    printf("====================================================\n");

    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);

    printf("[+] Attempting connection to Multiplexer Daemon at %s...\n", SOCKET_PATH);
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        printf("[-] Daemon not running (Expected for standalone test). Path verified.\n");
        close(sock);
        return 0;
    }

    const char *cmd = "ATTACH_SESSION:prod_api\n";
    write(sock, cmd, strlen(cmd));

    char buf[256];
    ssize_t n = read(sock, buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        printf("[+] Server Response: %s\n", buf);
    }

    close(sock);
    return 0;
}
```

---

## 5. Production Post-Mortem: The Cloud Instance Reboot Session Loss
### The Outage
A DevOps engineer managed 4 long-running compilation builds inside tmux on an AWS EC2 instance. The cloud provider initiated an automated hypervisor reboot for security maintenance. All tmux sessions died because tmux stores runtime state strictly in volatile RAM.

### Architectural Fix
Install and configure `tmux-resurrect` and `tmux-continuum`:
- Periodically serializes window layouts, active directories, and running processes to `~/.tmux/resurrect/`.
- Automatically restores all sessions and windows upon system reboot via a systemd user unit.---

## 6. Industrial `.tmux.conf` Configuration for DevOps & Engineering
Out-of-the-box `tmux` uses awkward default bindings (e.g., `Ctrl-b` and Emacs navigation). The industry standard configuration adopts Vim keybindings, mouse support, and high-visibility status bars:

```tmux
# Change prefix from Ctrl-b to Ctrl-a (more ergonomic)
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# Enable true color support (24-bit color)
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:Tc"

# Enable mouse mode (clickable panes, scrolling)
set -g mouse on

# Vim-style pane splitting:
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

# Vim-style pane navigation (hjkl):
bind h select-pane -L
bind j select-pane -D
bind k select-pane -U
bind l select-pane -R

# Increase scrollback buffer from 2000 to 50000 lines:
set -g history-limit 50000

# Broadcast keystrokes to all panes simultaneously (Synchronize Panes):
bind S setw synchronize-panes
```
Setting `setw synchronize-panes on` allows an engineer with 4 split panes connected to 4 different servers to type commands simultaneously into all 4 servers in real time!

---

## 7. Automated Workspace Orchestration Script
You can automate complex, multi-pane development environments with a single idempotent Bash script:

```bash
#!/usr/bin/env bash
SESSION_NAME="dev-environment"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "[+] Session '$SESSION_NAME' already active. Attaching..."
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# 1. Create session with Window 1 named 'code'
tmux new-session -d -s "$SESSION_NAME" -n "code"

# 2. Split into editor (70% top) and test runner (30% bottom)
tmux split-window -v -p 30 -t "${SESSION_NAME}:code"
tmux send-keys -t "${SESSION_NAME}:code.1" "python -m pytest -v" C-m

# 3. Create Window 2 named 'logs' with horizontal split
tmux new-window -t "$SESSION_NAME" -n "logs"
tmux split-window -h -t "${SESSION_NAME}:logs"
tmux send-keys -t "${SESSION_NAME}:logs.0" "tail -f /var/log/syslog" C-m
tmux send-keys -t "${SESSION_NAME}:logs.1" "htop" C-m

# 4. Focus back on Window 1 and attach
tmux select-window -t "${SESSION_NAME}:code"
tmux select-pane -t "${SESSION_NAME}:code.0"
tmux attach-session -t "$SESSION_NAME"
```
This launches a 4-pane dual-window workspace in 100 milliseconds with zero manual clicking or resizing.
---

## 7. Deep Architectural Mechanics: PTY Master/Slave Pairs & Multiplexer Architecture

### The Pseudoterminal (PTY) Subsystem
How does `tmux` allow multiple terminal programs (Vim, Bash, top) to run inside a single physical window?
`tmux` creates a **Pseudoterminal (PTY)** for every pane. A PTY consists of two connected file descriptors:
1. `/dev/ptmx` (**PTY Master**): Owned by the `tmux` server process. `tmux` reads output from this FD and writes keystrokes into it.
2. `/dev/pts/[N]` (**PTY Slave**): Emulates a real hardware terminal. When `tmux` spawns Bash in a new pane, it connects Bash's `stdin`, `stdout`, and `stderr` to this slave device.

```
+----------------+      UNIX Socket       +------------------------------------+
|  tmux Client   | <====================> |            tmux Server             |
| (Physical TTY) |                        +------------------------------------+
+----------------+                               |                  |
                                         (PTY Master 0)     (PTY Master 1)
                                                 |                  |
                                         (PTY Slave 0)      (PTY Slave 1)
                                                 |                  |
                                          +-------------+    +-------------+
                                          | Pane 0: vim |    | Pane 1: htop|
                                          +-------------+    +-------------+
```

### Complete Compilable C Program: Allocating a Real Linux PTY
```c
/*
 * pty_allocator_demo.c - Allocates a POSIX PTY Master/Slave pair
 * Compile: gcc -O2 -Wall pty_allocator_demo.c -o pty_allocator_demo
 */
#define _XOPEN_SOURCE 600
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>

int main(void) {
    int master_fd = posix_openpt(O_RDWR | O_NOCTTY);
    if (master_fd < 0) {
        perror("posix_openpt");
        return 1;
    }

    if (grantpt(master_fd) != 0 || unlockpt(master_fd) != 0) {
        perror("grantpt/unlockpt");
        close(master_fd);
        return 1;
    }

    char *slave_name = ptsname(master_fd);
    printf("=========================================\n");
    printf("POSIX PSEUDOTERMINAL ALLOCATION AUDIT\n");
    printf("=========================================\n");
    printf("PTY Master File Descriptor : %d\n", master_fd);
    printf("PTY Slave Device Path      : %s\n", slave_name);
    printf("Child processes attached to %s will treat it as a real physical hardware terminal!\n", slave_name);
    printf("=========================================\n");

    close(master_fd);
    return 0;
}
```

---

## 8. Production War Story: The Lost 18-Hour Database Reseed
In 2020, an SRE was running a 18-hour schema re-indexing and data restoration task over an SSH VPN connection. At hour 17, the engineer's laptop went to sleep when closing the lid for lunch.
The VPN connection dropped. TCP keepalives timed out. The SSH connection severed, and the shell killed the database migration process. The entire 17 hours of work was lost, leaving the database in an inconsistent corrupted state.
Had the engineer run the command inside a `tmux` session (`tmux new -s restore`), the `tmux` server process would have continued executing the script completely unaffected by the client's network disconnection. Upon reconnecting to the server, typing `tmux attach -t restore` restores the session exactly as it was.
Rule of thumb: **Never run any long-running command over remote SSH without a terminal multiplexer.**
