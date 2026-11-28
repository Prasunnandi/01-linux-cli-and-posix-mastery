# Day 52: Sudoers Architecture: Privilege Delegation, visudo, and PAM Integration

The monolithic root account in UNIX represents an operational liability. The `sudo` (SuperUser DO) subsystem enforces fine-grained, auditable, and revocable administrative delegation. Rather than distributing the root password, `sudo` evaluates declarative grammar defined in `/etc/sudoers`, validates the calling user's credentials against PAM, and executes the designated target command under elevated kernel credentials (`EUID=0`).

---

## 1. Grammatical Specification of /etc/sudoers

The syntax of `/etc/sudoers` is formalized as an extended context-free grammar. A standard permission specification follows the canonical form:

```text
User_Spec ::= User_List Host_List '=' (Runas_List) (Tag_Spec) Command_List
```

### Deconstructing the Canonical Rule
```text
%devops  ALL=(root : ALL) NOPASSWD: /usr/bin/systemctl restart nginx, /usr/bin/journalctl
   |      |     |     |       |                       |
   |      |     |     |       |                       +--> Authorized command binaries
   |      |     |     |       +--> Tags (disable password re-prompting)
   |      |     |     +--> Target group execution list
   |      |     +--> Target user execution list
   |      +--> Host authorization (matches machine hostname or 'ALL')
   +--> Identity specifier (% represents group; bare string represents user)
```

### Sudo Aliases for Structured Governance
To scale administrative policies across thousands of enterprise hosts, `sudoers` provides four alias categories:
1. `User_Alias`: Groups users or directory service accounts (`User_Alias SEC_TEAM = alice, bob, %soc_auditors`).
2. `Runas_Alias`: Permitted target execution identities (`Runas_Alias DB_ADMINS = postgres, mysql, oracle`).
3. `Host_Alias`: Clusters of hostnames, FQDNs, or subnets (`Host_Alias DB_SERVERS = 10.0.10.0/24, db1.corp.lan`).
4. `Cmnd_Alias`: Whitelisted binaries with immutable absolute paths (`Cmnd_Alias WEB_OPS = /usr/bin/systemctl reload nginx, /usr/bin/nginx -t`).

---

## 2. Low-Level Kernel Execution & Token Caching

When a user executes `sudo <command>`:
1. `sudo` is executed with the SUID bit set (`-rwsr-xr-x 1 root root`).
2. The kernel sets `current->cred->euid = 0`, while retaining the calling user's $RUID$.
3. `sudo` opens `/etc/sudoers` and `/etc/sudoers.d/*`. It verifies file ownership (`root:root`) and permissions (`0440`). If permissions are permissive, execution halts immediately.
4. `sudo` checks the timestamp ticket file located in `/var/run/sudo/ts/` (or `/run/sudo/ts/`).

### Sudo Ticket Lifetime Mathematics
A sudo ticket record tracks the epoch timestamp $T_{\text{auth}}$ of the last successful credential verification. Given a timeout duration $T_{\text{timeout}}$ (default $15$ minutes = $900$ seconds):

$$\Delta T = T_{\text{now}} - T_{\text{auth}}$$

$$\text{Re-prompt Required} = \begin{cases}
\text{False} & \text{if } \Delta T < T_{\text{timeout}} \land \text{TTY Match} \\
\text{True} & \text{if } \Delta T \ge T_{\text{timeout}} \lor \text{Ticket Missing}
\end{cases}$$

Upon successful re-authentication via PAM, the kernel timestamp is updated:
$$T_{\text{auth}} \leftarrow T_{\text{now}}$$

```text
[User Invokes sudo] 
        |
        v
[SUID Elevation: EUID=0] 
        |
        v
[Inspect /run/sudo/ts/<user>] --(Valid Ticket?)--> [Skip PAM Password]
        | (Expired or Missing)                          |
        v                                               |
[Invoke PAM: pam_authenticate()]                        |
        | (Valid Password)                              |
        v                                               |
[Update /run/sudo/ts/<user>] <--------------------------+
        |
        v
[Parse /etc/sudoers Rule Matrix]
        | (Match Command & Host?)
        v
[setresuid(target_uid, target_uid, target_uid)]
        |
        v
[execve(command_path, argv, envp)]
```

---

## 3. Compilable C Implementation: Safe Privilege Dropping with `setresuid`

A core security responsibility when writing elevated tooling is dropping permissions permanently or temporarily. The Linux-specific `setresuid()` syscall atomically manipulates Real, Effective, and Saved UIDs.

Compile with: `gcc -O2 -Wall -Wextra privilege_drop.c -o privilege_drop`

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <pwd.h>
#include <errno.h>

void print_credentials(const char *phase) {
    uid_t ruid, euid, suid;
    if (getresuid(&ruid, &euid, &suid) == 0) {
        printf("[%s] RUID=%d, EUID=%d, SUID=%d\n", phase, ruid, euid, suid);
    } else {
        perror("getresuid");
    }
}

int drop_privileges_permanently(uid_t target_uid, gid_t target_gid) {
    /* 1. Clear supplementary groups to prevent privilege leakage */
    if (setgroups(0, NULL) != 0) {
        perror("setgroups failed");
        return -1;
    }

    /* 2. Drop GID: Real, Effective, Saved must all be set */
    if (setresgid(target_gid, target_gid, target_gid) != 0) {
        perror("setresgid failed");
        return -1;
    }

    /* 3. Drop UID: Real, Effective, Saved must all be set */
    if (setresuid(target_uid, target_uid, target_uid) != 0) {
        perror("setresuid failed");
        return -1;
    }

    /* 4. Verification assertion: verify that regaining root is impossible */
    if (setuid(0) != -1 || seteuid(0) != -1) {
        fprintf(stderr, "FATAL SECURITY FAILURE: Able to re-elevate privileges!\n");
        abort();
    }

    return 0;
}

int main(void) {
    print_credentials("Initial Process State");

    /* Attempt to drop privileges to 'nobody' (UID 65534) */
    uid_t nobody_uid = 65534;
    gid_t nobody_gid = 65534;

    if (getuid() == 0 || geteuid() == 0) {
        printf("Dropping privileges permanently to UID %d...\n", nobody_uid);
        if (drop_privileges_permanently(nobody_uid, nobody_gid) != 0) {
            fprintf(stderr, "Failed to drop privileges cleanly.\n");
            return EXIT_FAILURE;
        }
        print_credentials("After Dropping Privileges");
    } else {
        printf("Process is not running with root EUID. Run with sudo to test privilege dropping.\n");
    }

    return EXIT_SUCCESS;
}
```

---

## 4. `visudo`: Atomic Parsing, Locking, and Lexical Verification

Editing `/etc/sudoers` directly with a standard text editor (`nano`, `vim`) is a critical operational hazard: a single missing comma or syntax error locks out all administrative users across the entire system.

### How `visudo` Prevents System Destruction
1. **Advisory Locking**: `visudo` creates a lockfile `/etc/sudoers.tmp` using `fcntl(fd, F_SETLK, ...)` to serialize concurrent administrative edits.
2. **Atomic Tempfile Generation**: The editor modifies the temporary file `/etc/sudoers.tmp`.
3. **Lexical and Syntax Parse**: Upon saving and closing, `visudo` invokes its internal lexer/parser (`sudoers.y` / `sudoers.l`).
4. **Interactive Recovery**: If syntax errors exist, `visudo` intercepts:
   ```text
   >>> /etc/sudoers: syntax error near line 25 <<<
   What now? [e]dit, [x]it without saving, [Q]uit and force write:
   ```
5. **Atomic Rename**: Only upon zero parse errors does `visudo` issue `rename("/etc/sudoers.tmp", "/etc/sudoers")`, which is an atomic filesystem operation on POSIX filesystems.

---

## 5. Production Post-Mortem: Baron Samedit (CVE-2021-3156) Heap Overflow

### Vulnerability Mechanics
In January 2021, Qualys uncovered a decade-old heap-based buffer overflow in `sudo` (CVE-2021-3156, named *Baron Samedit*). When `sudo` executes commands in shell mode (`sudo -s` or `sudo -i`), it escapes special characters by prepending backslashes.

However, if `sudoedit` or `sudo` was invoked with the `-s` or `-i` flags and command-line arguments terminated with an unescaped trailing backslash:
```bash
sudoedit -s '\' $(python3 -c 'print("A"*1000)')
```
The internal parsing function `set_cmnd()` skipped past the terminating null byte:
```c
/* Vulnerable logic snippet */
for (cp = NewArgv[0]; *cp != '\0'; cp++) {
    if (*cp == '\\' && *(cp + 1) != '\0')
        cp++; /* Skips backslash, pointing to terminating null! */
    *dp++ = *cp;
}
*dp = '\0'; /* Out-of-bounds heap write */
```
This allowed unprivileged local attackers to corrupt contiguous heap memory (`struct service_user` pointers in glibc NSS), injecting arbitrary shared library paths and achieving root code execution without password authentication.

### Remediation & Defense-in-Depth
1. **Immediate Patching**: Ensure `sudo` version is updated beyond 1.9.5p2.
2. **Restricting Sudoedit**: Deploy custom audit rules alerting on `sudoedit` invocations containing escape characters.
3. **Hardening `/etc/sudoers`**: Disable shell invocation rights where possible using `NOEXEC:` tag:
```text
%auditors ALL=(root) NOEXEC: /usr/bin/cat, /usr/bin/less
```
---

## 6. Sudo Environment Sanitization & Secure Path Architecture

By default, executing an elevated command via `sudo` sanitizes process environment variables to prevent dynamic linker hijacking attacks (`LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH`).

### The `secure_path` Directive
In `/etc/sudoers`, the default configuration enforces:
```text
Defaults    secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```
When `sudo` invokes `execve()`, it discards the user's `$PATH` variable and substitutes `secure_path`. This eliminates PATH injection vulnerabilities where an attacker drops a malicious binary named `systemctl` in `/tmp` or current working directory.

### Environment Whitelisting vs Passing
To pass specific environment variables (such as HTTP proxy settings), administrators explicitly declare `env_keep`:
```text
Defaults    env_keep += "http_proxy https_proxy no_proxy"
```
Never use `Defaults !env_reset` in production systems, as it preserves all calling environment variables, allowing attackers to manipulate internal runtime flags of elevated processes.
