# Day 23: String Manipulation & Parameter Expansion

## 1. Architectural Foundations: In-Process Parameter Expansion
In shell scripting, spawning external processes like `sed`, `awk`, or `cut` inside loops creates massive process creation overhead.
Each time you write:
```bash
ext=$(echo "$filename" | cut -d'.' -f2) # Spawns 2 forks + 2 execve calls!
```
Over a 100,000-line file, this incurs **200,000 process creations**, degrading a 1-second operation into a 45-minute CPU grind.

Bash provides native, zero-overhead **Parameter Expansions** executed entirely inside the shell's memory space in $O(N)$ string time.

---

## 2. Parameter Expansion Taxonomy

### 1. Default & Alternative Values
- `${VAR:-default}`: If `VAR` is unset or null, evaluate to `default` (does not modify `VAR`).
- `${VAR:=default}`: If `VAR` is unset or null, set `VAR` to `default` and evaluate to `default`.
- `${VAR:?error_msg}`: If `VAR` is unset or null, print `error_msg` to stderr and abort script.
- `${VAR:+override}`: If `VAR` is set, evaluate to `override`; otherwise evaluate to empty string.

### 2. Substring & Slicing
- `${#VAR}`: Returns the length of `$VAR` in characters.
- `${VAR:offset}`: Substring starting at zero-based `offset`.
- `${VAR:offset:length}`: Substring starting at `offset` spanning `length` characters.

### 3. Pattern Trimming (Prefix / Suffix Stripping)
- `${VAR#pattern}`: Remove shortest matching `pattern` from the **beginning**.
- `${VAR##pattern}`: Remove **longest** matching `pattern` from the **beginning**.
- `${VAR%pattern}`: Remove shortest matching `pattern` from the **end**.
- `${VAR%%pattern}`: Remove **longest** matching `pattern` from the **end**.

```
Memory Example: filepath="/usr/local/nginx/logs/access.log.tar.gz"

${filepath#*/}   -> "usr/local/nginx/logs/access.log.tar.gz" (Shortest prefix stripped)
${filepath##*/}  -> "access.log.tar.gz"                      (Longest prefix stripped -> basename!)
${filepath%/*}   -> "/usr/local/nginx/logs"                  (Shortest suffix stripped -> dirname!)
${filepath%%.*}  -> "/usr/local/nginx/logs/access"          (Longest suffix stripped -> root path!)
```

### 4. Search and Replace
- `${VAR/pattern/replacement}`: Replace first occurrence.
- `${VAR//pattern/replacement}`: Replace **all** occurrences.
- `${VAR/#pattern/replacement}`: Replace match if anchored at beginning.
- `${VAR/%pattern/replacement}`: Replace match if anchored at end.

---

## 3. Mathematical Benchmark: Fork Overhead vs In-Process Expansion
Let $N$ be the number of string transformations.
- **External Utility (`cut`/`sed`)**:
  $$T_{\text{ext}} = N \times (T_{\text{fork}} + T_{\text{exec}} + T_{\text{pipe}} + T_{\text{reap}})$$
  On modern Linux x86-64: $T_{\text{fork}} + T_{\text{exec}} \approx 300\mu\text{s} - 800\mu\text{s}$.
  For $N = 100,000$:
  $$T_{\text{ext}} \approx 100,000 \times 500\mu\text{s} = 50\text{ seconds}!$$
- **Native Bash Parameter Expansion**:
  $$T_{\text{native}} = N \times T_{\text{string\_scan}} \approx 100,000 \times 200\text{ns} = 0.02\text{ seconds}!$$
**Native parameter expansion is 2,500x faster than spawning subshell pipes!**

---

## 4. Production Masterclass: Compilable C In-Memory Pattern Matcher

Save as `param_expansion_sim.c` and compile with `gcc -Wall -Wextra -O2 param_expansion_sim.c -o param_expansion_sim`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Simulates ${VAR##*/} (basename)
const char *strip_longest_prefix(const char *str, char delimiter) {
    const char *last = strrchr(str, delimiter);
    return (last) ? last + 1 : str;
}

// Simulates ${VAR%/*} (dirname)
void strip_shortest_suffix(const char *str, char delimiter, char *out_buf, size_t out_size) {
    const char *last = strrchr(str, delimiter);
    if (!last) {
        strncpy(out_buf, str, out_size);
        return;
    }
    size_t len = last - str;
    if (len >= out_size) len = out_size - 1;
    strncpy(out_buf, str, len);
    out_buf[len] = '\0';
}

int main(void) {
    printf("====================================================\n");
    printf("IN-MEMORY PARAMETER EXPANSION ENGINE\n");
    printf("====================================================\n");

    const char *path = "/var/log/kubernetes/pods/ingress-nginx.log.gz";
    printf("Input String: \"%s\"\n\n", path);

    // 1. Longest Prefix Strip: ${path##*/}
    const char *basename = strip_longest_prefix(path, '/');
    printf("[${path##*/}] Stripped longest prefix until '/' -> \"%s\"\n", basename);

    // 2. Shortest Suffix Strip: ${path%/*}
    char dirname[256];
    strip_shortest_suffix(path, '/', dirname, sizeof(dirname));
    printf("[${path%%/*}]  Stripped shortest suffix after '/'  -> \"%s\"\n", dirname);

    // 3. Extension extraction: ${basename#*.}
    const char *ext = strchr(basename, '.');
    if (ext) {
        printf("[${basename#*.}] Extension: \"%s\"\n", ext + 1);
    }

    return 0;
}
```

---

## 5. Production Post-Mortem: The 6-Hour Cloud Migration Stall
### The Outage
A data engineering team wrote a migration script to rename and normalize 500,000 audio recording files in an AWS S3 bucket mount. The script was estimated to take 5 minutes, but stalled for 6 hours, pushing data ingestion beyond SLA.

### Root Cause Analysis
Inside the file processing loop:
```bash
for filepath in /mnt/audio/*.wav; do
    fname=$(basename "$filepath")
    clean_name=$(echo "$fname" | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g')
    ...
done
```
For 500,000 files, the loop invoked `basename`, `tr`, and `sed`, generating **1,500,000 child processes**. The Linux kernel scheduler and MMU spent 98% of CPU cycles creating and tearing down page tables.

### Remediation
Rewritten using pure native parameter expansion:
```bash
for filepath in /mnt/audio/*.wav; do
    fname="${filepath##*/}"               # Replaces basename!
    clean_name="${fname,,}"               # Native Bash 4+ lowercase conversion!
    clean_name="${clean_name//_/-}"       # Native global string replacement!
    ...
done
```
Execution time collapsed from **6 hours down to 4.2 seconds** with zero external subshell forks.---

## 6. Associative Arrays & Dynamic Dictionary Lookups (Bash 4+)
Starting in Bash 4.0, the shell supports genuine hash tables (associative arrays) indexed by arbitrary string keys:

```bash
# Declare an associative array:
declare -A HTTP_STATUS_CODES=(
    [200]="OK"
    [301]="Moved Permanently"
    [400]="Bad Request"
    [403]="Forbidden"
    [404]="Not Found"
    [500]="Internal Server Error"
    [503]="Service Unavailable"
)

# Accessing values:
echo "Code 404: ${HTTP_STATUS_CODES[404]}"

# Iterating over all keys:
for code in "${!HTTP_STATUS_CODES[@]}"; do
    echo "HTTP Status $code -> ${HTTP_STATUS_CODES[$code]}"
done

# Array length:
echo "Total mapped codes: ${#HTTP_STATUS_CODES[@]}"
```

---

## 7. Indirect Parameter Expansion (`${!VAR}`)
When meta-programming or building dynamic configuration loaders, you may need to evaluate a variable whose name is stored in another variable:

```bash
PROD_DB="postgres-cluster-01.internal"
STAGING_DB="postgres-staging-01.internal"

ENV="PROD"
TARGET_VAR="${ENV}_DB" # Evaluates to string "PROD_DB"

# Indirect expansion: dereference the string stored in TARGET_VAR
echo "Connecting to: ${!TARGET_VAR}" # Prints "postgres-cluster-01.internal"!
```
This avoids dangerous `eval` statements, which are vulnerable to arbitrary shell injection attacks.

---

## 8. POSIX Parameter Expansion Equivalents for Portable Shells
While Bash provides `${VAR^^}` (uppercase) and `${VAR//pattern/replace}`, scripts that must run under minimal POSIX `/bin/sh` (such as Alpine Linux BusyBox Docker images) must rely on strictly standardized expansions:

| Feature | Bash 4+ Specific | POSIX Standard (`/bin/sh`) |
| :--- | :--- | :--- |
| **Substring** | `${VAR:4:8}` | `expr substr "$VAR" 5 8` or parameter splitting |
| **Uppercase** | `${VAR^^}` | `$(printf '%s' "$VAR" \| tr '[:lower:]' '[:upper:]')` |
| **Global Replace** | `${VAR//old/new}` | `$(printf '%s' "$VAR" \| sed 's/old/new/g')` |
| **Prefix Strip** | `${VAR#pattern}` | **POSIX Supported** (`${VAR#pattern}`) |
| **Longest Prefix Strip** | `${VAR##pattern}` | **POSIX Supported** (`${VAR##pattern}`) |
| **Suffix Strip** | `${VAR%pattern}` | **POSIX Supported** (`${VAR%pattern}`) |
| **Longest Suffix Strip** | `${VAR%%pattern}` | **POSIX Supported** (`${VAR%%pattern}`) |

By mastering the four POSIX prefix and suffix trimming operators (`#`, `##`, `%`, `%%`), you write lightning-fast scripts that execute with zero dependencies across macOS, BSD, Debian, and minimal Alpine Linux embedded containers.

