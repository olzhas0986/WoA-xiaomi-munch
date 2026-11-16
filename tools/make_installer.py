#!/usr/bin/env python3
"""Build the recovery zip that installs Windows into a spare partition.

Inputs:
  --gpt      raw dump of the start of sda (see tools/gpt_read.py)
  --target   number or GPT name of a partition to replace; repeat it to
             replace several adjacent partitions as one range
  --win      output directory of tools/prepare_image.sh
  --tools    static aarch64 tools from scripts/build_recovery_tools.sh

The chosen range is split into ESP (512 MiB), MSR (16 MiB) and Windows
(the rest). ESP and Windows reuse the numbers of the replaced partitions.
Partition GUIDs are generated here and baked into both the BCD and
install.conf, so the BCD matches the partitions the zip creates.

Outputs (in -o, default out/installer):
  win-install-munch.zip          installs
  win-install-munch-dryrun.zip   same content, only runs the checks
  layout.txt                     what will be written where

--match-table takes the partition GUIDs from a reference GPT partition array
(8192 bytes from LBA 2) and checks that the resulting array is byte-identical
to it, so firmware or tools pinned to that exact layout keep working.

--reuse takes the partition GUIDs from a zip built earlier. Use it to fix an
installation: the phone already has partitions with those GUIDs, so the new
zip resumes on them (reformat and reapply) instead of refusing.

Example:
    make_installer.py --gpt out/sda-gpt.bin --target arch_boot --target arch_root
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import struct
import sys
import uuid
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gpt_read  # noqa: E402

MIB = 1 << 20
ESP_BYTES = 512 * MIB
MSR_BYTES = 16 * MIB
MIN_WIN_BYTES = 20 << 30
# Only partitions someone created by hand qualify: Linux or Microsoft data types.
# Every stock Qualcomm/Android partition uses a vendor-specific type GUID.
ALLOWED_TYPES = {
    "0FC63DAF-8483-4772-8E79-3D69D8477DE4": "Linux filesystem",
    "B921B045-1DF0-41C3-AF44-4C6F280D3FAE": "Linux root (ARM64)",
    "933AC7E1-2EB4-4F13-B844-0E14E2AEF915": "Linux home",
    "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7": "Microsoft basic data",
    # an earlier Windows install made by this tool can be laid out again
    "C12A7328-F81F-11D2-BA4B-00A0C93EC93B": "EFI system partition",
    "E3C9E316-0B5C-4DB8-817D-F92DF00215AE": "Microsoft reserved",
}
PROTECTED_NAMES = {"userdata", "super", "metadata", "persist", "misc", "frp", "cust",
                   "modemst1", "modemst2", "fsg", "fsc", "ssd", "logfs", "rawdump"}


def pick_targets(gpt, targets):
    parts, picked = gpt["partitions"], []
    for target in targets:
        match = [p for p in parts if str(p["number"]) == target or p["name"] == target]
        if len(match) != 1:
            sys.exit(f"target '{target}' matches {len(match)} partitions")
        p = match[0]
        if p["name"].lower() in PROTECTED_NAMES:
            sys.exit(f"refusing to touch '{p['name']}'")
        if p["type_guid"] not in ALLOWED_TYPES:
            sys.exit(f"partition {p['number']} '{p['name']}' has type {p['type_guid']}, which "
                     "is not a Linux/Windows data type - is it really a spare partition?")
        if p not in picked:
            picked.append(p)
    picked.sort(key=lambda p: p["first_lba"])
    ss = gpt["sector_size"]
    for a, b in zip(picked, picked[1:]):
        # anything else between the targets would be overwritten
        others = [p for p in parts if p not in picked
                  and p["first_lba"] <= b["first_lba"] and p["last_lba"] >= a["last_lba"]]
        if others or (b["first_lba"] - a["last_lba"] - 1) * ss > MIB:
            sys.exit(f"'{a['name']}' and '{b['name']}' are not adjacent")
    total = (picked[-1]["last_lba"] - picked[0]["first_lba"] + 1) * ss
    if not 20 << 30 <= total <= 128 << 30:
        sys.exit(f"target range is {total >> 20} MiB, expected 20-128 GiB")
    return picked


def layout(gpt, targets):
    ss = gpt["sector_size"]
    align = MIB // ss
    used = {p["number"] for p in gpt["partitions"]}
    free = [n for n in range(1, gpt["entries"] + 1) if n not in used]
    numbers = [t["number"] for t in targets] + free
    if len(numbers) < 3:
        sys.exit("no free partition entries for MSR and Windows")
    first, last = targets[0]["first_lba"], targets[-1]["last_lba"]

    esp_start = -(-first // align) * align
    esp_size = ESP_BYTES // ss
    msr_start, msr_size = esp_start + esp_size, MSR_BYTES // ss
    win_start = msr_start + msr_size
    win_size = (last + 1 - win_start) // align * align
    if win_size * ss < MIN_WIN_BYTES:
        sys.exit(f"only {win_size * ss >> 20} MiB left for Windows")
    new = lambda: str(uuid.uuid4()).upper()  # noqa: E731
    esp_nr, win_nr, msr_nr = numbers[0], numbers[1], numbers[2]
    conf = {"SECTOR_SIZE": ss, "DISK_GUID": gpt["disk_guid"],
            "TARGET_NRS": " ".join(str(t["number"]) for t in targets)}
    for t in targets:
        n = t["number"]
        conf.update({f"T{n}_NAME": t["name"], f"T{n}_UUID": t["part_guid"],
                     f"T{n}_START": t["first_lba"],
                     f"T{n}_SIZE": t["last_lba"] - t["first_lba"] + 1})
    conf.update({
        "ESP_NR": esp_nr, "ESP_START": esp_start, "ESP_SIZE": esp_size, "ESP_UUID": new(),
        "MSR_NR": msr_nr, "MSR_START": msr_start, "MSR_SIZE": msr_size, "MSR_UUID": new(),
        "WIN_NR": win_nr, "WIN_START": win_start, "WIN_SIZE": win_size, "WIN_UUID": new(),
    })
    return conf


def match_reference_table(gpt_dump, table_path, conf):
    """Adopt the reference GUIDs and prove the new array equals the reference."""
    ss = conf["SECTOR_SIZE"]
    ref = open(table_path, "rb").read()
    cur = bytearray(open(gpt_dump, "rb").read()[2 * ss:2 * ss + len(ref)])
    if len(cur) != len(ref):
        sys.exit("GPT dump is too short for the reference table")
    types = {"ESP": "C12A7328-F81F-11D2-BA4B-00A0C93EC93B",
             "MSR": "E3C9E316-0B5C-4DB8-817D-F92DF00215AE",
             "WIN": "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7"}
    for n in conf["TARGET_NRS"].split():
        cur[(int(n) - 1) * 128:int(n) * 128] = bytes(128)
    for part, name in (("ESP", "esp"), ("MSR", "msr"), ("WIN", "win")):
        i = conf[part + "_NR"] - 1
        e = ref[i * 128:(i + 1) * 128]
        first, last = struct.unpack_from("<QQ", e, 32)
        if (e[56:128].decode("utf-16le").rstrip("\0") != name
                or str(uuid.UUID(bytes_le=e[:16])).upper() != types[part]
                or (first, last - first + 1) != (conf[part + "_START"], conf[part + "_SIZE"])):
            sys.exit(f"reference entry {i + 1} is not {name} at the computed position")
        conf[part + "_UUID"] = str(uuid.UUID(bytes_le=e[16:32])).upper()
        new = bytearray(128)
        new[:16] = uuid.UUID(types[part]).bytes_le
        new[16:32] = e[16:32]
        struct.pack_into("<QQQ", new, 32, first, last, 0)
        new[56:56 + len(name) * 2] = name.encode("utf-16le")
        cur[i * 128:(i + 1) * 128] = new
    if bytes(cur) != ref:
        diff = [i + 1 for i in range(len(ref) // 128)
                if cur[i * 128:(i + 1) * 128] != ref[i * 128:(i + 1) * 128]]
        sys.exit(f"resulting partition array differs from the reference in entries {diff}")
    print(f"partition array will match the reference: sha256 {hashlib.sha256(ref).hexdigest()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpt", required=True)
    ap.add_argument("--target", required=True, action="append")
    ap.add_argument("--win", default=os.path.join(ROOT, "out/win"))
    ap.add_argument("--tools", default=os.path.join(ROOT, "out/recovery-tools/bin"))
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "out/installer"))
    ap.add_argument("--reuse", metavar="ZIP", help="take partition GUIDs from an earlier zip")
    ap.add_argument("--match-table", metavar="BIN",
                    help="take GUIDs from a reference partition array and require an exact match")
    args = ap.parse_args()

    gpt = gpt_read.parse(open(args.gpt, "rb").read())
    targets = pick_targets(gpt, args.target)
    conf = layout(gpt, targets)
    if args.reuse:
        with zipfile.ZipFile(args.reuse) as z:
            old = dict(line.split("=", 1) for line in z.read("install.conf").decode().splitlines()
                       if "=" in line and not line.startswith("#"))
        old = {k: v.strip("'") for k, v in old.items()}
        for k, v in conf.items():
            if not k.endswith("_UUID") and str(v) != old.get(k):
                sys.exit(f"--reuse: {k} differs ({old.get(k)} vs {v}); not the same layout")
        for k in ("ESP_UUID", "MSR_UUID", "WIN_UUID"):
            conf[k] = old[k]
    if args.match_table:
        match_reference_table(args.gpt, args.match_table, conf)
    esd = os.path.join(args.win, "install.esd")
    for path in (esd, os.path.join(args.win, "BCD-Template"),
                 os.path.join(args.win, "esp/EFI/Boot/bootaa64.efi")):
        if not os.path.isfile(path):
            sys.exit(f"missing {path}: run tools/prepare_image.sh first")
    tools = ["sfdisk", "partx", "mkfs.fat", "mkntfs", "wimlib-imagex"]
    for t in tools:
        if not os.path.isfile(os.path.join(args.tools, t)):
            sys.exit(f"missing {t}: run scripts/build_recovery_tools.sh first")
    conf["ESD_SIZE"] = os.path.getsize(esd)

    os.makedirs(args.out, exist_ok=True)
    stage = os.path.join(args.out, "stage")
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(os.path.join(args.win, "esp"), os.path.join(stage, "esp"))
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools/make_bcd.py"),
                    "--template", os.path.join(args.win, "BCD-Template"),
                    "--disk-guid", conf["DISK_GUID"], "--esp-guid", conf["ESP_UUID"],
                    "--win-guid", conf["WIN_UUID"],
                    "-o", os.path.join(stage, "esp/EFI/Microsoft/Boot/BCD")], check=True)

    conf_text = "# generated by tools/make_installer.py - do not edit\n" + \
        "".join(f"{k}={v}\n" if isinstance(v, int) else f"{k}='{v}'\n" for k, v in conf.items())
    ss = conf["SECTOR_SIZE"]
    summary = [f"disk GUID {conf['DISK_GUID']}, sector {ss}", "replace:"]
    for t in targets:
        summary.append(f"  sda{t['number']:<3} '{t['name']}' {t['size_bytes'] >> 20} MiB "
                       f"{t['part_guid']}")
    summary.append("with:")
    for n in ("ESP", "MSR", "WIN"):
        summary.append(f"  sda{conf[n + '_NR']:<3} {n:<3} start {conf[n + '_START']:>10} "
                       f"size {conf[n + '_SIZE'] * ss >> 20:>6} MiB  {conf[n + '_UUID']}")
    summary.append(f"install.esd {conf['ESD_SIZE']} bytes")
    with open(os.path.join(args.out, "layout.txt"), "w") as f:
        f.write("\n".join(summary) + "\n")

    for name in ("win-install-munch.zip", "win-install-munch-dryrun.zip"):
        path = os.path.join(args.out, name)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(os.path.join(ROOT, "installer/update-binary"),
                    "META-INF/com/google/android/update-binary")
            z.writestr("META-INF/com/google/android/updater-script", "#dummy\n")
            z.writestr("install.conf", conf_text)
            for t in tools:
                z.write(os.path.join(args.tools, t), f"bin/{t}")
            for dirpath, _, files in os.walk(os.path.join(stage, "esp")):
                for fn in files:
                    full = os.path.join(dirpath, fn)
                    z.write(full, os.path.relpath(full, stage))
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        summary.append(f"{name}: {os.path.getsize(path) >> 10} KiB, sha256 {digest[:16]}")
    shutil.rmtree(stage)
    print("\n".join(summary))
    print(json.dumps({"layout": os.path.join(args.out, "layout.txt")}))


if __name__ == "__main__":
    main()
