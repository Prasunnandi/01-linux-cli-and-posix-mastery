# Day 03: Fast Text Searching with `grep`: Regular Grammars, Thompson NFA, Boyer-Moore & ReDoS Physics

> **Zero External Dependency Guarantee**: This document is an encyclopedic, self-contained masterclass. It contains formal automata theory, Thompson's NFA $\\epsilon$-closure mathematics, Boyer-Moore shift formula proofs, GNU Grep algorithmic optimizations, C and Python implementations, real-world Cloudflare ReDoS post-mortems, and FAANG staff-level interview questions. You do NOT need any textbook or external website.

---

## 1. Executive Summary & Historical Origins

The name **`grep`** was coined in 1973 by Ken Thompson at Bell Labs. In the original Unix text editor `ed`, the command to globally search for a regular expression and print matching lines was:
$$\mathbf{g/re/p} \quad \implies \quad \mathbf{g}\text{lobal} \ / \ \mathbf{r}\text{egular } \mathbf{e}\text{xpression} \ / \ \mathbf{p}\text{rint}$$

Thompson extracted this search routine into a standalone executable. Today, `grep` is the world's most ubiquitous text search tool, capable of scanning multi-terabyte log streams faster than the raw transfer rate of modern disks.

```
THE EVOLUTION OF STRING & PATTERN SEARCH:
+---------------------+      Substring Search       +-----------------------------+
| Exact String Match  | --------------------------> | Boyer-Moore Algorithm (1977)|
+---------------------+                             +-----------------------------+
           |
           v Regular Expression Grammars
+---------------------+      State Automata         +-----------------------------+
| Pattern Matching    | --------------------------> | Thompson NFA / Aho-Corasick |
+---------------------+                             +-----------------------------+
```

---

## 2. Automata Theory: NFAs, DFAs & Thompson's Construction

A regular expression is a declarative syntax for defining a **Regular Language** over an alphabet $\\Sigma$ (Chomsky Hierarchy Type-3 Grammar). To execute a search on physical hardware, the regular expression must be compiled into a state machine.

### 2.1 NFA vs. DFA: The Fundamental Trade-off
* **NFA (Nondeterministic Finite Automaton)**:
  - Can exist in multiple states simultaneously via **$\\epsilon$-transitions** (state transitions that consume zero input characters).
  - Memory required to represent the machine: **$O(M)$** where $M$ is the length of the pattern. Fast compilation!
  - Execution time per character: **$O(M)$**, giving total search time **$O(N \cdot M)$**.
* **DFA (Deterministic Finite Automaton)**:
  - For any given state and input character, there is **exactly one** deterministic next state.
  - Execution time per character: **$O(1)$**, giving blazing linear search time **$O(N)$** independent of pattern complexity!
  - Memory required to represent the machine: In the worst case, converting an NFA to a DFA requires the **Subset Construction Algorithm** (Powerset Construction), which can create up to **$2^M$ states** (state explosion).

```
COMPARISON MATRIX: REGEX SEARCH ENGINES
+-------------------------+-------------------------+-------------------------+
| Feature                 | Thompson NFA / DFA      | Backtracking Engines    |
|                         | (GNU grep, RE2, Go)     | (PCRE, Python re, Perl) |
+-------------------------+-------------------------+-------------------------+
| Time Complexity (Worst) | O(N) Guaranteed Linear  | O(2^N) Exponential!     |
| Memory Bound            | O(M) or O(2^M states)   | O(Recursion Depth)      |
| Catastrophic ReDoS Risk | ZERO (Immune to ReDoS)  | SEVERE (Server Halting) |
| Backreferences support  | No (Not Regular Grammars)| Yes                     |
| Lookaround Assertions   | No                      | Yes                     |
+-------------------------+-------------------------+-------------------------+
```

### 2.2 Thompson's Construction Algorithm
Invented by Ken Thompson in 1968, this algorithm constructs an equivalent NFA from a regular expression in $O(M)$ time using basic building blocks:

```
THOMPSON'S NFA STRUCTURAL ATOMS:

1. Literal Character 'a':
   [ State 1 ] --- 'a' ---> [ (State 2) ]

2. Concatenation 'ab':
   [ State 1 ] --- 'a' ---> [ State 2 ] --- 'b' ---> [ (State 3) ]

3. Alternation 'a|b':
                +--- e ---> [ State 2 ] --- 'a' ---> [ State 3 ] --- e ---+
                |                                                         v
   [ State 1 ] -+                                                       [ (State 6) ]
                |                                                         ^
                +--- e ---> [ State 4 ] --- 'b' ---> [ State 5 ] --- e ---+

4. Kleene Star 'a*':
                     +----------------- e -----------------+
                     |                                     v
   [ State 1 ] --- e ---> [ State 2 ] --- 'a' ---> [ State 3 ] --- e ---> [ (State 4) ]
                               ^                     |
                               +--------- e ---------+
```

---

## 3. Substring Search Physics: The Boyer-Moore Algorithm

When searching for a fixed string (e.g., `grep -F "ERROR"` or `fgrep`), `grep` switches from automata engines to the **Boyer-Moore Algorithm** (or its optimized variant, Boyer-Moore-Horspool).

### 3.1 The Backward Scanning Principle
Most naive search algorithms compare characters from left to right. Boyer-Moore aligns the pattern with the text and compares characters **from right to left (end of pattern backwards)**!
* If the character in the text does not appear anywhere in the pattern, the entire pattern can skip forward by $M$ characters in a single step!
* Boyer-Moore can search text in **sub-linear time**: on average, it inspects only $N / M$ characters.

```
BOYER-MOORE SKIP MECHANISM:
Text:      [ T ][ R ][ A ][ N ][ S ][ A ][ C ][ T ][ I ][ O ][ N ]
Pattern:   [ E ][ R ][ R ][ O ][ R ]
                                 ^
                                 Mismatch! 'S' is not in "ERROR".
                                 We can instantly shift forward by 5 positions!

Shifted:   [ T ][ R ][ A ][ N ][ S ][ A ][ C ][ T ][ I ][ O ][ N ]
                                     [ E ][ R ][ R ][ O ][ R ]
```

### 3.2 The Bad Character Rule Mathematical Formula
For a mismatched character $c$ in the text at pattern position $j$:
$$\\text{Shift}_{\\text{bad}}(c) = \\max(1, \ j - \\text{last\_occurrence}(c))$$

If $c$ does not exist in the pattern, $\\text{last\_occurrence}(c) = -1$, yielding a massive jump of $j - (-1) = j + 1$.

### 3.3 Why GNU Grep is Faster Than Everything Else
In 2010, Mike Haertel (the original author of GNU Grep) published his famous architectural explanation of why GNU Grep outperforms custom C code:
1. **Never Look at Every Byte**: Boyer-Moore skips huge swaths of input bytes.
2. **Unrolled Inner Loops**: The inner character comparison loop is unrolled to keep CPU pipelines saturated without branch mispredictions.
3. **Buffer Boundaries via Sentinels**: Instead of checking `if (ptr >= end_of_buffer)` on every character, GNU Grep appends a newline and the search pattern itself to the end of the memory buffer. The search loop runs without bounds checking until a hit occurs!
4. **Zero-Copy Page Cache Access**: GNU Grep uses `mmap()` or large 64KB page-aligned buffers to avoid userspace memory copies.

---

## 4. Complete C Implementation: Boyer-Moore-Horspool String Searcher

```c
/**
 * boyer_moore_search.c - Production-grade Boyer-Moore-Horspool pattern searcher.
 * Compile: gcc -Wall -Wextra -O3 boyer_moore_search.c -o bm_search
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ALPHABET_SIZE 256

/* Precompute Bad Character Shift Table */
void precompute_bad_char(const char *pattern, int pattern_len, int bad_char[ALPHABET_SIZE]) {
    for (int i = 0; i < ALPHABET_SIZE; i++) {
        bad_char[i] = pattern_len; // Default shift is the full pattern length
    }
    for (int i = 0; i < pattern_len - 1; i++) {
        bad_char[(unsigned char)pattern[i]] = pattern_len - 1 - i;
    }
}

/* Boyer-Moore-Horspool Search Routine */
void search_stream(FILE *stream, const char *pattern) {
    int m = strlen(pattern);
    if (m == 0) return;

    int bad_char[ALPHABET_SIZE];
    precompute_bad_char(pattern, m, bad_char);

    char *line = NULL;
    size_t linecap = 0;
    ssize_t linelen;
    unsigned long line_num = 0;

    while ((linelen = getline(&line, &linecap, stream)) > 0) {
        line_num++;
        int n = (int)linelen;
        int i = 0;

        while (i <= n - m) {
            int j = m - 1;

            // Match from right to left
            while (j >= 0 && pattern[j] == line[i + j]) {
                j--;
            }

            if (j < 0) {
                // Match found!
                printf("Line %lu: %s", line_num, line);
                break; // Move to next line
            }

            // Shift based on the bad character at the end of the window
            i += bad_char[(unsigned char)line[i + m - 1]];
        }
    }
    free(line);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <pattern> [file]\n", argv[0]);
        return EXIT_FAILURE;
    }
    const char *pattern = argv[1];
    if (argc == 2) {
        search_stream(stdin, pattern);
    } else {
        FILE *fp = fopen(argv[2], "r");
        if (!fp) {
            perror(argv[2]);
            return EXIT_FAILURE;
        }
        search_stream(fp, pattern);
        fclose(fp);
    }
    return EXIT_SUCCESS;
}
```

---

## 5. Python High-Performance Regex vs Linear Thompson NFA

Python's standard `re` module uses a backtracking engine (written in C). While rich in features, it is vulnerable to exponential time explosions. For mission-critical linear-time guarantees, the `google-re2` engine compiles regular expressions directly into DFAs:

```python
import time
import re

# Benchmark: Catastrophic Backtracking vs Linear Execution
pattern_backtrack = r"^(a+)+$"
regex_evil = re.compile(pattern_backtrack)

test_string = "a" * 28 + "!" # 28 'a' characters followed by a mismatch

print(f"Testing regex '{pattern_backtrack}' against length {len(test_string)} string...")
start = time.perf_counter()
match = regex_evil.match(test_string)
elapsed = time.perf_counter() - start

print(f"Python standard 're' engine took: {elapsed:.4f} seconds!")
# In GNU grep (grep -E "^(a+)+$"), this takes less than 0.0001 seconds because
# GNU grep uses DFA simulation without backtracking!
```

---

## 6. Real-World Production War Stories

### 6.1 War Story 1: The 2019 Cloudflare 27-Minute Global Outage (ReDoS)
* **The Incident**: On July 2, 2019, at 13:42 UTC, Cloudflare's global network CPU spiked to 100% across all datacenters worldwide, dropping over 80% of global web traffic.
* **The Root Cause**: An engineer deployed a new WAF (Web Application Firewall) rule containing the following regular expression:
  ```regex
  (?:(?:"|'|]|}|\/[\*\s]*|(?:;)?\s*problem)(?:\s*\w+|[\s+]\*\/)[^&]*[a-zA-Z]+.*[a-zA-Z]+=.*)
  ```
* **The Physics**: The subpattern `.*.*=` contains nested Kleene stars with overlapping character classes.
  - When presented with a string of text that had no `=` sign at the end, the PCRE backtracking engine tried every possible permutation of dividing the string between the first `.*` and the second `.*`.
  - For a string of length $N$, the number of backtracking evaluation branches is:
    $$\\mathcal{O}(2^N)$$
  - For a 50-byte input, the engine required $2^{50} \approx 1.12 \times 10^{15}$ operations!
* **The SRE Lesson**: Never use backtracking regex engines (PCRE, Python `re`) in high-throughput proxies. Always enforce DFA engines (Rust `regex`, Go `regexp`, Google `RE2`, GNU `grep`).

---

## 7. Staff-Level Technical Interview Deep-Dives

### Question 1: What makes GNU Grep faster than a simple C program that loops with `strstr()`?
**Exhaustive Answer**:
1. **Algorithm**: `strstr()` in older C standard libraries implemented naive $O(N \cdot M)$ search. GNU Grep uses Boyer-Moore-Horspool, skipping multiple bytes per mismatch.
2. **Memory Architecture**: GNU Grep aligns buffers with kernel page boundaries (4096 bytes) and uses raw unbuffered `read()` system calls into large 64KB blocks, eliminating standard library `fgetc()` function call overhead.
3. **Inner Loop Sentinel**: GNU Grep appends a copy of the search pattern as a sentinel at the end of the buffer, removing the `pointer < buffer_end` check from the inner loop.
4. **Page Cache Optimization**: By streaming sequentially, GNU Grep triggers hardware CPU prefetchers and kernel page cache readahead.

### Question 2: Why do backreferences (e.g. `([a-z]+)\1`) make regular expression matching NP-Complete?
**Exhaustive Answer**:
* By definition, a regular language can be recognized by a Finite State Automaton with fixed, finite memory.
* A backreference `\1` requires the engine to remember an arbitrary, unbounded string previously matched, and verify that the subsequent string is identical.
* This requires context-sensitive grammar capabilities (equivalent to a Turing Machine). In 1989, it was formally proven that determining whether a regular expression with backreferences matches a string is **NP-Complete**, reducible from the 3-SAT Boolean Satisfiability problem!

---

## 8. Complete Verification Checklist (Zero Gaps)
- [ ] What is the origin of the word `grep` in Dennis Ritchie and Ken Thompson's `ed` editor?
- [ ] Draw Thompson's NFA construction for alternation (`a|b`) and Kleene star (`a*`).
- [ ] Why does the Boyer-Moore algorithm scan characters from right to left instead of left to right?
- [ ] Calculate the bad character shift for pattern "TEST" when a mismatch occurs on character 'X'.
- [ ] Explain how nested quantifiers `(a+)+` cause catastrophic backtracking in PCRE but linear time in GNU Grep.
