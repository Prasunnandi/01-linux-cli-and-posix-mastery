# Day 22: Control Flow: Conditionals, Loops & Exit Traps

## 1. Architectural Foundations: The Exit Status Mechanism
In Unix, every process terminates by returning an 8-bit unsigned integer ($0 \dots 255$) called the **Exit Status** to the kernel via `exit(status)` or returning from `main()`.

```
+----------------------------------------------------------------------------+
| THE POSIX EXIT STATUS CONVENTION:                                          |
|   - 0: SUCCESS (Truth in Boolean logic)                                    |
|   - Non-Zero (1 - 255): FAILURE (False in Boolean logic)                   |
|                                                                            |
| Standard Exit Codes:                                                       |
|   - 1   : General Catchall Error                                           |
|   - 2   : Misuse of Shell Builtins (e.g. missing syntax)                   |
|   - 126 : Command Invoked Cannot Execute (Permission denied / not exec)    |
|   - 127 : "Command Not Found" (Binary missing from PATH)                   |
|   - 128 + N: Fatal Error Signal "N" (e.g. 128 + 9 = 137 for SIGKILL)       |
+----------------------------------------------------------------------------+
```

Bash conditionals (`if`, `while`, `until`) do not evaluate Boolean expressions like Python or C. Instead, **they execute a command and evaluate its integer exit status (`$?`)**:
```
if COMMAND; then ...
# IF COMMAND returns 0 -> Execute THEN block
# IF COMMAND returns != 0 -> Execute ELSE block
```

---

## 2. Test Constructs: `test`, `[ ]`, and `[[ ]]`

| Construct | Type | Feature Set | Word Splitting & Globbing |
| :--- | :--- | :--- | :--- |
| **`test expression`** | POSIX Builtin | Basic string, integer, file tests (`-f`, `-d`, `-z`, `-n`). | **Vulnerable** (unquoted variables break syntax). |
| **`[ expression ]`** | POSIX Builtin | Exact alias for `test`. Requires closing `]`. | **Vulnerable** (`[ $foo = "bar" ]` fails if `$foo` empty). |
| **`[[ expression ]]`** | **Bash Keyword** | Regex (`=~`), wildcard glob (`== *.txt`), logical `&&` and `||`. | **Safe** (suppresses word splitting and pathname expansion). |

### The `[[ =~ ]]` Regular Expression Operator
The double-bracket keyword supports Perl-compatible extended regular expressions (ERE):
```bash
ip="192.168.1.50"
if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Valid IPv4 syntax"
fi
```
Matched capture groups are automatically populated into the `BASH_REMATCH` array:
- `BASH_REMATCH[0]`: Full match string.
- `BASH_REMATCH[1]`: First capture group.

---

## 3. Exit Traps (`trap ... EXIT`)
In long-running or mission-critical scripts, temporary files, locked mutexes, and child background jobs must be cleaned up reliably regardless of whether the script finishes cleanly, encounters an error, or receives a termination signal (`SIGINT`, `SIGTERM`).

The POSIX `trap` builtin registers an action to be executed when the shell receives a signal or terminates:
```bash
trap 'cleanup_handler' EXIT
```
The pseudocoding signal `EXIT` (signal 0) guarantees that the handler executes:
- When the script reaches the end of its instructions.
- When `exit` is called explicitly from anywhere in the script.
- When the script aborts due to an unhandled signal (if signals are forwarded).

---

## 4. Production Masterclass: Compilable C Command Runner & Exit Status Engine

Save as `exit_status_engine.c` and compile with `gcc -Wall -Wextra -O2 exit_status_engine.c -o exit_status_engine`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

void run_and_inspect_exit(const char *cmd, char *const argv[]) {
    printf("====================================================\n");
    printf("EXECUTING: %s\n", cmd);
    printf("====================================================\n");

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return;
    }

    if (pid == 0) {
        // Child executes binary
        execvp(cmd, argv);
        // If execvp returns, it failed!
        if (errno == ENOENT) exit(127); // Command not found
        if (errno == EACCES) exit(126); // Permission denied
        exit(1);
    }

    int status;
    waitpid(pid, &status, 0);

    if (WIFEXITED(status)) {
        int exit_code = WEXITSTATUS(status);
        printf("[+] Process exited normally with exit code: %d\n", exit_code);
        if (exit_code == 0) {
            printf("    --> Evaluated as: TRUE / SUCCESS in shell conditionals.\n");
        } else {
            printf("    --> Evaluated as: FALSE / ERROR in shell conditionals.\n");
        }
    } else if (WIFSIGNALED(status)) {
        int term_sig = WTERMSIG(status);
        printf("[!] Process killed by signal: %d (%s)\n", term_sig, strsignal(term_sig));
        printf("    --> Bash synthesizes exit code: %d (128 + %d)\n", 128 + term_sig, term_sig);
    }
}

int main(void) {
    // 1. Successful execution
    char *args_true[] = { "true", NULL };
    run_and_inspect_exit("true", args_true);

    // 2. Failed execution
    char *args_false[] = { "false", NULL };
    run_and_inspect_exit("false", args_false);

    // 3. Command not found
    char *args_missing[] = { "non_existent_binary_xyz", NULL };
    run_and_inspect_exit("non_existent_binary_xyz", args_missing);

    return 0;
}
```

---

## 5. Production Post-Mortem: The Dangling Lockfile Cluster Lockup
### The Outage
A distributed cluster backup script ran hourly across 400 servers:
```bash
LOCKFILE="/var/run/cluster_backup.lock"
if [ -f "$LOCKFILE" ]; then
    echo "Backup already in progress. Exiting."
    exit 1
fi
touch "$LOCKFILE"
# Perform rsync...
rm -f "$LOCKFILE"
```
During a scheduled network maintenance window, the `rsync` command timed out, causing an unhandled exit. The lockfile was never deleted. For 7 consecutive days, zero backups executed across the entire enterprise.

### Remediation: Atomic Locking with Guaranteed EXIT Traps
Use atomic directory creation (`mkdir` is atomic in POSIX filesystems) combined with `trap ... EXIT`:
```bash
LOCKDIR="/var/run/cluster_backup.lock"
# Atomic lock acquisition:
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    echo "ERROR: Active lock exists held by PID $(cat "$LOCKDIR/pid" 2>/dev/null)"
    exit 1
fi
echo $$ > "$LOCKDIR/pid"

# GUARANTEE CLEANUP ON ALL EXITS AND SIGNALS:
trap 'rm -rf "$LOCKDIR"' EXIT SIGINT SIGTERM

# Perform critical work safely...
```
Even if the script is killed with `SIGTERM` or crashes halfway through, the `EXIT` trap triggers deterministically, freeing the lock.---

## 6. Arithmetic Evaluation & C-Style Loops: `(( ... ))`
While POSIX shells traditionally used the external `expr` binary for math, modern Bash provides native in-process 64-bit integer arithmetic via the double-parentheses construct:

```bash
# C-style 3-expression for loop:
for ((i = 0, j = 10; i <= 10; i++, j--)); do
    printf "i = %2d, j = %2d, product = %3d\n" "$i" "$j" "$((i * j))"
done
```

### Supported Bitwise & Logical Operators
Inside `(( ... ))`, variables do not require leading `$` signs, and standard C operators are fully supported:
- Bitwise: `<<`, `>>`, `&`, `|`, `^`, `~`
- Logical: `&&`, `||`, `!`, `==`, `!=`, `<`, `<=`
- Ternary: `condition ? val_if_true : val_if_false`

```bash
# Example: Fast bitmask flags checking:
FLAG_READ=1; FLAG_WRITE=2; FLAG_EXEC=4
mode=6 # Read + Write

if (( (mode & FLAG_WRITE) != 0 )); then
    echo "Write permission bit is active"
fi
```

---

## 7. The `case` Statement: Pattern Matching State Machine
For command routers and CLI parsers, `case` statements execute in pure shell memory without regex overhead:

```bash
case "$action" in
    start|launch)
        start_service
        ;;
    stop|halt|terminate)
        stop_service
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {start|stop|status}" >&2
        exit 1
        ;;
esac
```
- `;;`: Terminates the clause.
- `;&`: Falls through to the next clause without testing its pattern.
- `;;&`: Continues testing subsequent pattern clauses.
