#!/usr/bin/env python3
"""Build the recovery zip that installs Windows into a spare partition.

Inputs:
  --gpt      raw dump of the start of sda (see tools/gpt_read.py)
  --target   number or GPT name of the partition to replace
  --win      output directory of tools/prepare_image.sh
  --tools    static aarch64 tools from scripts/build_recovery_tools.sh

The chosen partition is split into ESP (512 MiB), MSR (16 MiB) and Windows
(the rest). Partition GUIDs are generated here and baked into both the BCD
and install.conf, so the BCD matches the partitions the zip creates.

Outputs (in -o, default out/installer):
  win-install-munch.zip          installs
  win-install-munch-dryrun.zip   same content, only runs the checks
  layout.txt                     what will be written where

Example:
    make_installer.py --gpt out/sda-gpt.bin --target arch
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
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
}
PROTECTED_NAMES = {"userdata", "super", "metadata", "persist", "misc", "frp", "cust",
                   "modemst1", "modemst2", "fsg", "fsc", "ssd", "logfs", "rawdump"}


def pick_target(gpt, target):
    parts = gpt["partitions"]
    match = [p for p in parts if str(p["number"]) == target or p["name"] == target]
    if len(match) != 1:
        sys.exit(f"target '{target}' matches {len(match)} partitions")
    p = match[0]
    if p["name"].lower() in PROTECTED_NAMES:
        sys.exit(f"refusing to touch '{p['name']}'")
    if p["type_guid"] not in ALLOWED_TYPES:
        sys.exit(f"partition {p['number']} '{p['name']}' has type {p['type_guid']}, which is "
                 "not a Linux/Windows data type - is it really the spare partition?")
    if not 20 << 30 <= p["size_bytes"] <= 128 << 30:
        sys.exit(f"partition is {p['size_bytes'] >> 20} MiB, expected 20-128 GiB")
    return p


def layout(gpt, target):
    ss = gpt["sector_size"]
    align = MIB // ss
    used = {p["number"] for p in gpt["partitions"]}
    free = [n for n in range(1, gpt["entries"] + 1) if n not in used]
    if len(free) < 2:
        sys.exit("no free partition entries for MSR and Windows")

    esp_start = -(-target["first_lba"] // align) * align
    esp_size = ESP_BYTES // ss
    msr_start, msr_size = esp_start + esp_size, MSR_BYTES // ss
    win_start = msr_start + msr_size
    win_size = (target["last_lba"] + 1 - win_start) // align * align
    if win_size * ss < MIN_WIN_BYTES:
        sys.exit(f"only {win_size * ss >> 20} MiB left for Windows")
    new = lambda: str(uuid.uuid4()).upper()  # noqa: E731
    return {
        "SECTOR_SIZE": ss, "DISK_GUID": gpt["disk_guid"],
        "TARGET_NR": target["number"], "TARGET_NAME": target["name"],
        "TARGET_UUID": target["part_guid"], "TARGET_START": target["first_lba"],
        "TARGET_SIZE": target["last_lba"] - target["first_lba"] + 1,
        "ESP_NR": target["number"], "ESP_START": esp_start, "ESP_SIZE": esp_size, "ESP_UUID": new(),
        "MSR_NR": free[0], "MSR_START": msr_start, "MSR_SIZE": msr_size, "MSR_UUID": new(),
        "WIN_NR": free[1], "WIN_START": win_start, "WIN_SIZE": win_size, "WIN_UUID": new(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpt", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--win", default=os.path.join(ROOT, "out/win"))
    ap.add_argument("--tools", default=os.path.join(ROOT, "out/recovery-tools/bin"))
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "out/installer"))
    args = ap.parse_args()

    gpt = gpt_read.parse(open(args.gpt, "rb").read())
    conf = layout(gpt, pick_target(gpt, args.target))
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
    summary = [f"disk GUID {conf['DISK_GUID']}, sector {ss}",
               f"replace sda{conf['TARGET_NR']} '{conf['TARGET_NAME']}' "
               f"({conf['TARGET_SIZE'] * ss >> 20} MiB) with:"]
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
