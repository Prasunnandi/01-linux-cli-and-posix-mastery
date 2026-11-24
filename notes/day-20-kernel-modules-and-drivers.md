# Day 20: Kernel Modules & Drivers (lsmod, modprobe, kmod)

## 1. Architectural Foundations: Monolithic Kernel with Dynamic Modules
The Linux operating system operates as a **monolithic kernel**: all subsystems (virtual memory, scheduler, filesystems, network stack, and device drivers) execute in a single shared, highly privileged address space (**x86-64 Ring 0**).

To avoid the necessity of recompiling the entire multi-gigabyte kernel image whenever new hardware is added, Linux utilizes **Loadable Kernel Modules (LKMs)**. Modules are relocatable ELF binaries (`.ko` files) dynamically linked into the running kernel via the `init_module()` system call.

```
+----------------------------------------------------------------------------+
| USER SPACE (Ring 3)                                                        |
|   Applications -> glibc -> System Calls (open, read, ioctl)                |
+----------------------------------------------------------------------------+
                                      |
============================== SYSCALL BOUNDARY ==============================
                                      |
+----------------------------------------------------------------------------+
| KERNEL SPACE (Ring 0)                                                      |
|   VFS (Virtual Filesystem)                                                 |
|     |                                                                      |
|     v                                                                      |
|   Character Device Subsystem (Major:Minor dispatch)                        |
|     |                                                                      |
|     v                                                                      |
|   [ Dynamic Kernel Module: my_chardev.ko ]                                 |
|     - struct file_operations (my_open, my_read, my_write, my_ioctl)        |
|     - Direct access to hardware registers / physical memory                |
+----------------------------------------------------------------------------+
```

### Ring 0 vs Ring 3 Constraints
| Property | User Space (Ring 3) | Kernel Space (Ring 0) |
| :--- | :--- | :--- |
| **Fault Handling** | Segmentation Fault terminates process (`SIGSEGV`). | Page Fault causes kernel **Oops** or fatal **Kernel Panic**. |
| **Standard Library** | Full access to `glibc` (`printf`, `malloc`, `fopen`). | **No standard libraries**. Must use kernel API (`printk`, `kmalloc`). |
| **Stack Space** | Virtually unlimited (typically 8 MiB per thread). | Strictly constrained: **Fixed 8 KiB or 16 KiB total stack**! |
| **Execution Context** | Scheduled preemptively by kernel. | Process Context (can sleep) OR Atomic/Interrupt Context (**NEVER SLEEP**). |
| **Concurrency** | POSIX pthreads, mutexes. | Spinlocks, read-copy-update (RCU), atomic bitops, mutexes. |

---

## 2. Character Device Driver Architecture
In Unix, devices are represented as filesystem nodes in `/dev/`.
- **Major Number**: Identifies the driver associated with the device (e.g. Major 1 = memory devices, Major 4 = serial terminals).
- **Minor Number**: Identifies the specific device instance controlled by that driver.

When a userspace process calls `open("/dev/mydevice", O_RDWR)`:
1. The VFS reads the inode's `i_rdev` field to extract the `(major, minor)` pair.
2. The kernel queries `chrdevs[]` table to locate the registered `struct cdev`.
3. The kernel sets `file->f_op = cdev->ops` and invokes the driver's custom `open()` method.

---

## 3. Production Masterclass: Complete Compilable Linux Kernel Module

Save as `my_chardev.c`:

```c
#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/cdev.h>
#include <linux/device.h>

#define DEVICE_NAME "super_char"
#define CLASS_NAME  "super_class"
#define BUFFER_SIZE 1024

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Antigravity Systems Masterclass");
MODULE_DESCRIPTION("Exhaustive POSIX Character Device Driver");
MODULE_VERSION("1.0");

static int    major_number;
static char   kernel_buffer[BUFFER_SIZE];
static size_t message_size = 0;
static struct class*  char_class  = NULL;
static struct device* char_device = NULL;
static DEFINE_MUTEX(device_mutex); // Protect buffer against concurrent race conditions

// Function prototypes for character driver operations
static int     dev_open(struct inode *, struct file *);
static int     dev_release(struct inode *, struct file *);
static ssize_t dev_read(struct file *, char __user *, size_t, loff_t *);
static ssize_t dev_write(struct file *, const char __user *, size_t, loff_t *);

static struct file_operations fops = {
    .owner   = THIS_MODULE,
    .open    = dev_open,
    .read    = dev_read,
    .write   = dev_write,
    .release = dev_release,
};

static int __init chardev_init(void) {
    printk(KERN_INFO "[super_char] Initializing character driver module\\n");

    // Dynamically allocate a major number
    major_number = register_chrdev(0, DEVICE_NAME, &fops);
    if (major_number < 0) {
        printk(KERN_ALERT "[super_char] Failed to allocate major number\\n");
        return major_number;
    }
    printk(KERN_INFO "[super_char] Registered with Major Number %d\\n", major_number);

    // Register device class
    char_class = class_create(CLASS_NAME);
    if (IS_ERR(char_class)) {
        unregister_chrdev(major_number, DEVICE_NAME);
        return PTR_ERR(char_class);
    }

    // Create device node in /dev/super_char automatically via udev
    char_device = device_create(char_class, NULL, MKDEV(major_number, 0), NULL, DEVICE_NAME);
    if (IS_ERR(char_device)) {
        class_destroy(char_class);
        unregister_chrdev(major_number, DEVICE_NAME);
        return PTR_ERR(char_device);
    }

    mutex_init(&device_mutex);
    printk(KERN_INFO "[super_char] Device /dev/%s created successfully\\n", DEVICE_NAME);
    return 0;
}

static void __exit chardev_exit(void) {
    mutex_destroy(&device_mutex);
    device_destroy(char_class, MKDEV(major_number, 0));
    class_unregister(char_class);
    class_destroy(char_class);
    unregister_chrdev(major_number, DEVICE_NAME);
    printk(KERN_INFO "[super_char] Module unloaded cleanly\\n");
}

static int dev_open(struct inode *inodep, struct file *filep) {
    if (!mutex_trylock(&device_mutex)) {
        printk(KERN_WARNING "[super_char] Device is currently busy\\n");
        return -EBUSY;
    }
    printk(KERN_INFO "[super_char] Device opened\\n");
    return 0;
}

static ssize_t dev_read(struct file *filep, char __user *user_buf, size_t len, loff_t *offset) {
    size_t bytes_to_copy;

    if (*offset >= message_size) {
        return 0; // End-of-file
    }

    bytes_to_copy = min(len, (size_t)(message_size - *offset));

    // Safely copy data from Kernel Space to User Space
    if (copy_to_user(user_buf, kernel_buffer + *offset, bytes_to_copy) != 0) {
        return -EFAULT;
    }

    *offset += bytes_to_copy;
    printk(KERN_INFO "[super_char] Sent %zu bytes to userspace\\n", bytes_to_copy);
    return bytes_to_copy;
}

static ssize_t dev_write(struct file *filep, const char __user *user_buf, size_t len, loff_t *offset) {
    message_size = min(len, (size_t)(BUFFER_SIZE - 1));

    // Safely copy data from User Space to Kernel Space
    if (copy_from_user(kernel_buffer, user_buf, message_size) != 0) {
        return -EFAULT;
    }

    kernel_buffer[message_size] = '\\0'; // Null-terminate
    printk(KERN_INFO "[super_char] Received %zu bytes from userspace: %s\\n", message_size, kernel_buffer);
    return message_size;
}

static int dev_release(struct inode *inodep, struct file *filep) {
    mutex_unlock(&device_mutex);
    printk(KERN_INFO "[super_char] Device closed and mutex unlocked\\n");
    return 0;
}

module_init(chardev_init);
module_exit(chardev_exit);
```

### Kernel Makefile
```makefile
obj-m += my_chardev.o

KDIR := /lib/modules/$(shell uname -r)/build

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
```

---

## 4. Production Post-Mortem: Sleeping in Atomic Context Panic
### The Outage
A custom high-frequency trading kernel bypass network driver caused an immediate kernel panic during an options trading session:
`BUG: scheduling while atomic: insmod/1402/0x00000002`
`Call Trace: dump_stack -> __schedule_bug -> __schedule -> schedule -> schedule_timeout -> wait_for_completion`

### Root Cause Analysis
In Linux kernel programming:
1. **Process Context**: Code runs on behalf of a process. It is allowed to sleep, yield CPU, and allocate memory with `GFP_KERNEL` (which may trigger page reclaim or disk I/O).
2. **Interrupt / Atomic Context**: Code runs inside an Interrupt Service Routine (ISR), softirq, tasklet, or while holding a **spinlock**.
   - Holding a spinlock disables kernel preemption on that CPU core.
   - Calling any function that can sleep (e.g. `mutex_lock`, `msleep`, `copy_from_user`, or `kmalloc(GFP_KERNEL)`) while holding a spinlock is a catastrophic bug. If the thread sleeps while holding the spinlock, the thread that would wake it can never acquire the spinlock on that core, creating an unrecoverable kernel deadlock.

### Resolution
1. Change allocation flags inside atomic sections to non-blocking:
   ```c
   void *ptr = kmalloc(size, GFP_ATOMIC); // Never sleeps; pulls immediately from emergency reserve pool
   ```
2. Release spinlocks before invoking functions that can sleep, or transition to a kernel mutex if sleeping is expected.
