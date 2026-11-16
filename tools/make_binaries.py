#!/usr/bin/env python3
"""Build the Mu-Silicium Binaries/munch tree from an extracted XBL.

Input:  directory produced by xbl_fv_extract.py (INDEX.tsv + files),
        port/binaries-map.tsv, port/patches.toml.
Output: <out>/{ArmPkg,MdeModulePkg,QcomPkg,...}/**.inf|efi|depex and RawFiles/,
        plus Include/RAW.inc for munchPkg (FREEFORM files with their GUIDs).

Example:
    make_binaries.py out/xbl-fv -o out/Binaries/munch --raw-inc port/munchPkg/Include/RAW.inc
"""
import argparse
import csv
import hashlib
import os
import shutil
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = os.path.join(os.path.dirname(HERE), "port")
SECTION_EXT = {"PE32": "efi", "DXE_DEPEX": "depex", "TE": "te", "RAW": "raw"}
# Files only the stock DisplayDxe needs (panels) go into RAW.inc conditionally
PANEL_PREFIX = "Panel_"
# uefiplat.cfg is replaced by MemoryMapLib/ConfigurationMapLib; logo and BDS menu by our own
RAW_SKIP = {"uefiplat.cfg", "BDS_Menu.cfg", "logo1.bmp"}
# Images of the stock QcomChargerApp: the charger app is not part of the build
RAW_SKIP_PREFIX = ("battery_symbol_", "tsens_")


def load_index(fv_dir):
    with open(os.path.join(fv_dir, "INDEX.tsv")) as f:
        return {r["guid"]: r for r in csv.DictReader(f, delimiter="\t")}


def load_map():
    rows = []
    with open(os.path.join(PORT, "binaries-map.tsv")) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            guid, inf, base, mtype, entry, sections = line.rstrip("\n").split("\t")
            rows.append({"guid": guid, "inf": inf, "base": base, "type": mtype,
                         "entry": entry,
                         "sections": [s.split(":") for s in sections.split(",")]})
    return rows


def load_patches():
    with open(os.path.join(PORT, "patches.toml"), "rb") as f:
        patches = tomllib.load(f)["patch"]
    by_name = {}
    for p in patches:
        by_name.setdefault(p["name"], []).append(p)
    return by_name


def apply_patches(name, data, patches):
    data = bytearray(data)
    for p in patches:
        old, new = bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        if "anchor" in p:
            anchor = bytes.fromhex(p["anchor"])
            pos = data.find(anchor)
            if pos < 0 or data.find(anchor, pos + 1) >= 0:
                sys.exit(f"{name}: patch anchor not found or ambiguous")
            offset = pos + p["delta"]
        else:
            offset = p["offset"]
        found = bytes(data[offset:offset + len(old)])
        if found != old:
            sys.exit(f"{name}: expected {old.hex()} at {offset:#x}, found "
                     f"{found.hex()} - different XBL build, patch not applied")
        data[offset:offset + len(new)] = new
        print(f"  patch {name} @ {offset:#x}: {old.hex()} -> {new.hex()}")
    return bytes(data)


def write_inf(path, row, files):
    lines = ["[Defines]",
             "  INF_VERSION                    = 0x0001001B",
             f"  BASE_NAME                      = {row['base']}",
             f"  FILE_GUID                      = {row['guid']}",
             f"  MODULE_TYPE                    = {row['type']}",
             "  VERSION_STRING                 = 1.0"]
    if row["entry"] != "-":
        lines.append(f"  ENTRY_POINT                    = {row['entry']}")
    lines += ["", "[Binaries.AARCH64]"]
    lines += [f"  {kind}|{name}|*" for kind, name in files]
    if any(kind == "DXE_DEPEX" for kind, _ in files):
        lines += ["", "[Depex]", "  TRUE"]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fv_dir")
    ap.add_argument("-o", "--out", default="out/Binaries/munch")
    ap.add_argument("--raw-inc", help="where to write RAW.inc for munchPkg")
    ap.add_argument("--device", default="munch")
    args = ap.parse_args()

    index, patches = load_index(args.fv_dir), load_patches()
    used, sums = set(), []
    if os.path.isdir(args.out):
        shutil.rmtree(args.out)

    for row in load_map():
        entry = index.get(row["guid"])
        if entry is None:
            sys.exit(f"XBL has no file {row['guid']} ({row['base']})")
        used.add(row["guid"])
        src_dir = os.path.join(args.fv_dir, entry["name"])
        dst_dir = os.path.join(args.out, os.path.dirname(row["inf"]))
        os.makedirs(dst_dir, exist_ok=True)
        files = []
        for kind, dst_name in row["sections"]:
            src = os.path.join(src_dir, f"{entry['name']}.{SECTION_EXT[kind]}")
            if not os.path.isfile(src):
                sys.exit(f"{row['base']}: XBL has no {kind} section")
            data = open(src, "rb").read()
            with open(os.path.join(dst_dir, dst_name), "wb") as f:
                f.write(data)
            todo = patches.get(entry["name"]) if kind == "PE32" else None
            if todo:
                stem, ext = os.path.splitext(dst_name)
                dst_name = f"{stem}.patched{ext}"
                data = apply_patches(entry["name"], data, todo)
                with open(os.path.join(dst_dir, dst_name), "wb") as f:
                    f.write(data)
            files.append((kind, dst_name))
            sums.append((hashlib.sha256(data).hexdigest(),
                         os.path.join(os.path.dirname(row["inf"]), dst_name)))
        write_inf(os.path.join(args.out, row["inf"]), row, files)

    unknown_patches = set(patches) - {index[g]["name"] for g in used}
    if unknown_patches:
        sys.exit(f"patches for unknown drivers: {sorted(unknown_patches)}")

    # FREEFORM files: panels, charger configs, battery profiles
    raw_dir = os.path.join(args.out, "RawFiles")
    os.makedirs(raw_dir, exist_ok=True)
    raws = []
    for guid, entry in index.items():
        if entry["type"] != "FREEFORM" or entry["name"] == guid:
            continue
        name = entry["name"]
        src = os.path.join(args.fv_dir, name, f"{name}.raw")
        shutil.copyfile(src, os.path.join(raw_dir, name))
        sums.append((hashlib.sha256(open(src, "rb").read()).hexdigest(),
                     os.path.join("RawFiles", name)))
        if (name not in RAW_SKIP and not name.startswith(RAW_SKIP_PREFIX)
                and os.path.getsize(src) > 0):
            raws.append((guid, name))

    with open(os.path.join(args.out, "SHA256SUMS"), "w") as f:
        f.writelines(f"{h}  {p}\n" for h, p in sorted(sums, key=lambda s: s[1]))

    if args.raw_inc:
        def block(guid, name):
            return (f"  FILE FREEFORM = {guid} {{\n"
                    f"    SECTION UI = \"{name}\"\n"
                    f"    SECTION RAW = Binaries/{args.device}/RawFiles/{name}\n"
                    f"  }}\n")
        panels = [r for r in raws if r[1].startswith(PANEL_PREFIX)]
        others = [r for r in raws if not r[1].startswith(PANEL_PREFIX)]
        with open(args.raw_inc, "w") as f:
            f.write("# Generated by tools/make_binaries.py from the XBL - do not edit.\n")
            f.write("!if $(USE_CUSTOM_DISPLAY_DRIVER) == 1\n")
            f.write("\n".join(block(*r) for r in panels))
            f.write("!endif\n\n")
            f.write("\n".join(block(*r) for r in others))
    print(f"drivers: {len(used)}, raw files: {len(raws)} -> {args.out}")


if __name__ == "__main__":
    main()
