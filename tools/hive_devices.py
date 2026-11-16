#!/usr/bin/env python3
"""List the devices Windows enumerated and which driver each one got.

Reads a SYSTEM hive pulled from the phone (tools/win_logs.sh) and prints
every Enum\\ACPI device: hardware ID, instance, description, bound service.
A device without a service had no driver installed. Also reports whether
the hive is dirty (sequence numbers differ: unsaved changes still in the
.LOG1/.LOG2 transaction logs) and the USB role switch default.

Example:
    hive_devices.py out/win-logs/System32_config_SYSTEM
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_bcd import Hive  # noqa: E402


def sz(vals, name):
    t, d = vals.get(name.lower(), (0, b""))
    if t in (1, 2):
        return d.decode("utf-16le", "replace").rstrip("\0")
    if t == 7:
        return ";".join(x for x in d.decode("utf-16le", "replace").split("\0") if x)
    if t == 4 and len(d) == 4:
        return str(struct.unpack("<I", d)[0])
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hive")
    args = ap.parse_args()

    data = open(args.hive, "rb").read()
    seq1, seq2 = struct.unpack_from("<II", data, 4)
    print(f"hive sequence {seq1}/{seq2}: {'clean' if seq1 == seq2 else 'DIRTY (logs not merged)'}")
    h = Hive(data)
    select = h.values(h.path("Select"))
    current = struct.unpack("<I", select["current"][1])[0] if "current" in select else 1
    cs = f"ControlSet{current:03d}"
    usb = h.path(cs, "Control", "USB")
    print(f"{cs}\\Control\\USB OsDefaultRoleSwitchMode = "
          f"{sz(h.values(usb), 'OsDefaultRoleSwitchMode') if usb else '(no USB key)'}")

    acpi = h.path(cs, "Enum", "ACPI")
    if acpi is None:
        sys.exit("no Enum\\ACPI key")
    print(f"\n{'hardware id':<26} {'inst':<6} {'service':<16} description")
    for hwid, off in sorted(h.subkeys(acpi).items()):
        for inst, ioff in sorted(h.subkeys(off).items()):
            v = h.values(ioff)
            desc = sz(v, "DeviceDesc").split(";")[-1]
            print(f"{hwid:<26} {inst:<6} {sz(v, 'Service') or '-':<16} {desc}")


if __name__ == "__main__":
    main()
