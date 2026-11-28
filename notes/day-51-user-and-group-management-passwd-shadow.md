# Day 51: Linux User & Group Architecture: /etc/passwd, /etc/shadow, and Cryptographic Authentication

The POSIX user and group security model represents the foundational boundary of UNIX multi-tenant security. While modern enterprises delegate authentication to LDAP, Kerberos, and OAuth, every Linux kernel enforces access control strictly through numeric identifiers: the User ID ($UID$) and Group ID ($GID$). This masterclass dissects the low-level data structures, cryptographic password storage algorithms, PAM hooks, and kernel accounting mechanisms governing Linux identity.

---

## 1. System Identity Files & Binary Struct Representations

At the userspace boundary, Linux identity rests upon four canonical flat files: `/etc/passwd`, `/etc/shadow`, `/etc/group`, and `/etc/gshadow`. The C standard library parses these records into well-defined POSIX structures defined in `<pwd.h>` and `<shadow.h>`.

### The POSIX `struct passwd` (Defined in `<pwd.h>`)
```c
/* Standard POSIX passwd structure */
struct passwd {
    char   *pw_name;       /* Username (e.g. "deploy") */
    char   *pw_passwd;     /* Obsolete password field (contains 'x' when shadowed) */
    uid_t   pw_uid;        /* Numerical User ID (32-bit unsigned on modern Linux) */
    gid_t   pw_gid;        /* Numerical Primary Group ID */
    char   *pw_gecos;      /* User information comment field (name, phone, room) */
    char   *pw_dir;        /* Absolute path to initial working directory ($HOME) */
    char   *pw_shell;      /* Initial login shell binary (/bin/bash, /usr/sbin/nologin) */
};
```

### The Shadow Password `struct spwd` (Defined in `<shadow.h>`)
Because `/etc/passwd` must remain world-readable (`chmod 644`) for utilities like `ls -l` to resolve numerical UIDs to human-readable strings, hashed passwords are segregated into `/etc/shadow` (`chmod 640`, owner `root:shadow`).

```c
/* Structure representing /etc/shadow record */
struct spwd {
    char *sp_namp;         /* Login username corresponding to /etc/passwd */
    char *sp_pwdp;         /* Cryptographic salt and hash string */
    long  sp_lstchg;       /* Days since Jan 1, 1970 that password was last modified */
    long  sp_min;          /* Minimum days allowed before password can be changed */
    long  sp_max;          /* Maximum days password remains valid before expiring */
    long  sp_warn;         /* Days before password expiration that user is warned */
    long  sp_inact;        /* Days after expiration before account is disabled */
    long  sp_expire;       /* Absolute date since Jan 1, 1970 when account is disabled */
    unsigned long sp_flag; /* Reserved for future kernel/libc extension (must be 0) */
};
```

### Kernel Identity Representation: `struct cred`
Within kernel memory, a process is associated with `struct cred` (defined in `include/linux/cred.h`), which tracks eight distinct IDs:
```c
struct cred {
    atomic_t        usage;
    uid_t           uid;            /* Real UID (who spawned the process) */
    gid_t           gid;            /* Real GID */
    uid_t           suid;           /* Saved UID (set-user-ID backup) */
    gid_t           sgid;           /* Saved GID */
    uid_t           euid;           /* Effective UID (used for permission checks) */
    gid_t           egid;           /* Effective GID */
    uid_t           fsuid;          /* File system UID (NFS/VFS operations) */
    gid_t           fsgid;          /* File system GID */
    struct group_info *group_info;  /* Supplementary group list */
    /* ... security hooks (SELinux/AppArmor) ... */
};
```

---

## 2. Cryptographic Password Hashing & Salt Theory

Modern Linux distributions employ modular crypt formats specified by `$id$salt$hash`. The identifier selects the underlying cryptographic primitive:
- `$1$`: MD5 (Legacy, broken, RFC 1321)
- `$2a$`, `$2y$`: Blowfish / bcrypt (OpenBSD heritage)
- `$5$`: SHA-256 (FIPS 180-2, 5000 rounds default)
- `$6$`: SHA-512 (FIPS 180-2, 5000 rounds default)
- `$y$`: yescrypt (Modern default on Debian/Ubuntu/RHEL, memory-hard against ASICs)

### The SHA-512 Crypt Rounds Expansion Formula
To defeat brute-force and dictionary attacks, SHA-512 crypt enforces iterated key stretching. Given password $P$, salt $S$, and rounds count $R$ (where $1,000 \le R \le 999,999,999$, defaulting to $5000$):

$$\text{Digest}_0 = \text{SHA512}(P \parallel S \parallel P)$$

$$\text{For } i = 0 \text{ to } R-1:$$

$$\text{Digest}_{i+1} = \text{SHA512}\left(\text{KeySequence}(i, P, S, \text{Digest}_i)\right)$$

### Password Expiration Epoch Calculation
The `sp_lstchg` and `sp_expire` fields measure integer days elapsed since the Unix epoch ($1970\text{-}01\text{-}01\text{T}00:00:00\text{Z}$). To determine whether an account has expired:

$$D_{\text{current}} = \left\lfloor \frac{T_{\text{epoch\_seconds}}}{86400} \right\rfloor$$

$$\text{Expired} = \begin{cases} 
\text{True} & \text{if } sp\_expire > 0 \land D_{\text{current}} \ge sp\_expire \\
\text{True} & \text{if } sp\_max > 0 \land D_{\text{current}} \ge (sp\_lstchg + sp\_max + sp\_inact) \\
\text{False} & \text{otherwise}
\end{cases}$$

---

## 3. Compilable C Implementation: Authenticating User Against `/etc/shadow`

The following C implementation reads `/etc/shadow`, extracts the salt, invokes `crypt_r()`, and validates the input password against the stored cryptographic digest.

Compile with: `gcc -O2 -Wall -Wextra -lcrypt verify_user.c -o verify_user`

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pwd.h>
#include <shadow.h>
#include <crypt.h>
#include <errno.h>

int authenticate_user(const char *username, const char *plaintext_password) {
    struct spwd spbuf;
    struct spwd *result = NULL;
    char buffer[4096];
    struct crypt_data cdata;
    memset(&cdata, 0, sizeof(cdata));

    /* Accessing /etc/shadow requires CAP_DAC_OVERRIDE or root privileges */
    int status = getspnam_r(username, &spbuf, buffer, sizeof(buffer), &result);
    if (status != 0 || result == NULL) {
        fprintf(stderr, "Authentication failed: User '%s' not found or permission denied.\n", username);
        return -1;
    }

    /* Check for locked or disabled accounts ('!', '*', or empty hash) */
    if (result->sp_pwdp == NULL || result->sp_pwdp[0] == '!' || result->sp_pwdp[0] == '*') {
        fprintf(stderr, "Authentication failed: Account '%s' is locked or disabled.\n", username);
        return -2;
    }

    /* crypt_r extracts salt parameters directly from stored hash prefix */
    char *computed_hash = crypt_r(plaintext_password, result->sp_pwdp, &cdata);
    if (computed_hash == NULL) {
        perror("crypt_r error");
        return -3;
    }

    /* Constant-time memory comparison to mitigate timing attacks */
    size_t len_stored = strlen(result->sp_pwdp);
    size_t len_comp = strlen(computed_hash);
    if (len_stored != len_comp) {
        return 1; /* Mismatch */
    }

    int diff = 0;
    for (size_t i = 0; i < len_stored; i++) {
        diff |= (result->sp_pwdp[i] ^ computed_hash[i]);
    }

    return (diff == 0) ? 0 : 1;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        printf("Usage: %s <username> <password>\n", argv[0]);
        return EXIT_FAILURE;
    }

    if (getuid() != 0) {
        fprintf(stderr, "Warning: Running unprivileged. Access to /etc/shadow will likely fail.\n");
    }

    int res = authenticate_user(argv[1], argv[2]);
    if (res == 0) {
        printf("SUCCESS: Password verified for user '%s'.\n", argv[1]);
        return EXIT_SUCCESS;
    } else {
        printf("FAILURE: Invalid credentials for user '%s' (Code: %d).\n", argv[1], res);
        return EXIT_FAILURE;
    }
}
```

---

## 4. Supplementary Groups, /etc/group, and `setgroups()`

In POSIX, while a process has exactly one primary $GID$, it can possess up to `NGROUPS_MAX` (typically 65,536 on modern Linux) supplementary groups.

### Supplementary Group Lookup Flow
1. Userspace reads `/etc/group` format: `group_name:password_placeholder:GID:user1,user2,user3`.
2. Upon user login, `initgroups(username, base_gid)` queries NSS (`/etc/nsswitch.conf`).
3. The kernel syscall `setgroups(int size, const gid_t *list)` populates `current->cred->group_info`.

### Effective vs Real vs Saved IDs
When a binary has the SUID bit set (`chmod u+s /usr/bin/passwd`):
1. **Real UID ($RUID$)**: The user who invoked the program.
2. **Effective UID ($EUID$)**: Determines kernel permission checks. Set to binary owner (0 / root).
3. **Saved UID ($SUID$)**: Copy of $EUID$ prior to privilege dropping, allowing `seteuid()` to toggle between unprivileged state and elevated state safely.

```text
+-------------------+--------------------+--------------------+
| Real UID (RUID)   | Effective UID (EUID)| Saved UID (SUID)   |
| (Logged-in User)  | (Root: 0)          | (Root: 0)          |
+-------------------+--------------------+--------------------+
          |                   |                    |
          |       Temporary drop via seteuid(RUID) |
          v                   v                    v
+-------------------+--------------------+--------------------+
| Real UID (RUID)   | Effective UID (RUID)| Saved UID (0)      |
+-------------------+--------------------+--------------------+
```

---

## 5. Production Post-Mortem: UID 0 Collision & Shadow Corruption Outage

### Incident Overview
An automated cloud provisioning script on an enterprise Kubernetes cluster generated a secondary administrative service account via:
```bash
echo "k8s-admin:x:0:0:Kubernetes Agent:/root:/bin/bash" >> /etc/passwd
```
The intention was to grant root access. However, multiple utilities (`find`, `ps`, `logrotate`, audit daemons) broke catastrophically:
1. **Account Overwrite**: `passwd k8s-admin` modified the password entry in `/etc/shadow` for the *first* matching UID 0 entry, inadvertently resetting root's master production credentials.
2. **Audit Failures**: Linux `auditd` logs attributed all actions of `k8s-admin` to `root`, violating SOC2 and PCI-DSS compliance logging.
3. **PAM Lockout**: Systemd's `logind` encountered non-deterministic session cgroup assignments because two disparate usernames resolved to the identical UID.

### Architectural Remediation
1. **Never Duplicate UID 0**: Never create multiple accounts with UID 0. True privilege delegation must strictly occur via `sudoers` or Linux Capabilities (`setcap`).
2. **Automated Auditing**: Deploy an automated CI/CD compliance check asserting that only a single line in `/etc/passwd` possesses UID 0:
```bash
awk -F: '($3 == "0") { print $1 }' /etc/passwd | grep -vx "root" && exit 1 || exit 0
```
3. **Integrity Locking**: Apply immutable attributes (`chattr +i /etc/passwd /etc/shadow`) on hardened production nodes to prevent unauthorized append operations.
