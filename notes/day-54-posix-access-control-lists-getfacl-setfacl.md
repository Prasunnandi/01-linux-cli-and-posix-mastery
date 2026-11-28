# Day 54: POSIX Access Control Lists (ACLs): getfacl, setfacl, and Kernel Mask Calculation

The standard UNIX discretionary access control (DAC) model (`rwxrwxrwx` for Owner, Group, Others) fails to satisfy enterprise access governance where multiple distinct groups or users require disparate permissions on a single file. POSIX Access Control Lists (POSIX.1e draft / RFC 2821 draft) extend inode metadata with fine-grained access entries. This masterclass examines on-disk filesystem extended attributes (`xattrs`), inheritance rules, and the mathematical calculation of the dynamic ACL Mask.

---

## 1. On-Disk ACL Inode Representation & Kernel Structures

On modern Linux filesystems (`ext4`, `XFS`, `btrfs`), ACLs are stored as Extended Attributes (`xattr`) in the `system` namespace under the key `system.posix_acl_access` (and `system.posix_acl_default` for directories).

### Kernel Struct Definition (`include/linux/posix_acl.h`)
```c
struct posix_acl_entry {
    short           e_tag;    /* ACL entry tag type (ACL_USER, ACL_GROUP, etc.) */
    unsigned short  e_perm;   /* Access permissions (bitmask: 4=R, 2=W, 1=X) */
    union {
        kuid_t      e_uid;    /* Numerical UID for ACL_USER entries */
        kgid_t      e_gid;    /* Numerical GID for ACL_GROUP entries */
    };
};

struct posix_acl {
    refcount_t              a_refcount;
    unsigned int            a_count;  /* Number of entries in ACL array */
    struct rcu_head         a_rcu;
    struct posix_acl_entry  a_entries[]; /* Flexible array member */
};
```

### The Six Permitted POSIX ACL Tag Types (`e_tag`)
1. `ACL_USER_OBJ` (0x01): Permissions for the owning user (matches standard `chmod u`).
2. `ACL_USER` (0x02): Additional named user (e.g. `user:alice:r-x`).
3. `ACL_GROUP_OBJ` (0x04): Permissions for the owning group (matches standard `chmod g` when no mask exists).
4. `ACL_GROUP` (0x08): Additional named group (e.g. `group:analytics:rw-`).
5. `ACL_MASK` (0x10): Maximum allowable permissions for all named users, named groups, and owning group.
6. `ACL_OTHER` (0x20): Permissions for users matching none of the above (matches `chmod o`).

---

## 2. The ACL Mask: Mathematical Intersection & Derivation

The existence of an `ACL_MASK` entry radically alters DAC evaluation. The mask defines an upper bound (ceiling) on permissions. Even if an entry grants `rwx`, if the mask is `r--`, effective access is strictly read-only.

### The Effective Permission Intersection Formula
Let $P_i$ be the permission bitmask granted to a specific named user or named group ($P_i \subseteq \{R, W, X\}$).
Let $M$ be the mask permission bitmask.
The effective permission $E_i$ awarded by the kernel is the bitwise logical AND intersection:

$$E_i = P_i \cap M$$

In binary arithmetic ($R=4, W=2, X=1$):
$$E_i = P_i \ \& \ M$$

### Automatic Mask Recalculation
Whenever `setfacl` modifies an ACL without an explicit `--no-mask` parameter, the kernel recalculates the mask $M$ as the union of all named users, owning group, and named groups:

$$M = P_{\text{GROUP\_OBJ}} \cup \left( \bigcup_{u \in \text{Users}} P_u \right) \cup \left( \bigcup_{g \in \text{Groups}} P_g \right)$$

```text
Named User (alice):    r - x  (101_2)
ACL Mask:              r w -  (110_2)
-------------------------------------
Effective Permission:  r - -  (100_2) -> Execution DENIED!
```

---

## 3. Kernel VFS Permission Evaluation Algorithm

When an application invokes an `open(..., O_RDWR)` or `stat()` syscall on a file protected by POSIX ACLs, the Linux kernel VFS executes `check_acl()` in `fs/namei.c`:

```text
Is Process EUID == Inode UID (Owner)?
       |
       +--> YES: Use ACL_USER_OBJ permissions. Done.
       |
       +--> NO: Check Named Users (ACL_USER):
                  Does Process EUID match any named user?
                  |
                  +--> YES: Effective = Entry_Perm & ACL_MASK. Check access. Done.
                  |
                  +--> NO: Check Groups:
                             Is Process in Inode Primary Group OR any Named Group?
                             |
                             +--> YES: Collect all matching groups (ACL_GROUP_OBJ + ACL_GROUP)
                             |         Union permissions: P_union = Union(P_matched)
                             |         Effective = P_union & ACL_MASK. Check access. Done.
                             |
                             +--> NO: Use ACL_OTHER permissions. Done.
```

---

## 4. Compilable C Implementation: Querying and Calculating ACLs via `<sys/acl.h>`

Compile with: `gcc -O2 -Wall -Wextra inspect_acl.c -o inspect_acl -lacl`

```c
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/acl.h>
#include <acl/libacl.h>
#include <pwd.h>
#include <grp.h>

void print_acl_details(const char *filepath) {
    acl_t acl = acl_get_file(filepath, ACL_TYPE_ACCESS);
    if (acl == NULL) {
        perror("acl_get_file failed (filesystem might not support ACLs)");
        return;
    }

    char *text_representation = acl_to_text(acl, NULL);
    printf("Raw ACL text for '%s':\n%s\n", filepath, text_representation);
    acl_free(text_representation);

    /* Iterate through individual ACL entries */
    acl_entry_t entry;
    int entry_id = ACL_FIRST_ENTRY;

    printf("--- Parsed Entry Analysis ---\n");
    while (acl_get_entry(acl, entry_id, &entry) == 1) {
        entry_id = ACL_NEXT_ENTRY;
        acl_tag_t tag_type;
        acl_get_tag_type(entry, &tag_type);

        acl_permset_t permset;
        acl_get_permset(entry, &permset);

        int r = acl_get_perm(permset, ACL_READ);
        int w = acl_get_perm(permset, ACL_WRITE);
        int x = acl_get_perm(permset, ACL_EXECUTE);

        switch (tag_type) {
            case ACL_USER_OBJ:
                printf("Owner User: %c%c%c\n", r?'r':'-', w?'w':'-', x?'x':'-');
                break;
            case ACL_USER: {
                uid_t *uid_ptr = (uid_t *)acl_get_qualifier(entry);
                struct passwd *pwd = getpwuid(*uid_ptr);
                printf("Named User (%s [UID %d]): %c%c%c\n",
                       pwd ? pwd->pw_name : "unknown", *uid_ptr,
                       r?'r':'-', w?'w':'-', x?'x':'-');
                acl_free(uid_ptr);
                break;
            }
            case ACL_MASK:
                printf("ACL MASK: %c%c%c\n", r?'r':'-', w?'w':'-', x?'x':'-');
                break;
            case ACL_OTHER:
                printf("Other: %c%c%c\n", r?'r':'-', w?'w':'-', x?'x':'-');
                break;
            default:
                break;
        }
    }

    acl_free(acl);
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        printf("Usage: %s <path_to_file>\n", argv[0]);
        return EXIT_FAILURE;
    }

    print_acl_details(argv[1]);
    return EXIT_SUCCESS;
}
```

---

## 5. Production Post-Mortem: The `chmod` Inadvertent Mask Destruction

### Incident Overview
On a production NFS cluster holding multi-terabyte financial analytics datasets, a junior systems administrator attempted to make a directory group-executable:
```bash
chmod g+x /data/financial_models/
```
Immediately, all downstream automated ETL pipelines began throwing `EACCES (Permission denied)` errors.

### Mechanism of the Outage
Under POSIX ACL semantics, executing `chmod g+<perms>` on a file or directory with an active ACL does **not** modify `ACL_GROUP_OBJ`. Instead, POSIX specifies that `chmod` on the group bits **overwrites the `ACL_MASK`**!
1. The original ACL had an explicit mask: `mask::rwx`.
2. The directory permissions prior to the command were `drwxr--r--+`.
3. Running `chmod g+x` set the group bitfield to `r-x`.
4. The kernel interpreted this as a command to reset the ACL Mask to `r-x`.
5. The named group entry for the analytics write-engine was `group:etl_writers:rwx`.
6. Effective permissions collapsed to:
$$E_{\text{etl}} = \text{rwx} \cap \text{r-x} = \text{r-x}$$
Write access was stripped instantly from the ETL engine, terminating batch database ingests.

### Mitigation & Hardening Rules
1. **Never use `chmod` on ACL-managed assets**: When files utilize POSIX ACLs (indicated by the `+` suffix in `ls -l`), all permission adjustments must strictly be executed via `setfacl`:
```bash
setfacl -m g::rwx,m::rwx /data/financial_models/
```
2. **Default Directory ACLs**: Always assign Default ACLs (`setfacl -d -m ...`) on shared team directories so that child files automatically inherit correct permission sets without administrative intervention.
---

## 6. Default ACLs & Directory Tree Inheritance

POSIX ACLs distinguish between **Access ACLs** (which govern immediate access to a file or directory) and **Default ACLs** (which define permission templates inherited by newly created child nodes).

### Inheritance Rules for New Inodes
When a process creates a file or subdirectory inside a parent directory possessing a `system.posix_acl_default` xattr:
1. The kernel copies the parent's Default ACL to become the child's Access ACL.
2. If the child is a directory, it also inherits the parent's Default ACL as its own Default ACL.
3. The newly assigned Access ACL is combined with the process creation mode (`umask` & `mode` argument in `open(..., O_CREAT)`):

$$P_{\text{child}} = P_{\text{default}} \cap (\sim \text{umask})$$

```bash
# Set default ACL ensuring 'developers' group always has read/write on new files
setfacl -d -m g:developers:rw- /srv/shared_project/

# Verify inherited attributes
touch /srv/shared_project/new_file.txt
getfacl /srv/shared_project/new_file.txt
# Output confirms: group:developers:rw- inherited automatically!
```
