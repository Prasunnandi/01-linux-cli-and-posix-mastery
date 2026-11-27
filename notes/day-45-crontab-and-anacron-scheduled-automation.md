# Day 45: Crontab & Anacron - Lexical Parsing, Spool Directories, and Catch-Up Scheduling

## 1. Classical UNIX Automation: Vixie Cron vs Anacron

Before the advent of systemd timers, automated task scheduling in Linux was split across two distinct daemons designed for different operational environments:
1. **Vixie Cron (`crond`)**: Designed for 24/7 constantly running servers. It inspects configuration tables every 60 seconds at second 00, firing tasks matching the current minute, hour, day, month, and day-of-week. If the system is asleep or powered off at the designated minute, the job is lost forever.
2. **Anacron**: Designed for workstations, laptops, and intermittent systems. Unlike cron, anacron operates with a granularity of **days**, not minutes. It records job completion timestamps in `/var/spool/anacron/` and executes missed jobs automatically upon machine reboot.

```
+--------------------------------------------------------------------------+
|                     CLASSICAL UNIX SCHEDULING SPOOLS                     |
+--------------------------------------------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
          v                                                   v
+-----------------------------+             +------------------------------+
|     Vixie Cron (crond)      |             |           Anacron            |
|  - Resolution: 1 Minute     |             |  - Resolution: 1 Day         |
|  - Spools:                  |             |  - Spools:                   |
|    /var/spool/cron/crontabs |             |    /var/spool/anacron/       |
|    /etc/crontab             |             |  - Config: /etc/anacrontab   |
|    /etc/cron.d/             |             |  - Delay: Forced start delay |
+-----------------------------+             +------------------------------+
```

---

## 2. Kernel C Structs & Binary Bitfields: Cron Spool Parsing Architecture

In classical Vixie Cron source code, user crontabs are parsed into an in-memory linked list of `entry` structs containing bitfields representing the valid minutes, hours, and days:

```c
/* Classical Vixie Cron Architecture excerpted from entry.h */
typedef struct _entry {
    struct _entry   *next;
    uid_t           uid;            /* Owner UID */
    gid_t           gid;            /* Owner GID */
    char            **envp;         /* Environment variables array */
    char            *cmd;           /* Shell command string to execute */

    /* Bitfields representing temporal firing schedules */
    /* 60 bits for minute: 0-59 */
    unsigned char   minute[8];      /* 8 bytes = 64 bits bitmask */
    /* 24 bits for hour: 0-23 */
    unsigned char   hour[4];        /* 4 bytes = 32 bits bitmask */
    /* 31 bits for day of month: 1-31 */
    unsigned char   dom[4];         /* 4 bytes = 32 bits bitmask */
    /* 12 bits for month: 1-12 */
    unsigned char   month[2];       /* 2 bytes = 16 bits bitmask */
    /* 7 bits for day of week: 0-6 (0=Sun) */
    unsigned char   dow[1];         /* 1 byte = 8 bits bitmask */

    int             flags;
} entry;
```
When cron wakes up every minute, it evaluates whether the current system time matches the bitfield:
```c
#define bit_test(bitstr, bit)     ((bitstr)[(bit) / 8] & (1 << ((bit) % 8)))

bool should_fire(entry *e, struct tm *tm) {
    return bit_test(e->minute, tm->tm_min) &&
           bit_test(e->hour,   tm->tm_hour) &&
           bit_test(e->dom,    tm->tm_mday) &&
           bit_test(e->month,  tm->tm_mon + 1) &&
           bit_test(e->dow,    tm->tm_wday);
}
```

---

## 3. Mathematical Foundations: Crontab Lexical Grammar & Bitmask Matching

A standard crontab entry consists of 5 temporal fields followed by the command string:
$$	ext{Entry} = \langle M, H, 	ext{DoM}, 	ext{Mon}, 	ext{DoW}, 	ext{Cmd}angle$$

Each field $F$ represents a subset of permissible integers $S_F \subseteq \mathbb{Z}_{\ge 0}$:
- Exact value: $n \implies S = \{n\}$
- Asterisk (wildcard): $* \implies S = \{0, 1, \dots, N_{\max}\}$
- Range: $a-b \implies S = \{x \in \mathbb{Z} \mid a \le x \le b\}$
- Step: $a-b/k \implies S = \{x \in \mathbb{Z} \mid a \le x \le b \land (x - a) \equiv 0 \pmod k\}$
- List: $v_1, v_2 \implies S = S_{v_1} \cup S_{v_2}$

### Day of Month vs Day of Week Disjunction:
A notorious edge case in POSIX cron: If **both** `DoM` and `DoW` are specified as non-wildcard values (i.e. neither is `*`), the condition is evaluated as an **OR** (disjunction), rather than an **AND** (conjunction):
$$	ext{Fires}(	ext{Date}) \iff 	ext{Match}(M) \land 	ext{Match}(H) \land 	ext{Match}(	ext{Mon}) \land \Big(	ext{Match}(	ext{DoM}) \lor 	ext{Match}(	ext{DoW})\Big)$$

---

## 4. Compilable C Implementation: Pure POSIX Crontab Bitmask Matcher

Save the following program as `cron_matcher.c`:

```c
/*
 * cron_matcher.c - Lexical Parser and Bitmask Evaluator for Crontab Expressions
 * Demonstrates:
 * 1. Bitmask manipulation for fast temporal matching
 * 2. Step, range, and wildcard expansion
 * 3. Evaluation against system POSIX time structures
 *
 * Compilation:
 *   gcc -O2 -Wall -Wextra -pthread cron_matcher.c -o cron_matcher
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

typedef struct {
    uint64_t minute_mask; /* Bits 0-59 */
    uint32_t hour_mask;   /* Bits 0-23 */
} SimpleCronSchedule;

void set_bit_range(uint64_t *mask, int start, int end, int step)
{
    for (int i = start; i <= end; i += step) {
        *mask |= (1ULL << i);
    }
}

int parse_field(const char *str, int max_val, uint64_t *out_mask)
{
    *out_mask = 0;
    if (strcmp(str, "*") == 0) {
        set_bit_range(out_mask, 0, max_val, 1);
        return 0;
    }

    /* Check for step syntax: */
    if (strncmp(str, "*/", 2) == 0) {
        int step = atoi(str + 2);
        if (step <= 0) return -1;
        set_bit_range(out_mask, 0, max_val, step);
        return 0;
    }

    /* Single integer */
    int val = atoi(str);
    if (val >= 0 && val <= max_val) {
        *out_mask = (1ULL << val);
        return 0;
    }

    return -1;
}

int main(void)
{
    printf("====================================================\n");
    printf("CRONTAB BITMASK PARSER & MATCH ENGINE\n");
    printf("====================================================\n");

    const char *min_expr = "*/15"; /* Every 15 minutes: 0, 15, 30, 45 */
    const char *hour_expr = "*";    /* Every hour */

    uint64_t min_mask = 0;
    uint64_t hour_mask_64 = 0;

    parse_field(min_expr, 59, &min_mask);
    parse_field(hour_expr, 23, &hour_mask_64);
    uint32_t hour_mask = (uint32_t)hour_mask_64;

    printf("[PARSER] Field '%s' -> 64-bit Hex Mask: 0x%016llX\n",
           min_expr, (unsigned long long)min_mask);
    printf("[PARSER] Field '%s'   -> 32-bit Hex Mask: 0x%08X\n",
           hour_expr, hour_mask);

    /* Test evaluation against synthetic timestamps */
    int test_minutes[] = { 0, 14, 15, 29, 30, 45, 59 };
    for (size_t i = 0; i < sizeof(test_minutes)/sizeof(test_minutes[0]); i++) {
        int m = test_minutes[i];
        bool fires = (min_mask & (1ULL << m)) != 0;
        printf("  Minute :%02d -> %s\n", m, fires ? "[TRIGGERED]" : "[SKIPPED]");
    }

    printf("\n[VERIFIED] Bitmask matching operates in O(1) constant time!\n");
    return EXIT_SUCCESS;
}
```

---

## 5. Production War Story: The Stripped PATH Disaster in Production Cron

In 2016, an automated database replication script was migrated from an engineer's interactive shell into `/etc/cron.d/db-backup`:
```cron
0 2 * * * root backup-postgres.sh >> /var/log/backup.log 2>&1
```
The script ran perfectly when executed manually by the engineer via `sudo ./backup-postgres.sh`. However, when executed by cron at 2:00 AM, the backup silently produced an empty 0-byte archive for three straight months. When disaster struck and a restore was attempted, data loss occurred.

**Root Cause**:
Vixie Cron does not source `/etc/profile`, `~/.bashrc`, or user environment variables. Cron runs commands in a minimal environment where `PATH` is hardcoded to `/usr/bin:/bin`. The backup script relied on `/usr/local/bin/aws` and `/opt/pgsql/bin/pg_dump`. 

Because those paths were missing from cron's default environment, the commands failed with `pg_dump: command not found`, but an unhandled pipe error masked the failure and generated an empty tarball.

**The Fix**:
1. Always define explicit environment variables at the top of crontabs:
   ```cron
   SHELL=/bin/bash
   PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
   MAILTO=ops-alerts@internal.service
   ```
2. In shell scripts, always use `set -euo pipefail` so any command failure immediately halts execution.

---

## 6. Verification & CLI Mastery Reference

| Command | Action | Deep Technical Purpose |
| :--- | :--- | :--- |
| `crontab -l` | List User Crontab | Displays spool file located in `/var/spool/cron/crontabs/<user>`. |
| `crontab -e` | Edit Safely | Uses a temporary file and validates syntax before committing to the spool. |
| `crontab -r` | Remove Table | Deletes user's crontab spool file (CAUTION: does not prompt for confirmation). |
| `ls -la /etc/cron.*` | Inspect Directories | Lists system cron directories (`cron.hourly`, `cron.daily`, `cron.weekly`). |
| `anacron -T` | Test Anacrontab | Validates `/etc/anacrontab` configuration syntax without executing jobs. |
