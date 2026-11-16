#!/usr/bin/env python3
"""Create a Windows BCD store on Linux, the way bcdboot does.

Starts from BCD-Template shipped inside the Windows image
(Windows/System32/config/BCD-Template), marks it as the system store, then
adds the firmware and Windows boot manager settings and one Windows loader
entry with hivexregedit (package "hivex").

The template is not a system store: its root Description key has only an
opaque KeyName. bcdboot sets KeyName "BCD00000000", System = 1 and
TreatAsSystem = 1; without them the specialize pass of Windows setup fails
in Sysprep_Specialize_Bcd with "File is not system store" (0xC0000098).

Device elements use the qualified-partition encoding (88 bytes):
    0x00 associated GUID (zero)   0x10 device type = 6 (partition)
    0x18 size = 0x48              0x20 partition GUID
    0x38 disk GUID
which matches published decodings of real stores and the U1F984/create_bcd
generator. The GUIDs are the GPT disk and partition GUIDs, so the partitions
must be created with exactly these values.

Examples:
    make_bcd.py --template BCD-Template --disk-guid D --esp-guid E --win-guid W -o BCD
    make_bcd.py --dump BCD
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid

BOOTMGR = "{9dea862c-5cdd-4e70-acc1-f32b344d4795}"
FWBOOTMGR = "{a5a30fa2-3d06-4e9f-b5f4-a01df9d1fcba}"
GLOBALSETTINGS = "{7ea2e1ac-2e61-4728-aaa3-896d9d0a9f0e}"
BOOTLOADERSETTINGS = "{6efb52bf-1766-41db-a6b3-0ee5eff72bd7}"

REG_SZ, REG_BINARY, REG_DWORD, REG_MULTI_SZ = 1, 3, 4, 7

ELEMENT_NAMES = {
    0x11000001: "device", 0x12000002: "path", 0x12000004: "description",
    0x12000005: "locale", 0x14000006: "inherit", 0x16000009: "recoveryenabled",
    0x16000048: "nointegritychecks", 0x16000049: "testsigning",
    0x21000001: "osdevice", 0x22000002: "systemroot", 0x23000003: "default",
    0x24000001: "displayorder", 0x25000004: "timeout", 0x25000020: "nx",
    0x250000c2: "bootmenupolicy", 0x250000e0: "bootstatuspolicy",
}


# --------------------------------------------------------------------------
# element encoders

def device(disk_guid, part_guid):
    data = bytearray(0x58)
    struct.pack_into("<I", data, 0x10, 6)       # partition device
    struct.pack_into("<I", data, 0x18, 0x48)    # descriptor size
    data[0x20:0x30] = uuid.UUID(part_guid).bytes_le
    data[0x38:0x48] = uuid.UUID(disk_guid).bytes_le
    return REG_BINARY, bytes(data)


def string(s):
    return REG_SZ, s.encode("utf-16le") + b"\0\0"


def guid_list(items):
    return REG_MULTI_SZ, b"".join(i.encode("utf-16le") + b"\0\0" for i in items) + b"\0\0"


def integer(n):
    return REG_BINARY, struct.pack("<Q", n)


def boolean(b):
    return REG_BINARY, bytes([1 if b else 0])


# --------------------------------------------------------------------------
# minimal read-only regf parser, used to verify the result independently

class Hive:
    def __init__(self, data):
        if data[:4] != b"regf":
            raise ValueError("not a registry hive")
        self.d = data
        self.root = struct.unpack_from("<I", data, 0x24)[0]

    def cell(self, off):
        return self.d[0x1000 + off + 4:]

    def key_name(self, off):
        c = self.cell(off)
        flags, n = struct.unpack_from("<H", c, 2)[0], struct.unpack_from("<H", c, 72)[0]
        raw = c[76:76 + n]
        return raw.decode("latin-1") if flags & 0x20 else raw.decode("utf-16le")

    def subkeys(self, off):
        c = self.cell(off)
        if struct.unpack_from("<I", c, 20)[0] == 0:
            return {}
        out = {}
        self._walk_list(struct.unpack_from("<I", c, 28)[0], out)
        return out

    def _walk_list(self, off, out):
        c = self.cell(off)
        sig, n = c[:2], struct.unpack_from("<H", c, 2)[0]
        if sig in (b"lf", b"lh"):
            offs = [struct.unpack_from("<I", c, 4 + 8 * i)[0] for i in range(n)]
        elif sig in (b"li", b"ri"):
            offs = [struct.unpack_from("<I", c, 4 + 4 * i)[0] for i in range(n)]
        else:
            raise ValueError(f"unknown subkey list {sig!r}")
        for o in offs:
            if sig == b"ri":
                self._walk_list(o, out)
            else:
                out[self.key_name(o).lower()] = o

    def values(self, off):
        c = self.cell(off)
        n, lst = struct.unpack_from("<II", c, 36)
        out = {}
        for i in range(n):
            v = self.cell(struct.unpack_from("<I", self.cell(lst), 4 * i)[0])
            nlen, dlen, doff, vtype, flags = struct.unpack_from("<HIIIH", v, 2)
            name = v[20:20 + nlen].decode("latin-1" if flags & 1 else "utf-16le")
            if dlen & 0x80000000:
                data = struct.pack("<I", doff)[:dlen & 0x7FFFFFFF]
            else:
                data = bytes(self.cell(doff)[:dlen])
            out[name.lower()] = (vtype, data)
        return out

    def path(self, *names):
        off = self.root
        for n in names:
            off = self.subkeys(off).get(n.lower())
            if off is None:
                return None
        return off


def decode(element_type, vtype, data):
    if vtype == REG_SZ:
        return data.decode("utf-16le").rstrip("\0")
    if vtype == REG_MULTI_SZ:
        return [s for s in data.decode("utf-16le").split("\0") if s]
    if element_type >> 24 & 0xF == 1 and len(data) == 0x58:
        dtype = struct.unpack_from("<I", data, 0x10)[0]
        if dtype == 6:
            return (f"partition part={uuid.UUID(bytes_le=data[0x20:0x30])} "
                    f"disk={uuid.UUID(bytes_le=data[0x38:0x48])}")
        return f"device type {dtype}"
    fmt = element_type >> 24 & 0xF
    if fmt == 5 and 0 < len(data) <= 8:   # integer, stored in 1..8 bytes
        return int.from_bytes(data, "little")
    if fmt == 6 and data:                 # boolean
        return bool(data[0])
    return data.hex()


def dump(hive):
    objects = hive.path("Objects")
    if objects is None:
        sys.exit("no Objects key: not a BCD store")
    result = {}
    for name, off in sorted(hive.subkeys(objects).items()):
        desc = hive.subkeys(off).get("description")
        otype = hive.values(desc).get("type", (0, b"\0\0\0\0"))[1] if desc else b"\0\0\0\0"
        elems = {}
        el = hive.subkeys(off).get("elements")
        for ename, eoff in (hive.subkeys(el).items() if el else []):
            vtype, data = hive.values(eoff).get("element", (0, b""))
            etype = int(ename, 16)
            elems[etype] = decode(etype, vtype, data)
        result[name] = (struct.unpack("<I", otype[:4])[0], elems)
    return result


def print_dump(result):
    for name, (otype, elems) in result.items():
        print(f"{name}  type {otype:#010x}")
        for etype, val in sorted(elems.items()):
            print(f"    {ELEMENT_NAMES.get(etype, f'{etype:08x}'):<18} {val}")


# --------------------------------------------------------------------------
# writer (hivexregedit --merge)

def reg_value(name, vtype, data):
    return f'"{name}"=hex({vtype:x}):' + ",".join(f"{b:02x}" for b in data)


def build(template, out, disk, esp, win, description, locale, timeout):
    loader = "{" + str(uuid.uuid4()) + "}"
    objects = {
        FWBOOTMGR: (0x10100001, {
            0x24000001: guid_list([BOOTMGR]),
            0x25000004: integer(0),
        }),
        BOOTMGR: (0x10100002, {
            0x11000001: device(disk, esp),
            0x12000002: string(r"\EFI\Microsoft\Boot\bootmgfw.efi"),
            0x12000004: string("Windows Boot Manager"),
            0x12000005: string(locale),
            0x14000006: guid_list([GLOBALSETTINGS]),
            0x23000003: string(loader),
            0x24000001: guid_list([loader]),
            0x25000004: integer(timeout),
        }),
        loader: (0x10200003, {
            0x11000001: device(disk, win),
            0x12000002: string(r"\Windows\system32\winload.efi"),
            0x12000004: string(description),
            0x12000005: string(locale),
            0x14000006: guid_list([BOOTLOADERSETTINGS]),
            0x16000009: boolean(False),   # recoveryenabled: WinRE has no drivers here
            0x16000048: boolean(True),    # nointegritychecks
            0x16000049: boolean(True),    # testsigning: device drivers are not WHQL
            0x16000060: boolean(True),    # isolatedcontext, as in the template loader
            0x17000077: (REG_BINARY, struct.pack("<Q", 0x15000075)),  # allowedinmemorysettings
            0x21000001: device(disk, win),
            0x22000002: string(r"\Windows"),
            0x25000020: integer(0),       # nx OptIn
            0x250000c2: integer(1),       # bootmenupolicy Standard
            0x250000e0: integer(1),       # bootstatuspolicy IgnoreAllFailures
        }),
    }
    lines = ["Windows Registry Editor Version 5.00", "",
             r"[HKEY_LOCAL_MACHINE\BCD\Description]",
             reg_value("KeyName", REG_SZ, string("BCD00000000")[1]),
             reg_value("System", REG_DWORD, struct.pack("<I", 1)),
             reg_value("TreatAsSystem", REG_DWORD, struct.pack("<I", 1)), ""]
    for obj, (otype, elems) in objects.items():
        base = rf"HKEY_LOCAL_MACHINE\BCD\Objects\{obj}"
        lines += [f"[{base}]", "", f"[{base}\\Description]",
                  reg_value("Type", REG_DWORD, struct.pack("<I", otype)), "",
                  f"[{base}\\Elements]", ""]
        for etype, (vtype, data) in sorted(elems.items()):
            lines += [f"[{base}\\Elements\\{etype:08X}]", reg_value("Element", vtype, data), ""]

    if not shutil.which("hivexregedit"):
        sys.exit("hivexregedit not found: install the hivex package")
    shutil.copyfile(template, out)
    with tempfile.NamedTemporaryFile("w", suffix=".reg", delete=False) as f:
        f.write("\r\n".join(lines) + "\r\n")
        regfile = f.name
    try:
        subprocess.run(["hivexregedit", "--merge", "--prefix", r"HKEY_LOCAL_MACHINE\BCD",
                        out, regfile], check=True)
    finally:
        os.unlink(regfile)
    return loader


def verify(path, disk, esp, win, loader):
    hive = Hive(open(path, "rb").read())
    result = dump(hive)
    lower = {k.lower(): v for k, v in result.items()}
    bm, ld = lower.get(BOOTMGR), lower.get(loader.lower())
    errors = []
    desc = hive.values(hive.path("Description"))
    for name in ("system", "treatassystem"):
        if desc.get(name) != (REG_DWORD, struct.pack("<I", 1)):
            errors.append(f"Description\\{name} is not 1: not a system store")
    if desc.get("keyname", (0, b""))[1].decode("utf-16le", "replace").rstrip("\0") != "BCD00000000":
        errors.append("Description\\KeyName is not BCD00000000")
    if FWBOOTMGR not in lower:
        errors.append("firmware boot manager object missing")
    if not bm or not ld:
        errors.append("boot manager or loader object missing")
    else:
        want_esp = f"partition part={esp.lower()} disk={disk.lower()}"
        want_win = f"partition part={win.lower()} disk={disk.lower()}"
        if bm[1].get(0x11000001) != want_esp:
            errors.append(f"bootmgr device is {bm[1].get(0x11000001)}")
        for et in (0x11000001, 0x21000001):
            if ld[1].get(et) != want_win:
                errors.append(f"loader {ELEMENT_NAMES[et]} is {ld[1].get(et)}")
        if str(bm[1].get(0x23000003)).lower() != loader.lower():
            errors.append("bootmgr default does not point to the loader")
        if ld[0] != 0x10200003:
            errors.append(f"loader object type is {ld[0]:#x}")
    if errors:
        sys.exit("BCD verification failed:\n  " + "\n  ".join(errors))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", metavar="BCD", help="print the objects of an existing store")
    ap.add_argument("--template")
    ap.add_argument("--disk-guid")
    ap.add_argument("--esp-guid")
    ap.add_argument("--win-guid")
    ap.add_argument("--description", default="Windows 11 IoT Enterprise LTSC")
    ap.add_argument("--locale", default="en-US")
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    if args.dump:
        print_dump(dump(Hive(open(args.dump, "rb").read())))
        return
    missing = [a for a in ("template", "disk_guid", "esp_guid", "win_guid", "out")
               if not getattr(args, a)]
    if missing:
        ap.error("missing: " + ", ".join("--" + m.replace("_", "-") for m in missing))
    for g in (args.disk_guid, args.esp_guid, args.win_guid):
        uuid.UUID(g)
    loader = build(args.template, args.out, args.disk_guid, args.esp_guid, args.win_guid,
                   args.description, args.locale, args.timeout)
    print_dump(verify(args.out, args.disk_guid, args.esp_guid, args.win_guid, loader))
    print(f"\n{args.out}: verified, loader {loader}")


if __name__ == "__main__":
    main()
