# 🛡️ Day 5: Linux Permissions & Demystifying `chmod 777` vs `755`

> **Zero External Dependency Rule**: Everything you need to master this topic is contained right here in this document. You do NOT need to visit any external website or search Google.

---

## 1. The Core Problem: Why Do File Permissions Exist?

Linux was designed from day one as a **Multi-User Operating System**.
In an enterprise or university setting, 100 different developers, scientists, or students might be logged into the same Linux server simultaneously.

If there were no permissions:
* User A could peek into User B's private bank statements or passwords.
* An intern could accidentally run `rm -rf /` and wipe out the entire production database.

To prevent chaos, the Linux kernel attaches an explicit **Permission Bitmask** to every single file and folder on the disk.

---

## 2. Real-World Analogy: The 3 Rings of Security

Every file on your computer categorizes the people of the world into **3 distinct classes**:

```
                       THE THREE AUDIENCE CLASSES
          ┌──────────────────────────────────────────────────┐
          │  1. USER (u)   : The individual who owns the file│
          │  2. GROUP (g)  : The team/department sharing it  │
          │  3. OTHER (o)  : Everyone else in the world      │
          └──────────────────────────────────────────────────┘
```

For each of these three classes, the operating system answers three simple yes/no questions:

```
   CAN THEY READ? (r)     CAN THEY WRITE? (w)     CAN THEY EXECUTE? (x)
         [4]                      [2]                      [1]
```

* **`r` (Read)**: Can they open, inspect, and view the contents of the file?
* **`w` (Write)**: Can they edit, modify, overwrite, or delete the file?
* **`x` (Execute)**: Can they run the file as an application or program?

---

## 3. The Octal Number System: The Math of `7`

Why do developers type numbers like `chmod 755` or `chmod 644`?
Because computers think in binary bits! Each permission is literally a single bit:

```
Bit Position:     2^2       2^1       2^0
Permission:      Read      Write    Execute
Symbol:           r          w         x
Decimal Value:    4          2         1
```

Now, calculate any combination simply by adding the numbers:

| Desired Permission Combination | Math Formula | Final Number |
| :--- | :---: | :---: |
| **No Access At All** | $0 + 0 + 0$ | **`0`** |
| **Execute Only** (`--x`) | $0 + 0 + 1$ | **`1`** |
| **Write Only** (`-w-`) | $0 + 2 + 0$ | **`2`** |
| **Write + Execute** (`-wx`) | $0 + 2 + 1$ | **`3`** |
| **Read Only** (`r--`) | $4 + 0 + 0$ | **`4`** |
| **Read + Execute** (`r-x`) | $4 + 0 + 1$ | **`5`** |
| **Read + Write** (`rw-`) | $4 + 2 + 0$ | **`6`** |
| **Read + Write + Execute** (`rwx`) | $4 + 2 + 1$ | **`7`** |

---

## 4. Decoding the 3-Digit Codes Used in Production

When you run `chmod <3-digits> <file>`, the three digits represent:
* **Digit 1**: What the **USER (Owner)** can do.
* **Digit 2**: What the **GROUP (Team)** can do.
* **Digit 3**: What **OTHERS (Public)** can do.

```
                         USER      GROUP     OTHERS
                          │          │         │
      chmod 755  ──────►  7          5         5
                        (rwx)      (r-x)     (r-x)
```

### The 4 Most Important Codes in the Software Industry:

### 1. `chmod 755` (The Web Server / Public Script Standard)
* Owner: `7` (`rwx` - Can read, edit, and run).
* Group: `5` (`r-x` - Can read and run, cannot edit).
* Others: `5` (`r-x` - Can read and run, cannot edit).
* **Use Case**: Used for public scripts, web server directories, and binaries.

### 2. `chmod 644` (The Standard File Permission)
* Owner: `6` (`rw-` - Can read and edit).
* Group: `4` (`r--` - Can only read).
* Others: `4` (`r--` - Can only read).
* **Use Case**: Used for HTML files, CSS files, images, documents, and configuration files.

### 3. `chmod 600` / `700` (The Private Key / Secret Standard)
* Owner: `6` (`rw-`) or `7` (`rwx`).
* Group: `0` (`---` - Zero access).
* Others: `0` (`---` - Zero access).
* **Use Case**: Mandatory for SSH private keys (`~/.ssh/id_rsa`). SSH will refuse to connect if your private key is readable by anyone else!

### 4. `chmod 777` (⚠️ THE BIGGEST SECURITY SIN)
* Everyone in the entire world has full read, write, and execute permissions.
* Anyone on your machine can delete or inject malicious code into the file.
* **Rule**: Never run `chmod 777` in production! If you have a permission error, diagnose the correct user/group ownership instead of opening all gates.

---

## 5. What Does "Execute (`x`)" Mean on a Directory?

On a normal file, `x` means "run this script/program".
**On a directory/folder, `x` means something completely different**:
* `r` on a directory: You can list the files inside it (`ls`).
* `w` on a directory: You can create or delete files inside it.
* **`x` on a directory**: You can **enter** the directory (`cd`) and access files inside it! If a directory lacks `x` permission, you cannot `cd` into it, even if you have read permission!

---

## 6. Complete Self-Contained Q&A

**Q1: If a file has permission string `rwxr-xr--`, what is its 3-digit octal number?**  
**Answer**:
* User: `rwx` = $4 + 2 + 1 = 7$
* Group: `r-x` = $4 + 0 + 1 = 5$
* Others: `r--` = $4 + 0 + 0 = 4$  
Result: **`754`**.

**Q2: Why does SSH reject your private key if permissions are set to `chmod 777`?**  
**Answer**: Because `chmod 777` means other users on the system can read your private key. OpenSSH has a strict built-in security check that immediately aborts connection with `"Permissions 0777 for id_rsa are too open"` until you change it to `chmod 600`.

**Q3: How do you add execute permissions to a script without changing read or write permissions?**  
**Answer**: Use symbolic syntax: `chmod +x script.sh`.

---

## 7. Hands-on Lab Verification

Run the interactive calculator in `code/day-05/`:
```bash
python code/day-05/permission_calculator.py
```
Test converting any 3-digit octal code into its exact permission string and vice versa!
