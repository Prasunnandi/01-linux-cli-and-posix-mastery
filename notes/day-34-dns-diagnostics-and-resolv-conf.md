# Day 34: DNS Diagnostics: `dig`, `nslookup`, `resolv.conf`

## 1. Architectural Foundations: The Linux Stub Resolver & NSS
In Linux, applications do not perform recursive DNS resolution directly over the network.
Instead, when an application calls `getaddrinfo()` or `gethostbyname()`, it invokes the C standard library's **Stub Resolver** (part of Glibc).

The stub resolver executes according to the Name Service Switch configuration in `/etc/nsswitch.conf`:
```
hosts: files mdns4_minimal [NOTFOUND=return] dns
```
1. **`files`**: Looks up `/etc/hosts` first (local static mappings).
2. **`dns`**: Consults the DNS nameservers defined in `/etc/resolv.conf`.
3. If configured, modern distributions route DNS queries through `systemd-resolved` via local loopback `127.0.0.53:53`.

```
+-------------------------------------------------------------------------+
| LINUX HOST RESOLUTION ARCHITECTURE                                      |
|                                                                         |
| Application (curl / python / ping)                                      |
|      |                                                                  |
|      v                                                                  |
| glibc getaddrinfo()                                                     |
|      |                                                                  |
|      v                                                                  |
| /etc/nsswitch.conf  ---> [files] -------------> Read /etc/hosts         |
|      |                                                 | (Found!)       |
|      |                                                 v                |
|      +-----------------> [dns] --------------> Return IP address        |
|                               | (Not in hosts)                          |
|                               v                                         |
|                       Read /etc/resolv.conf                             |
|                               |                                         |
|                               v                                         |
|                       Query nameserver (UDP/53)                         |
+-------------------------------------------------------------------------+
```

---

## 2. Kernel & C Library Mechanics: `/etc/resolv.conf` Directives
The file `/etc/resolv.conf` controls the stub resolver:
```
nameserver 8.8.8.8
nameserver 1.1.1.1
search prod.internal corp.internal
options timeout:2 attempts:3 rotate ndots:5
```

- **`nameserver <IP>`**: IPv4/IPv6 address of DNS recursive resolver (max 3 nameservers). Evaluated top-to-bottom.
- **`search <domain...>`**: Search list for host-name lookup. If querying `db01`, the resolver automatically tests `db01.prod.internal`, then `db01.corp.internal`.
- **`options timeout:2`**: Seconds to wait for a reply before trying the next nameserver.
- **`options attempts:3`**: Number of times to retry before giving up.
- **`options rotate`**: Round-robins queries across all configured nameservers to balance load.
- **`options ndots:5`**: **The Kubernetes Latency Trap!** (See Section 6).

---

## 3. The Diagnostics Toolkit: `dig` vs `nslookup` vs `host`
Never use `ping` to debug DNS! `ping` uses cached NSS resolution, hides TTLs, hides record types, and obscures query times.
The professional diagnostic tool is **`dig` (Domain Information Groper)**.

### Masterclass `dig` Invocations
```bash
# Standard A-record lookup with full telemetry (TTL, flags, query time)
dig example.com

# Short output format (ideal for shell scripts)
dig +short example.com

# Query a specific record type (MX, TXT, AAAA, NS, SOA)
dig MX google.com
dig TXT _dmarc.google.com

# Query a specific DNS server directly (bypassing local /etc/resolv.conf)
dig @1.1.1.1 example.com

# Trace complete DNS delegation path from Root servers to Authoritative!
dig +trace example.com

# Reverse DNS lookup (PTR record from IP to hostname)
dig -x 8.8.8.8 +short
```

---

## 4. Dissecting the `dig` Output Anatomy
```
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 48215
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; QUESTION SECTION:
;example.com.                   IN      A

;; ANSWER SECTION:
example.com.            3600    IN      A       93.184.216.34

;; Query time: 18 msec
;; SERVER: 127.0.0.53#53(127.0.0.53)
;; WHEN: Wed Nov 25 10:00:00 UTC 2026
;; MSG SIZE  rcvd: 56
```

- **`status: NOERROR`**: Query succeeded. (`NXDOMAIN` = domain doesn't exist, `SERVFAIL` = nameserver broken).
- **`flags: qr rd ra`**:
  - `qr` (Query Response): Packet is a response.
  - `rd` (Recursion Desired): Client requested recursive lookup.
  - `ra` (Recursion Available): Server supports recursive lookup.
  - `aa` (Authoritative Answer): The responding server is the direct authoritative owner of the domain!

---

## 5. Compilable C Program: Resolving DNS Records via `getaddrinfo`
```c
/*
 * dns_resolver_demo.c - Implements POSIX getaddrinfo host resolution
 * Compile: gcc -O2 -Wall dns_resolver_demo.c -o dns_resolver_demo
 */
#define _POSIX_C_SOURCE 200112L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <netdb.h>
#include <arpa/inet.h>

int main(int argc, char *argv[]) {
    const char *hostname = (argc > 1) ? argv[1] : "google.com";

    struct addrinfo hints, *res, *p;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;     /* IPv4 or IPv6 */
    hints.ai_socktype = SOCK_STREAM; /* TCP stream */

    printf("Resolving hostname: %s via Glibc Stub Resolver...\n", hostname);
    int status = getaddrinfo(hostname, NULL, &hints, &res);
    if (status != 0) {
        fprintf(stderr, "getaddrinfo error: %s\n", gai_strerror(status));
        return 1;
    }

    printf("=========================================\n");
    printf("RESOLVED IP ADDRESSES\n");
    printf("=========================================\n");

    for (p = res; p != NULL; p = p->ai_next) {
        char ipstr[INET6_ADDRSTRLEN];
        void *addr;
        const char *ipver;

        if (p->ai_family == AF_INET) {
            struct sockaddr_in *ipv4 = (struct sockaddr_in *)p->ai_addr;
            addr = &(ipv4->sin_addr);
            ipver = "IPv4";
        } else {
            struct sockaddr_in6 *ipv6 = (struct sockaddr_in6 *)p->ai_addr;
            addr = &(ipv6->sin6_addr);
            ipver = "IPv6";
        }

        inet_ntop(p->ai_family, addr, ipstr, sizeof(ipstr));
        printf("Protocol: %-4s | IP: %s\n", ipver, ipstr);
    }

    freeaddrinfo(res);
    return 0;
}
```

---

## 6. Production War Story: The Kubernetes `ndots:5` Latency Explosion
In 2018, a major tech company migrated a high-traffic microservices backend to Kubernetes.
Immediately, API latency doubled, and DNS CoreDNS pods began crashing under 500,000 queries per second!
Investigation traced the issue to `/etc/resolv.conf` injected into pods:
`options ndots:5`
What does `ndots:5` do?
If a domain name has fewer than 5 dots, glibc **appends every search domain first** before trying the domain directly!
When an application queried `api.stripe.com` (2 dots, less than 5):
1. Query: `api.stripe.com.default.svc.cluster.local` $	o$ NXDOMAIN!
2. Query: `api.stripe.com.svc.cluster.local` $	o$ NXDOMAIN!
3. Query: `api.stripe.com.cluster.local` $	o$ NXDOMAIN!
4. Query: `api.stripe.com.ec2.internal` $	o$ NXDOMAIN!
5. Query: `api.stripe.com.` $	o$ Finally succeeded!
Every single external API call generated **5 sequential DNS queries**!
Fix: Set `ndots:2` in pod DNS configuration, or append a trailing dot `api.stripe.com.` in code to force absolute FQDN resolution!
---

## 8. Deep Systems Internals: `systemd-resolved` & D-Bus Bus Architecture
Modern distributions (Ubuntu 20.04+, Fedora, Debian 12+) intercept DNS calls using a local stub listener:
`127.0.0.53:53`
Under the hood:
1. When Glibc's stub resolver queries `127.0.0.53`, the query is received by the local `systemd-resolved` daemon.
2. `systemd-resolved` maintains per-link DNS configurations (e.g. Wi-Fi interface uses Google DNS `8.8.8.8`, while VPN interface `tun0` uses corporate DNS `10.0.0.1`).
3. To inspect real-time DNS metrics and query cache statistics, use:
```bash
resolvectl status          # Displays per-interface DNS servers and search domains
resolvectl statistics      # Displays total transactions, cache hits, and cache misses
resolvectl flush-caches    # Instantly clears local DNS cache
```
---

## 9. Production Troubleshooting Runbook & Diagnostics
1. **Symptom: `dig` works, but `ping` or `curl` fails with `Could not resolve host`**:
   - Root Cause: `dig` bypasses `/etc/nsswitch.conf` and queries nameservers directly. `ping` and `curl` use Glibc's `getaddrinfo()`, which consults `/etc/nsswitch.conf`.
   - Fix: Check `/etc/nsswitch.conf`. Ensure `hosts: files dns` is present and valid.
2. **Symptom: Intermittent 5-second DNS lookup delays**:
   - Root Cause: The primary nameserver in `/etc/resolv.conf` is dead or unreachable. Glibc waits for the 5-second default timeout before falling back to the secondary nameserver.
   - Fix: Add `options timeout:1 attempts:2` to `/etc/resolv.conf` to fail over in 1 second instead of 5.
3. **Symptom: Search domain loop on short names**:
   - If querying a short hostname causes unexpected internet queries, verify the `search` directive in `/etc/resolv.conf`.
---

## 10. Advanced Security Auditing: Mitigating DNS Rebinding & Poisoning
DNS Rebinding allows malicious web pages to bypass browser Same-Origin Policy and interact with internal private network IP addresses (`127.0.0.1` or `192.168.1.1`):
1. Attacker controls domain `attacker.com` with low TTL (1 second).
2. Initial query returns attacker IP `203.0.113.50`.
3. Subsequent query returns private local IP `127.0.0.1`.
4. Browser JavaScript can now read local services!
**Hardening with `dnsmasq` or `unbound`**:
```conf
# Reject upstream private IP address answers (anti-rebind protection)
stop-dns-rebind
rebind-localhost-ok
```
---

## 11. Glibc NSS Configuration & Systemd Res_Init Mechanics
When an application runs inside a long-lived process (such as a Java JVM, Node.js, or Go with cgo):
1. Glibc reads `/etc/resolv.conf` **only once** upon the first DNS lookup!
2. If `/etc/resolv.conf` is modified while the process is running (e.g. DHCP renewal, VPN connection), the long-lived process **never detects the new nameservers**!
3. It continues to query the old, dead nameservers until the service is restarted.
4. Modern C applications can force Glibc to reload `/etc/resolv.conf` dynamically by invoking:
```c
#include <resolv.h>
res_init(); /* Re-reads /etc/resolv.conf and resets internal resolver state */
```
In Java environments, this is why administrators set `-Dnetworkaddress.cache.ttl=60` to force periodic cache expiration and resolver re-initialization.
