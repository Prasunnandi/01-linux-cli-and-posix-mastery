#!/usr/bin/env python3
"""
Day 39 Lab: RFC 1928 SOCKS5 Protocol Proxy Engine
Implements the binary state machine of a SOCKS5 application proxy (ssh -D):
- Client authentication negotiation (0x05, 0x01, 0x00)
- Connection request framing (CONNECT 0x01, IPv4 0x01, Domain 0x03)
- Proxy response header generation
"""

import struct
from dataclasses import dataclass
from typing import Tuple, Optional


# RFC 1928 SOCKS5 Constants
SOCKS_VERSION      = 0x05
AUTH_NO_AUTH       = 0x00
AUTH_NO_ACCEPTABLE = 0xFF

CMD_CONNECT        = 0x01
CMD_BIND           = 0x02
CMD_UDP_ASSOCIATE  = 0x03

ATYP_IPV4          = 0x01
ATYP_DOMAIN        = 0x03
ATYP_IPV6          = 0x04

REP_SUCCESS        = 0x00
REP_FAILURE        = 0x01


@dataclass
class SOCKS5ConnectionRequest:
    command: int
    address_type: int
    destination_address: str
    destination_port: int


class SOCKS5ProxyEngine:
    def handle_auth_negotiation(self, packet: bytes) -> bytes:
        """
        Processes client greeting:
        Byte 0: SOCKS Version (0x05)
        Byte 1: NMETHODS
        Bytes 2..: Supported Method IDs
        """
        if len(packet) < 2 or packet[0] != SOCKS_VERSION:
            return bytes([SOCKS_VERSION, AUTH_NO_ACCEPTABLE])

        nmethods = packet[1]
        methods = packet[2:2 + nmethods]

        if AUTH_NO_AUTH in methods:
            # Accept NO AUTHENTICATION REQUIRED (0x00)
            return bytes([SOCKS_VERSION, AUTH_NO_AUTH])

        return bytes([SOCKS_VERSION, AUTH_NO_ACCEPTABLE])

    def parse_connection_request(self, packet: bytes) -> Tuple[Optional[SOCKS5ConnectionRequest], bytes]:
        """
        Processes connection request:
        [VER 1B][CMD 1B][RSV 1B][ATYP 1B][DST.ADDR][DST.PORT 2B]
        Returns (ParsedRequest, ProxyResponseBytes).
        """
        if len(packet) < 6 or packet[0] != SOCKS_VERSION:
            return None, bytes([SOCKS_VERSION, REP_FAILURE, 0x00, ATYP_IPV4, 0, 0, 0, 0, 0, 0])

        cmd = packet[1]
        atyp = packet[3]
        offset = 4

        if atyp == ATYP_IPV4:
            dst_ip = f"{packet[offset]}.{packet[offset+1]}.{packet[offset+2]}.{packet[offset+3]}"
            offset += 4
        elif atyp == ATYP_DOMAIN:
            domain_len = packet[offset]
            offset += 1
            dst_ip = packet[offset:offset + domain_len].decode("utf-8")
            offset += domain_len
        else:
            return None, bytes([SOCKS_VERSION, REP_FAILURE, 0x00, ATYP_IPV4, 0, 0, 0, 0, 0, 0])

        dst_port = struct.unpack(">H", packet[offset:offset + 2])[0]

        req = SOCKS5ConnectionRequest(cmd, atyp, dst_ip, dst_port)

        # Generate successful response: [VER 0x05][REP 0x00][RSV 0x00][ATYP 0x01][BND.ADDR 0.0.0.0][BND.PORT 0]
        response = bytes([SOCKS_VERSION, REP_SUCCESS, 0x00, ATYP_IPV4, 0, 0, 0, 0, 0, 0])
        return req, response


def main():
    print("====================================================")
    print("DAY 39: RFC 1928 SOCKS5 PROTOCOL PROXY ENGINE")
    print("====================================================")

    proxy = SOCKS5ProxyEngine()

    # Step 1: Client Greeting (Client supports NO_AUTH=0x00)
    client_greeting = bytes([0x05, 0x01, 0x00])
    auth_resp = proxy.handle_auth_negotiation(client_greeting)
    print(f"1. Client Greeting : Version 0x{client_greeting[0]:02X}, Methods: {list(client_greeting[2:])}")
    print(f"   Proxy Response  : Version 0x{auth_resp[0]:02X}, Method Selected: 0x{auth_resp[1]:02X} (NO_AUTH)\n")
    assert auth_resp == bytes([0x05, 0x00]), "Proxy must select NO_AUTH (0x00)"

    # Step 2: Client Connection Request for "api.stripe.com:443" via Domain Name (ATYP=0x03)
    domain_bytes = b"api.stripe.com"
    req_packet = bytearray()
    req_packet.extend([0x05, 0x01, 0x00, 0x03])  # SOCKS5, CONNECT, RSV, DOMAIN
    req_packet.append(len(domain_bytes))
    req_packet.extend(domain_bytes)
    req_packet.extend(struct.pack(">H", 443))     # Port 443

    parsed_req, conn_resp = proxy.parse_connection_request(bytes(req_packet))
    assert parsed_req is not None, "Connection request must parse successfully"
    print(f"2. Client Connection Request:")
    print(f"   Command         : 0x{parsed_req.command:02X} (CONNECT)")
    print(f"   Address Type    : 0x{parsed_req.address_type:02X} (DOMAIN NAME)")
    print(f"   Target Host     : {parsed_req.destination_address}")
    print(f"   Target Port     : {parsed_req.destination_port}")
    print(f"   Proxy Reply     : 0x{conn_resp[1]:02X} (SUCCESS)")

    assert parsed_req.destination_address == "api.stripe.com"
    assert parsed_req.destination_port == 443
    assert conn_resp[1] == REP_SUCCESS

    print("-" * 55)
    print("[VERIFIED] SOCKS5 protocol state machine and domain routing verified!")


if __name__ == "__main__":
    main()
