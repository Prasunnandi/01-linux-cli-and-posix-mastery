# Hands-On Lab: Day 19 - Linux Sysfs & PCI Device Inspector (`sysfs_hardware_scanner.py`)

## 1. What Are We Building & Why Does It Matter?
On Linux, peripheral hardware (graphics cards, network cards, NVMe SSDs) is discovered and managed via the `/sys/bus/pci/devices/` filesystem.
Every PCI device exposes:
- **Vendor ID** (e.g. `0x8086` for Intel, `0x10de` for NVIDIA).
- **Device ID** (identifying the specific model).
- **Class Code** (e.g. `0x020000` for Ethernet, `0x010802` for NVMe).

In this lab, we build `sysfs_hardware_scanner.py` to parse simulated `/sys` device hierarchies, resolve hex vendor codes to real hardware manufacturers, and decode PCI bus addresses (Domain:Bus:Device.Function).

---

## 2. Python Concepts for Beginners
1. **Hexadecimal String Conversion (`int(hex_str, 16)`)**:
   - In Python, `int("0x8086", 16)` converts hexadecimal text to the integer `32902`.
2. **Lookup Dictionaries**:
   - We map vendor hex strings to human-readable company names:
     ```python
     KNOWN_VENDORS = {
         "0x8086": "Intel Corporation",
         "0x10de": "NVIDIA Corporation",
         "0x10ec": "Realtek Semiconductor",
     }
     ```
3. **Regex or String Parsing (`.split(':')`)**:
   - We parse PCI DBDF addresses like `"0000:03:00.0"` into its component parts: Domain `0000`, Bus `03`, Device `00`, Function `0`.

---

## 3. Step-by-Step Code Walkthrough

```python
def resolve_pci_device(dbdf_address: str, vendor_id: str, device_id: str) -> dict:
    vendor_clean = vendor_id.lower().strip()
    vendor_name = KNOWN_VENDORS.get(vendor_clean, "Unknown Vendor")

    parts = dbdf_address.split(':')
    domain = parts[0]
    bus = parts[1]
    dev_func = parts[2].split('.')
    device = dev_func[0]
    function = dev_func[1]
```
- Splits the DBDF address cleanly and builds a structured dictionary with hardware identity.

---

## 4. How to Run the Script

```bash
cd code/day-19
python sysfs_hardware_scanner.py
```

### Expected Output
```
Scanning PCI Devices:
----------------------------------------------------
Device 1: 0000:00:02.0
  Vendor  : Intel Corporation (0x8086)
  Device  : 0x9bc4 (UHD Graphics 630)
  Topology: Bus 00, Device 02, Function 0
----------------------------------------------------
Device 2: 0000:01:00.0
  Vendor  : NVIDIA Corporation (0x10de)
  Device  : 0x2204 (GeForce RTX 3090)
  Topology: Bus 01, Device 00, Function 0
```

---

## 5. Beginner Exercises to Try
1. Add Qualcomm (`"0x17cb"`) or Broadcom (`"0x14e4"`) to the `KNOWN_VENDORS` dictionary and simulate a wireless NIC.
2. Add a function that groups devices by bus number.
---

## 6. Common Python Errors & How to Fix Them
As a beginner to Python, you may run into these common errors while experimenting:

1. **`ValueError: invalid literal for int() with base 10`**:
   - **Why it happens**: You called `int("hello")` or tried to convert an empty string `""` into a number.
   - **How to fix**: Always inspect what string you are passing into `int()`. Use `.strip()` to remove stray newline characters or check `if s.isdigit():` before converting.
2. **`KeyError: 'some_key'`**:
   - **Why it happens**: You tried to access a dictionary key that does not exist (`metrics["non_existent"]`).
   - **How to fix**: Use the `.get()` method instead: `metrics.get("some_key", default_value)`. This returns `default_value` safely without crashing your program.
3. **`IndexError: list index out of range`**:
   - **Why it happens**: You tried to access `items[5]` when the list only contains 3 items.
   - **How to fix**: Always verify the length of your list with `len(items)` before indexing into it.
4. **`FileNotFoundError`**:
   - **Why it happens**: You attempted to open a file that does not exist in the current working directory.
   - **How to fix**: Print `os.getcwd()` to check where your script is currently looking, or use absolute paths.

---

## 7. Line-by-Line Code Reference

Here is a summary of every standard library function and built-in used in this lab:
- `open(filename, mode)`: Opens a file stream for reading (`'r'`) or writing (`'w'`).
- `len(collection)`: Returns the number of items in a list, string, or dictionary.
- `print(...)`: Outputs text or variable values to the standard output stream (terminal).
- `assert condition, "error message"`: Sanity-checks that internal logic holds true; crashes with message if false.
- `if __name__ == '__main__':`: Standard Python boilerplate that executes test code when run directly from the command line, but does not run when imported as a module by other scripts.

