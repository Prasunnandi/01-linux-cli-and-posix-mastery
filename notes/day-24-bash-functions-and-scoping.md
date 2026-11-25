# Day 24: Functions, Local Variables & Return Traps

## 1. Architectural Foundations: Bash Call Stack & Scoping
In Bash, functions are not isolated modules with private stack frames; **by default, all variables in Bash have GLOBAL SCOPE**.

If a variable is created or modified inside a function without the `local` keyword, it immediately overwrites any variable with the same name in the global environment!

```
+----------------------------------------------------------------------------+
| GLOBAL SHELL ENVIRONMENT: i=100                                            |
+----------------------------------------------------------------------------+
       |
       v
+----------------------------------------------------------------------------+
| FUNCTION helper():                                                         |
|   for i in {1..5}; do ... done  <-- DANGER: OMITTED 'local i'!             |
+----------------------------------------------------------------------------+
       |
       v
[ Helper exits -> Global i is now 5! Corrupts outer loops! ]
```

---

## 2. The `local` Keyword & The Return Trap

### The Scope Rule of `local`
The `local` keyword restricts variable visibility to the current function and its **descendant child functions** (dynamic scoping, not lexical scoping):
```bash
my_func() {
    local count=42 # Scoped to my_func and any functions my_func calls!
}
```

### The Return Value Trap: `return` vs `echo`
In languages like Python or C, `return x` delivers data back to the caller.
In Bash, **`return` ONLY delivers an 8-bit integer exit status ($0 \dots 255$)**:
```bash
# WRONG: Attempting to return text
get_user() {
    return "john_doe" # CRASH: numeric argument required!
}

# WRONG: Attempting to return integer > 255
compute_total() {
    return 300 # WRAPAROUND: exit status becomes 300 % 256 = 44!
}
```

### How to Properly Return Data from Bash Functions
1. **Stdout Capture (Command Substitution)**:
   ```bash
   get_db_host() {
       echo "db.prod.internal"
   }
   host=$(get_db_host) # Incurs a subshell fork
   ```
2. **Namerefs (Bash 4.3+, Zero-Fork High Performance)**:
   Pass variable by reference using `declare -n`:
   ```bash
   fast_query() {
       declare -n out_ref=$1 # Nameref to variable name passed as argument
       out_ref="10.0.1.25"   # Mutates caller's variable directly!
   }
   fast_query result
   echo "$result" # 10.0.1.25 (Zero forks!)
   ```

---

## 3. Production Masterclass: Compilable C Function Call Stack Simulator

Save as `call_stack_sim.c` and compile with `gcc -Wall -Wextra -O2 call_stack_sim.c -o call_stack_sim`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DEPTH 16

typedef struct {
    char key[32];
    char value[64];
    int  scope_level;
} variable_t;

typedef struct {
    variable_t vars[64];
    int count;
    int current_scope;
} symbol_table_t;

void set_var(symbol_table_t *tbl, const char *key, const char *val, int is_local) {
    int target_scope = is_local ? tbl->current_scope : 0; // 0 = global

    // Check if variable already exists at this scope
    for (int i = 0; i < tbl->count; i++) {
        if (strcmp(tbl->vars[i].key, key) == 0 && tbl->vars[i].scope_level == target_scope) {
            strncpy(tbl->vars[i].value, val, 64);
            return;
        }
    }

    // Allocate new
    strncpy(tbl->vars[tbl->count].key, key, 32);
    strncpy(tbl->vars[tbl->count].value, val, 64);
    tbl->vars[tbl->count].scope_level = target_scope;
    tbl->count++;
}

const char *get_var(symbol_table_t *tbl, const char *key) {
    // Search backwards from innermost scope to global
    for (int s = tbl->current_scope; s >= 0; s--) {
        for (int i = 0; i < tbl->count; i++) {
            if (strcmp(tbl->vars[i].key, key) == 0 && tbl->vars[i].scope_level == s) {
                return tbl->vars[i].value;
            }
        }
    }
    return "(undefined)";
}

int main(void) {
    printf("====================================================\n");
    printf("BASH DYNAMIC SCOPING SIMULATOR\n");
    printf("====================================================\n");

    symbol_table_t syms = { .count = 0, .current_scope = 0 };

    set_var(&syms, "PORT", "8080", 0); // Global
    printf("[Global Scope] PORT = %s\n", get_var(&syms, "PORT"));

    printf("\n[+] Entering Function A (Scope Level 1)...\n");
    syms.current_scope = 1;
    set_var(&syms, "PORT", "9000", 1); // Local to Function A
    printf("  [Inside Func A] PORT = %s (Shadows global!)\n", get_var(&syms, "PORT"));

    printf("\n[+] Exiting Function A...\n");
    syms.current_scope = 0;
    printf("[Global Scope] PORT = %s (Restored cleanly!)\n", get_var(&syms, "PORT"));

    return 0;
}
```

---

## 4. Production Post-Mortem: The Global Loop Counter Collision
### The Outage
An automated deployment script deployed code to 50 Kubernetes clusters sequentially:
```bash
sync_cluster() {
    cluster_id=$1
    for i in {1..3}; do # DANGER: Forgot 'local i'!
        echo "Verifying cluster $cluster_id (Attempt $i)..."
    done
}

for i in "${clusters[@]}"; do
    sync_cluster "$i"
done
```
The script processed the first cluster, and then immediately terminated, leaving 49 clusters unupdated.

### Root Cause Analysis
Because `sync_cluster` did not declare `local i`:
1. The outer loop initialized `i="cluster-01"`.
2. `sync_cluster` entered its loop, overwriting the global variable `i` with integers `1`, `2`, `3`.
3. When `sync_cluster` returned, the outer loop inspected `i` to advance to the next array element, encountered corrupted iteration state, and terminated immediately!

### Remediation
Always declare loop and helper variables with `local`:
```bash
sync_cluster() {
    local cluster_id=$1
    local i # Strictly private to this invocation
    for i in {1..3}; do
        ...
    done
}
```---

## 5. Building an Automatic Stack Trace Generator in Bash
When a large Bash automation script fails in a production CI/CD runner, debugging is difficult without a call stack.
Bash provides three special built-in arrays that track runtime call state:
- **`${BASH_SOURCE[@]}`**: The filenames of all functions in the current call stack.
- **`${BASH_LINENO[@]}`**: The line numbers where each call occurred.
- **`${FUNCNAME[@]}`**: The names of each function in the stack.

```bash
# Production Call-Stack Dumper
print_stack_trace() {
    local depth=${#FUNCNAME[@]}
    echo "====================================================" >&2
    echo "FATAL RUNTIME ERROR ENCOUNTERED: CALL STACK TRACE" >&2
    echo "====================================================" >&2
    for ((i = 1; i < depth; i++)); do
        local file="${BASH_SOURCE[i]}"
        local line="${BASH_LINENO[i-1]}"
        local func="${FUNCNAME[i]}"
        echo "  at ${func}() in ${file}:${line}" >&2
    done
    echo "====================================================" >&2
}

# Trap ERR to dump stack on any command failure:
trap 'print_stack_trace' ERR
```
Now, if any nested function encounters an unhandled non-zero exit code under `set -e`, Bash prints a full Python-style traceback showing the exact caller chain and source lines.
