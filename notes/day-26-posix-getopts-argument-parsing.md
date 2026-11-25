# Day 26: POSIX Argument Parsing with getopts

## 1. Architectural Foundations: POSIX CLI Syntax Standards
Command-line interfaces in Unix must adhere to the **POSIX Utility Syntax Guidelines** (IEEE Std 1003.1, Section 12.2). These guidelines establish universal rules for how flags, arguments, and operands are delimited:
1. Arguments are preceded by a hyphen (`-`).
2. Single-character flags can be grouped: `-a -b -c` is equivalent to `-abc`.
3. Options requiring arguments can accept them with or without spaces: `-o file` or `-ofile`.
4. The special argument `--` indicates the end of options; all subsequent arguments are treated as literal operands.

Bash provides the built-in `getopts` utility to parse options in strict compliance with POSIX standards.

```
+----------------------------------------------------------------------------+
| BASH getopts RUNTIME STATE MACHINE:                                        |
|   - OPTSTRING: "f:vhp:" (Letters followed by ':' require an argument)       |
|   - OPTARG   : Holds the argument string for the current flag              |
|   - OPTIND   : Index of the NEXT argument in $1, $2, $3 to be processed    |
|   - OPTERR   : 1 = Shell prints error messages; 0 = Silent mode            |
+----------------------------------------------------------------------------+
```

---

## 2. Option String Syntax & Silent Error Handling
The option string passed to `getopts` specifies recognized flags:
- `"ab"`: Flags `-a` and `-b` take no arguments (boolean flags).
- `"f:o:"`: Flags `-f` and `-o` require an argument.
- **Leading Colon (`:f:o:`)**: Enables **Silent Mode**:
  - Suppresses standard Bash error messages to stderr.
  - If an unrecognized flag is passed, variable is set to `'?'` and `OPTARG` contains the invalid flag.
  - If a required argument is missing, variable is set to `':'` and `OPTARG` contains the flag that lacked an argument!

```bash
#!/usr/bin/env bash
set -euo pipefail

output_file=""
verbose=0
port=8080

while getopts ":f:vp:h" opt; do
    case "$opt" in
        f) output_file="$OPTARG" ;;
        v) verbose=1 ;;
        p) port="$OPTARG" ;;
        h) echo "Usage: $0 [-f file] [-p port] [-v] [-h]"; exit 0 ;;
        :) echo "ERROR: Option -$OPTARG requires an argument." >&2; exit 1 ;;
        \?) echo "ERROR: Unknown option -$OPTARG." >&2; exit 1 ;;
    esac
done
# Shift out all processed options so $1 points to the first positional operand!
shift $((OPTIND - 1))
```

---

## 3. `getopts` Builtin vs External `getopt` Binary
- **`getopts` (Shell Builtin)**:
  - Part of POSIX standard; works identically across all Unix platforms.
  - Executes directly in shell memory with zero process forks ($O(1)$ startup).
  - Only supports single-hyphen short options (`-f`); does **not** natively parse GNU-style long options (`--file`).
- **`getopt` (External Binary / GNU util-linux)**:
  - Supports GNU long options (`--config=app.conf`).
  - Requires spawning an external subshell process and re-evaluating arguments using `eval set -- "$PARSED"`.
  - Non-portable: macOS / BSD `getopt` behaves completely differently from GNU `getopt`.

---

## 4. Production Masterclass: Compilable C POSIX getopt Implementation

Save as `posix_getopt_engine.c` and compile with `gcc -Wall -Wextra -O2 posix_getopt_engine.c -o posix_getopt_engine`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    printf("====================================================\n");
    printf("POSIX getopt() ARGUMENT PARSER (C Standard)\n");
    printf("====================================================\n");

    int opt;
    char *config_file = NULL;
    int port = 8080;
    int verbose = 0;

    // Option string: "c:p:vh" (c and p require arguments)
    while ((opt = getopt(argc, argv, "c:p:vh")) != -1) {
        switch (opt) {
            case 'c':
                config_file = optarg;
                printf("[OPTION] Config File specified : %s\n", config_file);
                break;
            case 'p':
                port = atoi(optarg);
                printf("[OPTION] Target Port specified : %d\n", port);
                break;
            case 'v':
                verbose = 1;
                printf("[OPTION] Verbose logging ENABLED\n");
                break;
            case 'h':
                printf("Usage: %s [-c config] [-p port] [-v] [operands...]\n", argv[0]);
                return 0;
            case '?':
                fprintf(stderr, "[-] Unrecognized option or missing argument.\n");
                return 1;
        }
    }

    printf("\n[+] Options parsed successfully. Remaining Positional Operands:\n");
    for (int i = optind; i < argc; i++) {
        printf("  Operand [%d]: %s\n", i - optind + 1, argv[i]);
    }

    return 0;
}
```

---

## 5. Production Post-Mortem: The Argument Injection Security Exploit
### The Outage / Vulnerability
A SaaS deployment script allowed users to specify custom branch names for automated builds:
```bash
branch="$1"
git checkout $branch
```
A malicious tenant passed `branch="--help"`, or worse, `branch="-b new_branch"`. The script executed `git checkout -b new_branch`, modifying the git repo configuration and corrupting the build runner.

### Remediation: The Double-Hyphen (`--`) Delimiter
Always use `--` before untrusted user inputs to force the command interpreter to treat all subsequent tokens strictly as non-option arguments:
```bash
branch="$1"
git checkout -- "$branch"
```
The `--` instructs `git` (and all POSIX utilities) to stop parsing options, completely neutralizing argument injection attacks.---

## 6. Industrial Shell CLI Framework: Standard Flag & Env Precedence Pattern
Enterprise CLI scripts must adhere to standard configuration precedence:
$$\text{CLI Flags (Highest)} > \text{Environment Variables} > \text{Configuration File} > \text{Default Values (Lowest)}$$

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Defaults
PORT="${APP_PORT:-8080}"
LOG_LEVEL="${APP_LOG_LEVEL:-INFO}"
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [--] [TARGETS...]

Options:
  -p PORT       Set listening port (Default: 8080, Env: APP_PORT)
  -l LEVEL      Set log level (DEBUG, INFO, WARN, ERROR)
  -d            Dry-run mode (do not commit changes)
  -h            Display this help message and exit
EOF
    exit 0
}

# 2. Parse Options with getopts
while getopts ":p:l:dh" opt; do
    case "$opt" in
        p) PORT="$OPTARG" ;;
        l) LOG_LEVEL="$OPTARG" ;;
        d) DRY_RUN=1 ;;
        h) usage ;;
        :) echo "ERROR: Flag -$OPTARG requires a parameter." >&2; exit 2 ;;
        \?) echo "ERROR: Unknown option -$OPTARG." >&2; exit 2 ;;
    esac
done
shift $((OPTIND - 1))

# 3. Validation
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
    echo "ERROR: Invalid port '$PORT'. Must be 1-65535." >&2
    exit 1
fi
echo "[+] Starting service on port $PORT (Level: $LOG_LEVEL, Dry-run: $DRY_RUN)"
```
This pattern provides standard Unix semantics with zero external dependencies.

---

## 7. Pure Bash Long-Option Parser (Zero External Dependencies)
When you need to support GNU-style long options (`--config`, `--dry-run`, `--port=8080`) without relying on non-portable external `getopt`, you can implement a native option parsing loop:

```bash
#!/usr/bin/env bash
set -euo pipefail

CONFIG=""
PORT=8080
VERBOSE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--config)
            CONFIG="$2"
            shift 2
            ;;
        --config=*)
            CONFIG="${1#*=}"
            shift
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --port=*)
            PORT="${1#*=}"
            shift
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        --) # Explicit delimiter: end of all options
            shift
            break
            ;;
        -*)
            echo "ERROR: Unrecognized option '$1'" >&2
            exit 1
            ;;
        *) # First non-option argument
            break
            ;;
    esac
done

echo "[+] Configuration: CONFIG='$CONFIG', PORT=$PORT, VERBOSE=$VERBOSE"
echo "[+] Remaining Arguments: $@"
```
This loop natively handles both `--flag value` and `--flag=value` formats in pure shell memory with 100% portability.

