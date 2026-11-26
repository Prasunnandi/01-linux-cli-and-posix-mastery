# Hands-On Lab: Day 37 - OpenSSH Agent Protocol Simulator (`ssh_agent_protocol_sim.py`)

## 1. What Are We Building & Why Does It Matter?
When you log in over SSH or push code to GitHub using SSH keys, where does the private key live?
If every application (Git, SSH, VS Code) read your raw private key file (`~/.ssh/id_ed25519`), any malicious program or compromised dependency could steal your private key!

To protect your identity, OpenSSH uses **`ssh-agent`**.
The agent is a background daemon that holds decrypted keys in memory.
When a program needs to authenticate, it connects to the agent's UNIX domain socket (`$SSH_AUTH_SOCK`) and sends a request: *"Please sign this challenge!"*
The agent signs the data and returns the signature. **The client program never touches or sees the private key!**

In this lab, we build a simulator executing the exact binary message protocol defined by OpenSSH for identity querying and cryptographic signing.

---

## 2. Python Concepts for Beginners
1. **Binary Packing with `struct.pack(">I", value)`**:
   - `>I` encodes an integer as a **Big-Endian 32-bit unsigned integer** (4 bytes). This is the standard network byte order used in SSH and Internet protocols.
2. **Cryptographic Hashing with `hmac`**:
   - `hmac.new(key, data, hashlib.sha256).digest()` computes a keyed message authentication signature.
3. **Hexadecimal String Conversion**:
   - `pubkey.hex()[:16]` converts raw binary bytes into readable hexadecimal characters (e.g. `a3f4b8...`).

---

## 3. Step-by-Step Code Walkthrough

```python
if msg_type == SSH2_AGENTC_REQUEST_IDENTITIES:
    payload.append(SSH2_AGENT_IDENTITIES_ANSWER)
    payload.extend(struct.pack(">I", len(self.keys)))
```
- Message code `11` asks the agent what public keys it holds. The agent responds with code `12`, the key count, and public key blobs.

```python
elif msg_type == SSH2_AGENTC_SIGN_REQUEST:
    # Extracts requested public key and challenge payload
    # Signs challenge using target key's private seed
    sig = hmac.new(target_key.private_seed, data_to_sign, hashlib.sha256).digest()
```
- Message code `13` submits a server nonce challenge. The agent looks up the matching key, signs the challenge, and returns code `14`.

---

## 4. How to Run the Script

```bash
cd code/day-37
python ssh_agent_protocol_sim.py
```

### Expected Output
```
====================================================
DAY 37: OPENSSH AGENT PROTOCOL IPC SIMULATOR
====================================================
Loaded Identity into Agent: 'admin@infra.corp'
Public Key Fingerprint    : b7490336ae9c4644...

Client Query Identities Answer: 1 key(s) returned by agent.
Server Challenge Signed Successfully!
  Challenge : RANDOM_SERVER_HANDSHAKE_NONCE_789456
  Signature : e0f562479e0004ff97858c278912d33e... (32 bytes)
-------------------------------------------------------
[VERIFIED] SSH Agent challenge-response protocol validated without key exposure!
```

---

## 5. Common Python Errors & Troubleshooting
1. **`struct.error: unpack requires a buffer of 4 bytes`**:
   - Occurs if `struct.unpack(">I", ...)` is passed fewer than 4 bytes due to an offset parsing bug.
2. **Key Lookups with Byte Mismatch**:
   - Public keys are stored as binary `bytes`. Comparing a `str` against `bytes` always evaluates to `False`.

---

## 6. Beginner Exercises & Challenges
1. **Add Key Removal**: Implement handling for message code `18` (`SSH2_AGENTC_REMOVE_IDENTITY`), deleting a specific key from agent memory.
2. **Key Expiration Timer**: Add a lifetime timestamp to `SSHIdentity` so that keys automatically expire and delete themselves after 30 minutes.
