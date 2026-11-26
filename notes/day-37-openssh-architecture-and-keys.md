# Day 37: OpenSSH Architecture: Keys, Agents & Config

## 1. Architectural Foundations: Asymmetric Cryptography in SSH
The **Secure Shell (SSH)** protocol (RFC 4251-4254) replaced legacy unencrypted protocols (Telnet, rlogin, FTP) by providing end-to-end encryption, server authentication, and client authentication.

SSH authentication relies on **Public Key Cryptography**:
1. The **Private Key** (e.g. `id_ed25519`) never leaves the client host and must be guarded with strict file permissions (`chmod 600`).
2. The **Public Key** (e.g. `id_ed25519.pub`) is appended to `~/.ssh/authorized_keys` on the remote server.
3. During handshake, the server sends a random cryptographic challenge. The client signs the challenge with its private key. The server verifies the signature using the client's public key. The private key is **never transmitted over the network**!

```
+-------------------------------------------------------------------------+
| OPENSSH KEY-BASED AUTHENTICATION HANDSHAKE (RFC 4252)                   |
|                                                                         |
| Client Host                                           Remote Server     |
| (Has id_ed25519)                                      (Has authorized_keys)
|      |                                                      |           |
|      | 1. SSH-2.0 Identification & DH Key Exchange          |           |
|      |<====================================================>|           |
|      |    (Encrypted AES-GCM / ChaCha20-Poly1305 Tunnel)    |           |
|      |                                                      |           |
|      | 2. "I want to log in as user 'ubuntu' using Key K"   |           |
|      |----------------------------------------------------->|           |
|      |                                                      |           |
|      | 3. Server generates Random Challenge String C        |           |
|      |<-----------------------------------------------------|           |
|      |                                                      |           |
|      | 4. Client signs Challenge with Private Key: Sig(C)   |           |
|      |----------------------------------------------------->|           |
|      |                                                      | Checks Sig|
|      |                                                      | with pubkey
|      | 5. Authentication Accepted! Shell session granted.   |           |
|      |<-----------------------------------------------------|           |
+-------------------------------------------------------------------------+
```

---

## 2. Cryptographic Algorithms: Ed25519 vs RSA
- **RSA (Rivest-Shamir-Adleman)**: Relies on prime factorization. Requires 3072 or 4096-bit key lengths to remain secure. Legacy algorithm (SHA-1 signatures deprecated in modern OpenSSH).
- **Ed25519 (Edwards-curve Digital Signature Algorithm)**: Uses Twisted Edwards curve $y^2 - x^2 = 1 - rac{121665}{121666} x^2 y^2$ over the prime field $2^{255} - 19$.
  - 256-bit key length provides 128-bit security level (equivalent to 3072-bit RSA).
  - Immunity to side-channel timing attacks.
  - Generates compact, 68-character public keys.
  - **Modern Standard**: Always generate Ed25519 keys!

```bash
# Generate modern Ed25519 key with 100 rounds of Key Derivation Function (KDF)
ssh-keygen -t ed25519 -a 100 -C "admin@infrastructure.corp"
```

---

## 3. The `ssh-agent` & UNIX Domain Socket IPC
Typing a 20-character passphrase every time you log in or run Git is painful.
**`ssh-agent`** is a background daemon that decrypts private keys into memory once, and answers signing challenges on behalf of client processes.

### How `ssh-agent` Communicates
1. `ssh-agent` creates a secure UNIX domain socket: `/tmp/ssh-XXXXXX/agent.<PID>`.
2. It sets the environment variable `SSH_AUTH_SOCK=/tmp/ssh-XXXXXX/agent.<PID>`.
3. When you run `ssh host` or `git push`, the client connects to `$SSH_AUTH_SOCK` and requests: *"Please sign this challenge string using my loaded Ed25519 key!"*
4. The agent verifies permissions, signs the challenge, and returns the signature. **The client program never sees the raw private key!**

```bash
# Start ssh-agent in current shell
eval "$(ssh-agent -s)"

# Load key into agent memory (prompts for passphrase once)
ssh-add ~/.ssh/id_ed25519

# List keys loaded in agent
ssh-add -l

# Flush keys from agent memory upon leaving workstation
ssh-add -D
```

---

## 4. Masterclass `~/.ssh/config` Engineering
Never type `ssh -i ~/keys/prod.pem -p 2222 ubuntu@198.51.100.42` manually!
Use `~/.ssh/config` to define connection profiles, proxy jumps, and security defaults.

```ssh-config
# Global Defaults
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
    AddKeysToAgent yes
    IdentitiesOnly yes
    StrictHostKeyChecking ask
    VerifyHostKeyDNS yes

# Bastion / Jump Host
Host bastion
    HostName bastion.corp.internal
    User jumpuser
    Port 2222
    IdentityFile ~/.ssh/id_ed25519

# Internal Production Database (Routed via Bastion automatically!)
Host prod-db
    HostName 10.0.15.50
    User postgres
    ProxyJump bastion
    IdentityFile ~/.ssh/db_prod_ed25519
```

---

## 5. Compilable C Program: Inspecting the `SSH_AUTH_SOCK` IPC Protocol
```c
/*
 * ssh_agent_ping.c - Connects to local ssh-agent UNIX socket and queries loaded keys
 * Compile: gcc -O2 -Wall ssh_agent_ping.c -o ssh_agent_ping
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <arpa/inet.h>

#define SSH2_AGENTC_REQUEST_IDENTITIES 11
#define SSH2_AGENT_IDENTITIES_ANSWER   12

int main(void) {
    const char *sock_path = getenv("SSH_AUTH_SOCK");
    if (!sock_path) {
        fprintf(stderr, "Error: SSH_AUTH_SOCK environment variable not set! Run eval $(ssh-agent -s)\n");
        return 1;
    }

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sock_path, sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect to SSH_AUTH_SOCK");
        close(fd);
        return 1;
    }

    /* Send SSH2_AGENTC_REQUEST_IDENTITIES (Length: 1 byte, Code: 11) */
    unsigned char request[5];
    uint32_t len = htonl(1);
    memcpy(request, &len, 4);
    request[4] = SSH2_AGENTC_REQUEST_IDENTITIES;

    write(fd, request, 5);

    /* Read response header */
    unsigned char resp_header[5];
    read(fd, resp_header, 5);

    uint32_t resp_len;
    memcpy(&resp_len, resp_header, 4);
    resp_len = ntohl(resp_len);
    unsigned char msg_type = resp_header[4];

    printf("=========================================\n");
    printf("SSH-AGENT PROTOCOL PROBE AUDIT\n");
    printf("=========================================\n");
    printf("Agent Socket Path : %s\n", sock_path);
    printf("Agent Response Len: %u bytes\n", resp_len);
    printf("Agent Message Type: %u (%s)\n",
           msg_type,
           (msg_type == SSH2_AGENT_IDENTITIES_ANSWER) ? "SSH2_AGENT_IDENTITIES_ANSWER" : "UNKNOWN");

    if (msg_type == SSH2_AGENT_IDENTITIES_ANSWER) {
        uint32_t num_keys;
        read(fd, &num_keys, 4);
        num_keys = ntohl(num_keys);
        printf("Loaded Keys Count : %u\n", num_keys);
    }
    printf("=========================================\n");

    close(fd);
    return 0;
}
```

---

## 6. Production War Story: The Agent Forwarding Privileged Compromise
In 2020, an engineering organization required all developers to use `ForwardAgent yes` to access remote staging servers via an intermediate jump host.
An attacker compromised the jump host via an unpatched web vulnerability and gained `root` privileges.
Because developers used `ssh -A` (Agent Forwarding), their client machines exposed their local `SSH_AUTH_SOCK` into `/tmp/ssh-XXXXXX/agent.<PID>` on the jump host!
The attacker wrote a background script monitoring `/tmp/ssh-*`.
Whenever a senior infrastructure engineer logged into the jump host, the attacker hijacked their forwarding socket and authenticated directly into AWS core production servers, completely bypassing two-factor authentication!
Fix: **Never use Agent Forwarding (`ForwardAgent yes`)!** Instead, use **ProxyJump** (`ssh -J bastion target` or `ProxyCommand`), which forwards raw TCP packets without exposing your private key agent socket to the jump host.
---

## 8. Deep Systems Internals: SSH Host Key Verification & `known_hosts` Cryptographic Hashing
To prevent Man-In-The-Middle (MITM) attacks, SSH maintains a list of verified public host keys in `~/.ssh/known_hosts`.
When you connect to a server for the first time:
1. The server presents its host public key.
2. SSH displays the key's SHA256 fingerprint:
   `SHA256:RO2i38... (ED25519)`
3. If confirmed, the server's public key is appended to `known_hosts`.
4. If an attacker later intercepts the network connection and presents a different host key, OpenSSH immediately halts with the famous security warning:
   `@@@@@@@@@@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @@@@@@@@@@`
5. Modern OpenSSH hashes hostnames inside `known_hosts` (using `HashKnownHosts yes`) so that if a laptop is stolen, an attacker cannot extract the company's internal server IP addresses.
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: SSH rejects key with `Permissions 0644 for id_ed25519 are too open`**:
   - Root Cause: OpenSSH client enforces strict file security. If private keys are readable by other users or groups, SSH refuses to load them.
   - Fix: Run `chmod 600 ~/.ssh/id_ed25519` and `chmod 700 ~/.ssh`.
2. **Symptom: Remote server prompts for password despite public key in `authorized_keys`**:
   - Check remote permissions: Remote `~/.ssh` must be `0700`, and `~/.ssh/authorized_keys` must be `0600`.
   - Check ownership: If the home directory is owned by another user or group-writable (`chmod 775 ~`), OpenSSH's `StrictModes` security setting rejects all keys! Fix: `chmod 755 ~`.
3. **Symptom: `ssh-add` fails with `Could not open a connection to your authentication agent`**:
   - The `ssh-agent` daemon is not running in the current shell environment.
   - Fix: Run `eval "$(ssh-agent -s)"` before invoking `ssh-add`.
---

## 10. Advanced Security Auditing: OpenSSH Server Hardening (`/etc/ssh/sshd_config`)
To achieve CIS Benchmark and SOC2 compliance, harden the OpenSSH daemon:
```ssh-config
# Disable legacy password authentication completely (Keys only!)
PasswordAuthentication no
ChallengeResponseAuthentication no

# Disable direct root login over SSH
PermitRootLogin prohibit-password

# Disallow empty passwords
PermitEmptyPasswords no

# Enforce strict key permission validation
StrictModes yes

# Restrict allowed key exchange algorithms to modern elliptic curves
KexAlgorithms curve25519-sha256,diffie-hellman-group16-sha512

# Restrict allowed ciphers to authenticated encryption (AEAD)
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
```
