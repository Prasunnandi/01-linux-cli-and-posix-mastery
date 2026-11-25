# Day 21: Bash Internals: Subshells, Env & Scoping

## 1. Architectural Foundations: The Shell Execution Model
The Unix shell is not simply a command-line interpreter; it is a high-level programming language built directly atop the POSIX process management primitives: `fork()`, `execve()`, `waitpid()`, and `pipe()`.

When the user enters a command in Bash, the shell parses the input line into an Abstract Syntax Tree (AST), performs expansions, and executes the commands either in the current execution environment (builtins, functions, source) or in an isolated child process.

```
+----------------------------------------------------------------------------+
| PARENT SHELL (PID: 1000, e.g. /bin/bash)                                   |
|   - Variables: FOO="global"                                                |
|   - Environment Table: environ -> ["PATH=...", "HOME=...", "FOO=global"]  |
|   - Open File Descriptors: 0 (stdin), 1 (stdout), 2 (stderr)               |
+----------------------------------------------------------------------------+
                   |
     fork() system call (Clones address space via Copy-on-Write)
                   v
+----------------------------------------------------------------------------+
| SUBSHELL CHILD PROCESS (PID: 1001)                                         |
|   - Receives identical copy of memory, open FDs, and variable state.       |
|   - Modifies FOO="mutated" in child address space.                         |
|   - Parent memory remains 100% UNTOUCHED!                                  |
+----------------------------------------------------------------------------+
                   |
             exit(0) terminates child
                   v
[ Parent reaps child via waitpid() -> FOO is STILL "global" ]
```

---

## 2. Process Inheritance: Memory Isolation & The Environment Table
In the POSIX standard, every process possesses an execution context containing:
1. **Open File Table**: File descriptors pointing to open file descriptions in kernel space.
2. **Current Working Directory (`cwd`)**: Tracked in `task_struct->fs->pwd`.
3. **User and Group IDs (`cred`)**: Real, effective, and saved credentials.
4. **Environment Array (`char **environ`)**: A null-terminated array of null-terminated strings formatted as `KEY=VALUE`.

### The Fundamental Rule of Scoping
In Unix, **information only flows DOWN the process tree (parent to child), NEVER UP (child to parent)**.
When a subshell or external program modifies a variable, changes directory (`cd`), or alters an environment variable, it operates strictly within its private virtual memory pages. When the child process terminates, its entire address space is destroyed by the kernel MMU.

### Subshells vs Command Grouping
Bash provides two distinct syntax constructs for grouping commands:
1. **Parentheses `( ... )` - Subshell Execution**:
   - Forces an explicit `fork()` system call.
   - Executes in an isolated child process.
   - Any side effects (e.g. `cd /tmp`, `export VAR=123`) die upon exiting the closing parenthesis.
2. **Braces `{ ...; }` - Grouping in Current Shell**:
   - Does NOT fork. Executes directly in the current process context.
   - Side effects persist in the calling shell!

### The Pipeline Subshell Trap
In POSIX shells, each command in a pipeline (`cmd1 | cmd2 | cmd3`) is executed in a **separate subshell**:
```bash
count=0
cat access.log | while read line; do
    ((count++))
done
echo "Processed: $count" # PRINTS 0!
```
Because the `while` loop runs inside a forked subshell on the right side of the pipe, its incremented `count` vanishes upon EOF!
- **POSIX-Compliant Fix (Process Substitution)**:
  ```bash
  while read line; do
      ((count++))
  done < <(cat access.log) # while loop executes in main shell process!
  ```
- **Bash Option**: `shopt -s lastpipe` (runs the last command of a non-interactive pipeline in the main shell).

---

## 3. Mathematical Proof of Process Memory Independence
Let the parent process address space be $M_{\text{parent}}$ and the child address space be $M_{\text{child}}$.
Upon invocation of `fork()`:
$$M_{\text{child}} \leftarrow M_{\text{parent}} \quad (\text{virtual copy with COW bit set in page table})$$
For any variable address $A_v$:
$$\text{Read}(M_{\text{parent}}, A_v) = \text{Read}(M_{\text{child}}, A_v) = V_0$$
When the child writes $V_1$ to address $A_v$:
1. The CPU MMU catches a page write-fault because the page is marked read-only for Copy-on-Write.
2. The kernel allocates a new physical frame $P_{\text{new}}$ and updates the child's page table:
   $$\text{PTE}_{\text{child}}(A_v) \leftarrow P_{\text{new}}, \quad \text{PTE}_{\text{parent}}(A_v) \leftarrow P_{\text{orig}}$$
3. The write completes on $P_{\text{new}}$:
   $$\text{Write}(M_{\text{child}}, A_v, V_1) \implies \text{Read}(M_{\text{child}}, A_v) = V_1$$
4. The parent physical page $P_{\text{orig}}$ remains unaltered:
   $$\text{Read}(M_{\text{parent}}, A_v) = V_0$$
This guarantees absolute memory isolation between parent shell and subshell without shared memory primitives.

---

## 4. Production Masterclass: Compilable C Shell Subshell & Fork Demonstrator

Save as `subshell_engine.c` and compile with `gcc -Wall -Wextra -O2 subshell_engine.c -o subshell_engine`:

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <errno.h>

extern char **environ;

void print_process_state(const char *label, int local_var) {
    printf("[%s] PID: %d, Parent PID: %d | local_var = %d | ENV['TEST_KEY'] = '%s'\n",
           label, getpid(), getppid(), local_var,
           getenv("TEST_KEY") ? getenv("TEST_KEY") : "(null)");
}

int main(void) {
    printf("====================================================\n");
    printf("POSIX SUBSHELL & FORK ISOLATION DEMONSTRATOR\n");
    printf("====================================================\n");

    int local_var = 100;
    setenv("TEST_KEY", "PARENT_VALUE", 1);

    print_process_state("Parent Initial State", local_var);

    printf("\n[+] Spawning simulated Subshell via fork()...\n");
    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        // CHILD / SUBSHELL PROCESS
        printf("\n---> [CHILD ENTERED] Modifying variables in child address space...\n");
        local_var = 999; // Modify stack variable
        setenv("TEST_KEY", "CHILD_MUTATED_VALUE", 1); // Modify environment array

        print_process_state("Child Mutated State", local_var);

        printf("---> [CHILD EXITING] Subshell terminating.\n");
        exit(0);
    }

    // PARENT PROCESS
    int status;
    waitpid(pid, &status, 0); // Wait for subshell to finish

    printf("\n[+] Subshell exited. Inspecting Parent Process State...\n");
    print_process_state("Parent Post-Subshell", local_var);

    if (local_var == 100 && strcmp(getenv("TEST_KEY"), "PARENT_VALUE") == 0) {
        printf("\n[SUCCESS] Memory isolation verified: Child mutations had exactly ZERO effect on Parent!\n");
    } else {
        printf("\n[FAIL] Memory isolation violated!\n");
    }

    return 0;
}
```

---

## 5. Production Post-Mortem: The Pipeline Loop Zero-Count Outage
### The Outage
A high-throughput log ingestion daemon responsible for archiving AWS S3 billing events deployed a new Bash aggregator script:
```bash
total_cost=0
cat hourly_records.csv | while IFS=',' read -r timestamp client cost; do
    total_cost=$(echo "$total_cost + $cost" | bc)
done
# Send metric to Datadog:
curl -X POST "api.internal.service/metrics" -d "{\"metric\": \"billing.total\", \"value\": $total_cost}"
```
The billing dashboard reported `$0.00` total revenue across 14 consecutive days, resulting in automated alerts firing to executive leadership.

### Root Cause Analysis
The script author piped `cat hourly_records.csv` into `while read ...`.
Under POSIX standards, the pipe operator `|` forks both left-hand and right-hand operands into separate subshell processes.
1. The subshell executed the loop, reading thousands of rows and accumulating `total_cost` in its private memory.
2. Upon EOF, the subshell process terminated. All memory was reclaimed by the Linux kernel.
3. The parent shell, which never ran the loop, evaluated `$total_cost`, which was still `0`!

### Remediation
Eliminate the pipe subshell by using input redirection with process substitution:
```bash
total_cost=0
while IFS=',' read -r timestamp client cost; do
    total_cost=$(echo "$total_cost + $cost" | bc)
done < <(grep -v '^#' hourly_records.csv)

echo "Audited Cost: $total_cost" # Correctly prints aggregated revenue!
```---

## 6. The 12-Phase Bash Command Line Processing Pipeline
When a line of text is submitted to Bash, it passes through an exact, sequential 12-phase transformation engine before any binary is executed:

```
Raw Input String (e.g. echo ~/"$USER"/{a,b}/*.log)
  |
  v
1. Tokenization & Quoting Detection (Splits into words and operators)
  |
  v
2. Parsing & AST Construction (Builds Abstract Syntax Tree of commands & pipes)
  |
  v
3. Alias Expansion (If interactive; disabled in non-interactive scripts)
  |
  v
4. Brace Expansion: {a,b} -> a b
  |
  v
5. Tilde Expansion: ~ -> /home/username
  |
  v
6. Parameter & Variable Expansion: $USER -> "alice"
  |
  v
7. Command Substitution: $(date) or `cmd` (Forks subshell and reads stdout)
  |
  v
8. Arithmetic Expansion: $((x + y)) (Evaluates 64-bit signed integers)
  |
  v
9. Process Substitution: <(cmd) (Creates /dev/fd/N FIFO pipe)
  |
  v
10. Word Splitting: Evaluates IFS (Space, Tab, Newline by default)
  |
  v
11. Pathname Expansion (Globbing): *.log matches directory entries
  |
  v
12. Quote Removal: Eliminates quotes from final arguments
  |
  v
Redirection Setup -> fork() -> execve() system call
```

### The Critical Takeaway on Quoting
Because Word Splitting (Phase 10) and Pathname Expansion (Phase 11) occur **AFTER** Parameter Expansion (Phase 6), an unquoted variable containing spaces (e.g. `file="my document.pdf"`) will be split into two separate words by the word splitter!
Surrounding variables with double quotes (`"$file"`) tells the parser to skip Phase 10 and 11, preserving the string as a single atomic argument.
