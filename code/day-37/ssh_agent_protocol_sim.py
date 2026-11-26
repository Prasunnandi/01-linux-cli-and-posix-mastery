#!/usr/bin/env python3
"""
Day 37 Lab: OpenSSH Agent Protocol & Key Challenge Simulator
Implements the binary IPC protocol of ssh-agent over UNIX domain sockets:
- Loading simulated Ed25519 keys
- Handling SSH2_AGENTC_REQUEST_IDENTITIES (11)
- Handling SSH2_AGENTC_SIGN_REQUEST (13) challenge signing
"""

import hmac
import hashlib
import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple


# RFC / OpenSSH Agent Message Codes
SSH2_AGENTC_REQUEST_IDENTITIES = 11
SSH2_AGENT_IDENTITIES_ANSWER   = 12
SSH2_AGENTC_SIGN_REQUEST       = 13
SSH2_AGENT_SIGN_RESPONSE       = 14


@dataclass
class SSHIdentity:
    key_type: str
    public_key: bytes
    private_seed: bytes
    comment: str


class SSHAgentDaemon:
    def __init__(self):
        self.keys: List[SSHIdentity] = []

    def add_key(self, key_type: str, seed: bytes, comment: str) -> bytes:
        # Simulate Ed25519 public key derivation: SHA256 of seed
        pubkey = hashlib.sha256(seed).digest()
        identity = SSHIdentity(key_type, pubkey, seed, comment)
        self.keys.append(identity)
        return pubkey

    def handle_request(self, packet: bytes) -> bytes:
        """Processes binary agent message and returns response packet."""
        msg_type = packet[0]

        if msg_type == SSH2_AGENTC_REQUEST_IDENTITIES:
            # Response: [uint8 type][uint32 num_keys] + for each key: [string blob][string comment]
            payload = bytearray()
            payload.append(SSH2_AGENT_IDENTITIES_ANSWER)
            payload.extend(struct.pack(">I", len(self.keys)))

            for k in self.keys:
                payload.extend(struct.pack(">I", len(k.public_key)))
                payload.extend(k.public_key)
                comment_bytes = k.comment.encode("utf-8")
                payload.extend(struct.pack(">I", len(comment_bytes)))
                payload.extend(comment_bytes)
            return bytes(payload)

        elif msg_type == SSH2_AGENTC_SIGN_REQUEST:
            # Request: [uint8 type][uint32 key_len][key_blob][uint32 data_len][data_to_sign][uint32 flags]
            offset = 1
            klen = struct.unpack(">I", packet[offset:offset+4])[0]
            offset += 4
            requested_pubkey = packet[offset:offset+klen]
            offset += klen
            dlen = struct.unpack(">I", packet[offset:offset+4])[0]
            offset += 4
            data_to_sign = packet[offset:offset+dlen]

            # Locate key
            target_key = next((k for k in self.keys if k.public_key == requested_pubkey), None)
            if not target_key:
                return b"\x05"  # SSH_AGENT_FAILURE

            # Sign data using HMAC-SHA256 with private seed
            sig = hmac.new(target_key.private_seed, data_to_sign, hashlib.sha256).digest()

            payload = bytearray()
            payload.append(SSH2_AGENT_SIGN_RESPONSE)
            payload.extend(struct.pack(">I", len(sig)))
            payload.extend(sig)
            return bytes(payload)

        return b"\x05"  # SSH_AGENT_FAILURE


def main():
    print("====================================================")
    print("DAY 37: OPENSSH AGENT PROTOCOL IPC SIMULATOR")
    print("====================================================")

    agent = SSHAgentDaemon()

    # Load simulated Ed25519 key
    seed = b"ultra_secure_master_ed25519_seed_12345"
    pubkey = agent.add_key("ssh-ed25519", seed, "admin@infra.corp")
    print(f"Loaded Identity into Agent: 'admin@infra.corp'")
    print(f"Public Key Fingerprint    : {pubkey.hex()[:16]}...\n")

    # Client Request 1: Query Identities (Code 11)
    req1 = bytes([SSH2_AGENTC_REQUEST_IDENTITIES])
    resp1 = agent.handle_request(req1)
    assert resp1[0] == SSH2_AGENT_IDENTITIES_ANSWER, "Expected SSH2_AGENT_IDENTITIES_ANSWER"
    num_keys = struct.unpack(">I", resp1[1:5])[0]
    print(f"Client Query Identities Answer: {num_keys} key(s) returned by agent.")
    assert num_keys == 1

    # Client Request 2: Sign Server Challenge (Code 13)
    challenge = b"RANDOM_SERVER_HANDSHAKE_NONCE_789456"
    req2 = bytearray()
    req2.append(SSH2_AGENTC_SIGN_REQUEST)
    req2.extend(struct.pack(">I", len(pubkey)))
    req2.extend(pubkey)
    req2.extend(struct.pack(">I", len(challenge)))
    req2.extend(challenge)
    req2.extend(struct.pack(">I", 0))  # flags

    resp2 = agent.handle_request(bytes(req2))
    assert resp2[0] == SSH2_AGENT_SIGN_RESPONSE, "Expected SSH2_AGENT_SIGN_RESPONSE"
    sig_len = struct.unpack(">I", resp2[1:5])[0]
    signature = resp2[5:5+sig_len]

    print(f"Server Challenge Signed Successfully!")
    print(f"  Challenge : {challenge.decode('utf-8')}")
    print(f"  Signature : {signature.hex()[:32]}... ({sig_len} bytes)")

    # Verify signature matches HMAC of private seed
    expected_sig = hmac.new(seed, challenge, hashlib.sha256).digest()
    assert signature == expected_sig, "Signature must be cryptographically valid"

    print("-" * 55)
    print("[VERIFIED] SSH Agent challenge-response protocol validated without key exposure!")


if __name__ == "__main__":
    main()
