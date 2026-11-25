# Day 25: Robust Scripting: set -euo pipefail & Traps

## 1. Architectural Foundations: Bash Default Lax Error Behavior
By default, Bash is designed for interactive command lines, where minor errors should not close your terminal window. In non-interactive production scripts, however, this default lax behavior is catastrophic:
- If a command fails, Bash **silently continues** to execute the next line!
- If an unset variable is referenced, Bash substitutes an **empty string** rather than raising an error!
- If a command on the left side of a pipeline fails, Bash **masks the error** and evaluates the pipeline's exit code solely on the rightmost command!

```bash
# THE CLASSIC DISASTER SCENARIO:
rm -rf "$BACKUP_DIR/$TARGET"
# If $BACKUP_DIR is accidentally unset due to a typo:
# Bash expands to: rm -rf "/$TARGET"
# If $TARGET is also empty:
# Bash executes:   rm -rf "/"  <--- DESTROYS ENTIRE FILESYSTEM!
```

---

## 2. The Strict Mode Directive: `set -euo pipefail`

Every production Bash script must start with the strict mode prelude:
```bash
set -euo pipefail
IFS=$'\n\t'
```

### Breakdown of the Flags
1. **`set -e` (`errexit`)**:
   - Immediately aborts script execution if any command exits with a non-zero status ($> 0$).
   - Bypassed if the command is part of an explicit test (e.g. `if cmd; then`, `cmd || fallback`, `while cmd; do`).
2. **`set -u` (`nounset`)**:
   - Treats references to unset variables as fatal errors, printing `var: unbound variable` to stderr and aborting immediately.
   - Prevents catastrophic accidental empty-string expansions.
3. **`set -o pipefail`**:
   - By default, a pipeline `cmd1 | cmd2 | cmd3` returns the exit status of `cmd3`. If `cmd1` crashes with `exit 1`, the pipeline still returns 0 if `cmd3` succeeds!
   - `pipefail` changes this: the pipeline returns the exit status of the **last (rightmost) command to exit with a non-zero status**, or 0 if all succeed.
4. **`IFS=$'\n\t'`**:
   - Internal Field Separator. Removes space from word splitting, preventing filenames with spaces from breaking loops.

---

## 3. Mathematical Truth Table: Pipeline Exit Status with and without `pipefail`

| Pipeline | `cmd1` Exit | `cmd2` Exit | Standard Bash Exit | `pipefail` Exit Status |
| :--- | :--- | :--- | :--- | :--- |
| `cmd1 \| cmd2` | 0 | 0 | **0** (Success) | **0** (Success) |
| `cmd1 \| cmd2` | **1** (Failed) | 0 | **0 (ERROR MASKED!)** | **1 (FAILURE DETECTED)** |
| `cmd1 \| cmd2` | 0 | **2** (Failed) | **2** (Failed) | **2** (Failed) |
| `cmd1 \| cmd2` | **3** (Failed) | **4** (Failed) | **4** (Last command) | **4** (Last failed command) |

---

## 4. Production Masterclass: Compilable C Pipeline Status Evaluator

Save as `pipefail_engine.c` and compile with `gcc -Wall -Wextra -O2 pipefail_engine.c -o pipefail_engine`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

// Simulates the pipeline status vector returned by Bash ${PIPESTATUS[@]}
int evaluate_pipeline_exit(const int *exit_statuses, int count, int pipefail_enabled) {
    if (!pipefail_enabled) {
        // Standard mode: return the exit status of the final command
        return exit_statuses[count - 1];
    }

    // Pipefail mode: scan right-to-left for the first non-zero failure
    for (int i = count - 1; i >= 0; i--) {
        if (exit_statuses[i] != 0) {
            return exit_statuses[i];
        }
    }
    return 0; // All commands succeeded
}

int main(void) {
    printf("====================================================\n");
    printf("POSIX PIPELINE STATUS & PIPEFAIL ENGINE\n");
    printf("====================================================\n");

    // Scenario: mysqldump | gzip > backup.sql.gz
    // mysqldump fails with exit code 2 (connection failed)
    // gzip succeeds with exit code 0 (compressed the error text)
    int pipeline_statuses[] = { 2, 0 };
    int count = 2;

    int std_exit = evaluate_pipeline_exit(pipeline_statuses, count, 0);
    int pipefail_exit = evaluate_pipeline_exit(pipeline_statuses, count, 1);

    printf("Command: mysqldump (exit: %d) | gzip (exit: %d)\n",
           pipeline_statuses[0], pipeline_statuses[1]);
    printf("  Standard Bash Mode Exit  : %d (%s)\n",
           std_exit, std_exit == 0 ? "FALSE SUCCESS! Backup was corrupted!" : "FAILURE");
    printf("  Pipefail Mode Exit (-o)  : %d (FAILURE DETECTED! Script aborts safely)\n",
           pipefail_exit);

    return 0;
}
```

---

## 5. Production Post-Mortem: The Silent 0-Byte Database Backup
### The Outage
A healthcare company ran nightly database backups:
```bash
#!/bin/bash
# Missing: set -euo pipefail
mysqldump -u prod_user -p"$DB_PASS" medical_db | gzip > /backups/db.sql.gz
aws s3 cp /backups/db.sql.gz s3://prod-backups/
```
A database password rotation occurred. `mysqldump` began failing with `Access denied for user 'prod_user'`.
Because `set -o pipefail` was omitted:
1. `mysqldump` returned exit code 2 to the pipeline.
2. `gzip` compressed the empty stream, wrote a 20-byte valid gzip file, and returned exit code 0.
3. Bash evaluated the pipeline exit code as 0 (from `gzip`).
4. The script reported success, uploading empty files to S3 for 6 months until disaster struck and recovery was impossible.

### Remediation
Always enforce strict mode at the top of every script:
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```
With `pipefail`, `mysqldump`'s failure immediately halts the pipeline, prevents the empty upload, and triggers pager alerts.---

## 6. The `trap ... ERR` Exception Handling Engine
While `set -e` aborts on error, it does not provide context on what line or command failed.
By combining `trap ... ERR` with internal shell variables, you can implement an industrial-grade crash reporter:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Error Handler
on_error() {
    local exit_code=$?
    local failed_line=$1
    local failed_command=$2
    echo "[-] SCRIPT CRASHED with Exit Code $exit_code on line $failed_line!" >&2
    echo "[-] Failed Command: $failed_command" >&2
}

trap 'on_error ${LINENO} "$BASH_COMMAND"' ERR
```
If a command like `curl -f internal.service:8080/health` fails on line 42, the trap catches the error, prints the line number, command text, and exit code before aborting.

---

## 7. Safe Temporary File Handling with mktemp
Never hardcode temporary paths like `/tmp/my_temp_file.txt`, which introduces security vulnerabilities (symlink attacks, race conditions, file collisions). Always use `mktemp`:

```bash
# Create a secure temporary directory with mode 0700:
TMP_DIR=$(mktemp -d "/tmp/app_build.XXXXXXXXXX")

# Register automatic deletion on script termination:
trap 'rm -rf "$TMP_DIR"' EXIT

# Safely write temporary files inside TMP_DIR:
echo "payload" > "$TMP_DIR/data.raw"
```
The random `XXXXXXXXXX` sequence is cryptographically generated by the Linux kernel, preventing predictable file creation attacks.

---

## 8. Idempotency & Defensive Script Design
A robust shell script is **idempotent**: executing it multiple times produces the exact same system state without errors or duplicated side effects.

### Rules for Defensive Idempotency
1. **Directory Creation**:
   - BAD: `mkdir /opt/myapp` (Fails if directory already exists).
   - GOOD: `mkdir -p /opt/myapp` (Idempotent: succeeds if exists, creates parents if missing).
2. **File Removal**:
   - BAD: `rm /tmp/data.lock` (Fails if file does not exist).
   - GOOD: `rm -f /tmp/data.lock` (Idempotent: forces deletion without error if missing).
3. **Symbolic Links**:
   - BAD: `ln -s /var/log/app /logs` (Fails if `/logs` symlink already exists).
   - GOOD: `ln -sfn /var/log/app /logs` (Idempotent: `-f` removes existing target, `-n` treats destination symlink to directory as a normal file).
4. **Package Installation Check**:
   ```bash
   install_package() {
       local pkg=$1
       if ! command -v "$pkg" >/dev/null 2>&1; then
           echo "[+] Installing missing dependency: $pkg..."
           sudo apt-get install -y "$pkg"
       fi
   }
   ```
By applying these patterns alongside `set -euo pipefail`, production automation scripts survive transient network interruptions, rerun attempts, and varied environment conditions.
---

## 7. Deep Architectural Mechanics: POSIX vs Bash Strict Mode Edge Cases

### The `pipefail` System Call Pipeline Trace
In standard POSIX sh, the exit status of a pipeline `cmd1 | cmd2 | cmd3` is strictly the exit status of `cmd3`.
Under the hood, when the shell executes a pipeline:
1. It calls `pipe(fds)` to create unidirectional data channels between adjacent processes.
2. It forks child processes for `cmd1`, `cmd2`, and `cmd3`.
3. In each child, `dup2(fds[1], STDOUT_FILENO)` and `dup2(fds[0], STDIN_FILENO)` wire standard streams together.
4. The parent shell waits for all child processes using `wait4()` or `waitpid()`.

```
Without pipefail:
Parent waitpid() returns:
  cmd1 -> exit 1  (Ignored!)
  cmd2 -> exit 0  (Ignored!)
  cmd3 -> exit 0  <-- SHELL RETURNS 0 (Silent failure!)

With pipefail:
Parent inspects PIPESTATUS array:
  PIPESTATUS[0] = 1
  PIPESTATUS[1] = 0
  PIPESTATUS[2] = 0
Parent scans right-to-left: first non-zero status is 1 -> SHELL RETURNS 1!
```

### The Empty Array Trap with `set -u`
A notorious bug in Bash versions before 4.4 occurred when expanding empty arrays under `set -u`:
```bash
set -u
EMPTY_ARRAY=()
echo "${EMPTY_ARRAY[@]}"  # Threw: bash: EMPTY_ARRAY[@]: unbound variable!
```
To write robust cross-platform shell scripts that survive `set -u` across older environments (such as Alpine Linux or RHEL 7), seasoned systems engineers use conditional parameter expansion:
```bash
"${EMPTY_ARRAY[@]:-}"   # Safe fallback: expands to empty string if array is uninitialized
```

### Complete Compilable C Program: Inspecting Pipe Atomicity (`PIPE_BUF`)
```c
/*
 * pipe_atomicity_verify.c - Verifies OS PIPE_BUF atomicity limit
 * Compile: gcc -O2 -Wall -Wextra pipe_atomicity_verify.c -o pipe_atomicity_verify
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <limits.h>

int main(void) {
    printf("POSIX PIPE_BUF Limit on this Kernel: %d bytes\n", PIPE_BUF);
    printf("Writes of <= %d bytes to a pipe are guaranteed ATOMIC by the Linux VFS.\n", PIPE_BUF);
    printf("Concurrent writes exceeding %d bytes may be interleaved, causing stream corruption!\n", PIPE_BUF);
    return 0;
}
```

---

## 8. Production War Story: The Silent Database Migration Catastrophe
In 2018, an enterprise payments gateway ran an automated schema migration during a midnight maintenance window.
The deployment script contained:
```bash
#!/bin/bash
# Missing set -euo pipefail!
mysqldump -u app prod_db | gzip > /backups/db_backup.sql.gz
psql -h pg_prod -U pgapp new_prod_db < /backups/db_backup.sql.gz
```
During execution, `mysqldump` failed immediately due to an invalid password argument (exit code 2). However, `gzip` successfully compressed the empty stream, created a 20-byte empty archive, and exited with status 0!
Because `set -e` without `set -o pipefail` only checks the last command of a pipeline (`gzip`), the shell believed the backup succeeded.
The second command wiped the target database, expecting 40 million transactions, and populated zero rows!
The root cause: the failure of the first pipeline command was silently masked by the POSIX default pipeline behavior. Enforcing `set -euo pipefail` in all production automation is a non-negotiable safeguard.
