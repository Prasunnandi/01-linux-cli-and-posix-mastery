# Day 53: Pluggable Authentication Modules (PAM): Architecture, Stack Evaluation, and Security Control Flags

Pluggable Authentication Modules (PAM, RFC 86.0) decouple system applications (`sshd`, `sudo`, `login`, `su`) from the underlying authentication mechanisms (local shadow passwords, Kerberos, LDAP, 2FA/TOTP, smart cards, biometrics). Rather than hardcoding cryptographic verification into every binary, applications invoke the standardized Linux-PAM API. The runtime evaluates dynamic shared object chains specified in `/etc/pam.d/`.

---

## 1. The Four Independent PAM Management Groups

Every PAM configuration defines rules across four orthogonal operational primitives:

1. **`auth` (Authentication)**: Validates user identity (password prompt, biometric scan, TOTP ticket) and establishes credential tokens.
2. **`account` (Account Verification)**: Validates authorization independent of identity (e.g., password expired, account suspended, login outside business hours, terminal access restricted).
3. **`password` (Credential Mutation)**: Updates the authentication token (e.g., enforcing password complexity rules, history uniqueness via `pam_pwhistory.so`).
4. **`session` (Context Setup & Teardown)**: Actions executed before and after granting user access (mounting home directories via `pam_mount.so`, configuring resource limits via `pam_limits.so`, auditing login events).

---

## 2. PAM Control Flags: Formal State Machine & Truth Tables

Each line in `/etc/pam.d/<service>` pairs a management group with a control flag and a shared module:

```text
auth    required    pam_unix.so nullok
```

The four traditional control flags govern stack traversal through a strict state machine:

| Control Flag | On Module Success | On Module Failure | Stack Evaluation Continued? |
| :--- | :--- | :--- | :--- |
| **`required`** | Recorded as OK | Recorded as FAIL | **YES** (Evaluates remainder of stack to prevent timing attacks) |
| **`requisite`** | Recorded as OK | Recorded as FAIL | **NO** (Aborts immediately; returns failure to application) |
| **`sufficient`** | Returns **SUCCESS** if no earlier `required` failed | Ignored | **NO** on success; **YES** on failure |
| **`optional`** | Recorded | Recorded | **YES** (Only used if no other module in stack returns status) |

### Formal Evaluation Logic
Let $S_i \in \{\text{SUCCESS}, \text{FAIL}\}$ be the output of module $i$ in stack of length $N$.
Let $F_{\text{req}}$ be a boolean tracking whether any `required` module failed:

$$F_{\text{req}} = \bigvee_{k \in \text{Required}} (S_k == \text{FAIL})$$

If module $m$ is `sufficient` and $S_m == \text{SUCCESS}$:
$$\text{Final Status} = \begin{cases}
\text{SUCCESS} & \text{if } \neg F_{\text{req}} \\
\text{FAIL} & \text{if } F_{\text{req}}
\end{cases}$$

```text
[Module Execution]
       |
       +--> required?   --> Success: continue stack
       |                --> Failure: record failure, continue stack
       |
       +--> requisite?  --> Success: continue stack
       |                --> Failure: ABORT STACK IMMEDIATELY -> Return Failure
       |
       +--> sufficient? --> Success: If no prior required failed -> RETURN SUCCESS
       |                --> Failure: ignore, continue stack
       |
       +--> optional?   --> Continue stack
```

---

## 3. Compilable C Implementation: Custom PAM Conversation Function

Applications communicate with PAM modules through a callback function pointer: the conversation function (`pam_conv`). This function prompts the user for passwords, TOTP tokens, or messages.

Compile with: `gcc -O2 -Wall -Wextra pam_auth_demo.c -o pam_auth_demo -lpam`

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <security/pam_appl.h>

/* The conversation function handles prompts from PAM modules */
static int custom_pam_conversation(int num_msg, const struct pam_message **msg,
                                   struct pam_response **resp, void *appdata_ptr) {
    if (num_msg <= 0 || num_msg > PAM_MAX_NUM_MSG) {
        return PAM_CONV_ERR;
    }

    struct pam_response *reply = calloc(num_msg, sizeof(struct pam_response));
    if (reply == NULL) {
        return PAM_BUF_ERR;
    }

    const char *password = (const char *)appdata_ptr;

    for (int i = 0; i < num_msg; i++) {
        switch (msg[i]->msg_style) {
            case PAM_PROMPT_ECHO_OFF:
                /* Password request: provide secret */
                reply[i].resp = strdup(password ? password : "");
                reply[i].resp_retcode = 0;
                break;
            case PAM_PROMPT_ECHO_ON:
                /* Username or general text request */
                reply[i].resp = strdup("demo_user");
                reply[i].resp_retcode = 0;
                break;
            case PAM_TEXT_INFO:
            case PAM_ERROR_MSG:
                /* Informational messages from module */
                fprintf(stdout, "[PAM MESSAGE]: %s\n", msg[i]->msg);
                reply[i].resp = NULL;
                reply[i].resp_retcode = 0;
                break;
            default:
                free(reply);
                return PAM_CONV_ERR;
        }
    }

    *resp = reply;
    return PAM_SUCCESS;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        printf("Usage: %s <username> <password>\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *username = argv[1];
    const char *password = argv[2];

    pam_handle_t *pamh = NULL;
    struct pam_conv conv = {
        .conv = custom_pam_conversation,
        .appdata_ptr = (void *)password
    };

    /* Initialize PAM transaction for 'login' service */
    int ret = pam_start("login", username, &conv, &pamh);
    if (ret != PAM_SUCCESS) {
        fprintf(stderr, "pam_start failed: %s\n", pam_strerror(pamh, ret));
        return EXIT_FAILURE;
    }

    /* Step 1: Authenticate */
    ret = pam_authenticate(pamh, 0);
    if (ret != PAM_SUCCESS) {
        fprintf(stderr, "Authentication failed: %s\n", pam_strerror(pamh, ret));
        pam_end(pamh, ret);
        return EXIT_FAILURE;
    }

    /* Step 2: Validate Account Status (expiration, hours, etc.) */
    ret = pam_acct_mgmt(pamh, 0);
    if (ret != PAM_SUCCESS) {
        fprintf(stderr, "Account validation failed: %s\n", pam_strerror(pamh, ret));
        pam_end(pamh, ret);
        return EXIT_FAILURE;
    }

    printf("SUCCESS: User '%s' fully authenticated and authorized via PAM!\n", username);

    /* Clean up transaction */
    pam_end(pamh, PAM_SUCCESS);
    return EXIT_SUCCESS;
}
```

---

## 4. Complex Real-World Stacking: MFA with `pam_google_authenticator.so`

In hardened multi-factor environments, SSH enforces password authentication followed by time-based one-time password (TOTP) verification.

### Production `/etc/pam.d/sshd` Snippet
```text
# Step 1: Enforce account active status
account    required     pam_nologin.so
account    include      common-account

# Step 2: Primary authentication (Local Unix or Kerberos)
auth       requisite    pam_unix.so nullok

# Step 3: Secondary Factor (Google Authenticator TOTP)
auth       required     pam_google_authenticator.so forward_pass nullok

# Step 4: Session setup & limit enforcement
session    required     pam_limits.so
session    include      common-session
```
If an attacker provides an invalid UNIX password in Step 2, `pam_unix.so` fails. Because the control flag is `requisite`, the stack **halts immediately**, completely blinding the attacker to whether Step 3 (TOTP) is configured or valid.

---

## 5. Production Post-Mortem: The `pam_permit.so` Catastrophic Bypass

### Incident Overview
A DevOps engineer attempting to debug passwordless local sudo on a fleet of staging servers accidentally pushed an Ansible template modifying `/etc/pam.d/common-auth`:
```text
# Flawed configuration
auth    sufficient    pam_permit.so
auth    include       common-auth
```
Within minutes, this configuration propagated to production bastions via shared automation:
1. **Total Authentication Bypass**: `pam_permit.so` unconditionally returns `PAM_SUCCESS`.
2. **Root Takeover**: Anyone initiating an SSH session (`ssh root@prod-node`) could press Enter with an empty password, any random string, or garbage bytes. Because `pam_permit.so` was marked `sufficient` and preceded `pam_unix.so`, the PAM stack immediately returned `PAM_SUCCESS`.
3. **Automated Scanner Infiltration**: Automated cryptominer scanning bots breached 40 bare-metal database instances within 180 seconds.

### Root-Cause Analysis & Prevention
1. **Never use `pam_permit.so` in Auth**: `pam_permit.so` should never appear in `auth` stacks outside synthetic local testing harnesses.
2. **Static CI Validation of PAM Diffs**: Implement automated syntax and logic verifiers in infrastructure repos to reject commits matching dangerous regex patterns:
```bash
grep -rnE 'auth\s+sufficient\s+pam_permit\.so' /etc/pam.d/ && exit 1 || exit 0
```
3. **Session Fail-Safes**: Always enforce independent hardware-bound SSH keys (`AuthorizedKeysFile`) alongside PAM (`ChallengeResponseAuthentication yes`) to maintain defense-in-depth.
---

## 6. PAM Configuration Directives: Include vs Substack

Modern Linux distributions structure PAM policies modularly using `/etc/pam.d/common-*` files. Two primary directives govern inter-file inclusions:

1. **`@include <file>`**: Inlines the target file directly into the calling stack. If an included file executes a `sufficient` module that succeeds, the *entire outer stack* terminates with success immediately.
2. **`substack <file>`**: Executes the target file as an isolated subroutine stack. A `sufficient` success within the substack only terminates the substack itself, returning a single composite status code back to the parent stack.

```text
[Parent Stack: /etc/pam.d/sudo]
       |
       v
[Invoke substack: /etc/pam.d/common-auth]
       |
       +--> pam_unix.so (sufficient -> Returns SUCCESS from Substack)
       |
[Parent Stack Resumes: /etc/pam.d/sudo]
       |
       +--> pam_warn.so (Executed! Substack did not terminate parent!)
```

Using `substack` prevents secondary modules in parent services from being bypassed unintentionally by child configurations.
