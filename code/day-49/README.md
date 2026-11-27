# Day 49: Linux 5-Stage Boot Pipeline & switch_root Simulator

## 1. What Are We Building & Why Does It Matter?
Booting a modern Linux operating system from bare metal to a functional user environment is an intricate, multi-stage engineering pipeline:
1. **UEFI Firmware**: Hardware initialization, Secure Boot verification, and launching EFI binaries.
2. **GRUB2**: Boot menu, loading `vmlinuz` and `initramfs` into RAM.
3. **Kernel Core**: Decompressing `bzImage`, initializing virtual memory, and unpacking `initramfs` into RAM.
4. **Early Userspace (`initramfs`)**: Loading NVMe drivers, decrypting LUKS disks, mounting `/sysroot`, and running **`switch_root`** to purge the RAM disk and transition to the physical disk.
5. **Real Root PID 1**: Launching `systemd` to resolve the service dependency graph and enter `multi-user.target`.

In this lab, we build a **Linux Boot Pipeline Simulator** in pure Python that models state transitions, kernel argument propagation, and the switch_root pivot.

---

## 2. Python Concepts for Beginners

### A. Simulating Pipeline Architectures
A pipeline is an ordered series of operations where each stage feeds into the next. In Python, chaining boolean methods with `and` ensures that if any stage fails, the pipeline aborts cleanly:
```python
success = stage1() and stage2() and stage3()
```

### B. Python Dataclass State Containers
We use a central `@dataclass BootContext` to hold variables that evolve across the stages (e.g. `is_switch_root_done`, `active_target`).

### C. String Formatting for Logging
We append descriptive log strings to an internal `stage_log` list, allowing full forensic verification of the boot progression.

---

## 3. Step-by-Step Code Walkthrough

1. **`BootContext`**: Stores boot parameters (Secure Boot status, kernel cmdline, root device, active target).
2. **`execute_stage1_uefi()`**: Models UEFI firmware loading the EFI bootloader.
3. **`execute_stage2_grub()`**: Simulates GRUB2 parsing kernel arguments and loading the kernel and RAM disk into memory.
4. **`execute_stage3_kernel()`**: Simulates `startup_64()` decompressing the kernel image and mounting the temporary `initramfs` RAM filesystem.
5. **`execute_stage4_early_userspace()`**: Detects root NVMe disks and executes `switch_root` to transition to the physical disk.
6. **`execute_stage5_systemd_init()`**: Starts PID 1 and brings the system to `multi-user.target`.
7. **`main()` Function**: Executes the full sequence and verifies all milestones.

---

## 4. How to Run & Expected Output

Run the script from your terminal:
```bash
python 01-linux-cli-and-posix-mastery/code/day-49/boot_stage_verification_sim.py
```

Expected output:
```text
====================================================
DAY 49: LINUX 5-STAGE BOOT PIPELINE SIMULATOR
====================================================
Stage 1: UEFI POST & EFI System Partition (ESP) Verification
  -> Secure Boot active: Verifying Microsoft/Vendor EFI signatures...
  -> Launching /EFI/BOOT/BOOTX64.EFI (GRUB2)...
Stage 2: GRUB2 Bootloader
  -> Setting kernel cmdline: 'console=tty0 root=/dev/nvme0n1p2 ro quiet'
  -> Loading /boot/vmlinuz and /boot/initramfs.img into RAM...
Stage 3: Kernel Decompression & Early Subsystems
...
Stage 4: Early Userspace (initramfs) & switch_root
  -> Detecting storage controllers. Found /dev/nvme0n1p2 (ext4)
  -> Mounting real root disk to /sysroot (ro)...
  -> Performing switch_root: unlinking initramfs RAM contents & MS_MOVE to /...
Stage 5: Real Root PID 1 systemd Initialization
  -> Reached target: default.target -> multi-user.target

Verification Assertions:
  [PASS] switch_root transition verified.
  [PASS] multi-user.target reached.

[VERIFIED] 5-Stage Linux boot sequence simulation completed 100%!
```

---

## 5. Common Python Errors & Troubleshooting

- **`AttributeError: 'NoneType' object`**: Ensure all methods return boolean `True` on success so that chained `and` conditions evaluate properly.
- **Kernel Argument Parsing**: In real bootloaders, arguments like `init=/bin/bash` override PID 1. Our simulator can be extended to model custom `init` targets.

---

## 6. Beginner Exercises & Challenges

1. **Emergency Shell Intervention**: Add an option `kernel_cmdline = "init=/bin/sh"` that branches directly into an emergency shell at Stage 4, skipping Stage 5.
2. **LUKS Encryption Step**: Add an encrypted disk flag that prompts for a password and decrypts a simulated `/dev/mapper/root` device before mounting.
3. **Boot Blame Calculation**: Add elapsed timestamps to each stage and print a `systemd-analyze` style boot breakdown.
