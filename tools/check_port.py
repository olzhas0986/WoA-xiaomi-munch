#!/usr/bin/env python3
"""Static consistency check of the port without running a build.

  1. every INF/RAW in Binaries/munch referenced from dsc/fdf/inc exists in
     the generated tree, and all of its binary sections are present;
  2. every patched driver is actually used (its INF points to *.patched.efi);
  3. with --mu: the remaining INFs from fdf/inc exist in the Mu-Silicium tree
     (submodules are skipped if they are not checked out).

Example:
    check_port.py --binaries out/Binaries/munch [--mu work/Mu-Silicium]
"""
import argparse
import glob
import os
import re
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "port/munchPkg")
PACKAGE_PATHS = ["Platforms/Xiaomi", "Common/Mu", "Common/Mu_OEM_Sample", "Mu_Basecore",
                 "Silicon/Qualcomm", "Silicon/Silicium", "Silicium-ACPI",
                 "Silicium-ACPI/Platforms/Xiaomi", "Silicium-ACPI/Silicon/Qualcomm", "."]
SUBMODULES = ("MdeModulePkg", "MdePkg", "ArmPkg", "EmbeddedPkg", "FatPkg", "ShellPkg",
              "CryptoPkg", "SecurityPkg", "NetworkPkg", "PcBdsPkg", "MsCorePkg",
              "MsGraphicsPkg", "OemPkg", "DfciPkg", "MfciPkg", "UefiCpuPkg",
              "ArmPlatformPkg", "AdvLoggerPkg", "MsWheaPkg", "PolicyServicePkg",
              "alioth/")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binaries", required=True)
    ap.add_argument("--mu", help="Mu-Silicium checkout to verify the remaining paths")
    args = ap.parse_args()

    errors, bin_refs, other_refs = [], set(), set()
    sources = glob.glob(os.path.join(PKG, "*.dsc")) + glob.glob(os.path.join(PKG, "*.fdf")) \
        + glob.glob(os.path.join(PKG, "Include/*.inc"))
    for path in sources:
        for line in open(path):
            line = line.split("#")[0]
            for ref in re.findall(r"Binaries/munch/(\S+)", line):
                bin_refs.add(ref)
            m = re.match(r"\s*INF\s+(?:RuleOverride\s*=\s*\w+\s+)?(\S+\.inf)", line)
            if m and "Binaries/" not in m[1]:
                other_refs.add(m[1])
            m = re.search(r"\|\s*(munchPkg/\S+\.inf)", line)
            if m:
                other_refs.add(m[1])

    for ref in sorted(bin_refs):
        full = os.path.join(args.binaries, ref)
        if not os.path.isfile(full):
            errors.append(f"missing file Binaries/munch/{ref}")
        elif ref.endswith(".inf"):
            for name in re.findall(r"^\s*\w+\|([^|\s]+)", open(full).read(), re.M):
                if not os.path.isfile(os.path.join(os.path.dirname(full), name)):
                    errors.append(f"{ref}: missing section {name}")

    with open(os.path.join(ROOT, "port/patches.toml"), "rb") as f:
        patched = {p["name"] for p in tomllib.load(f)["patch"]}
    used_patched = set()
    for inf in glob.glob(os.path.join(args.binaries, "**/*.inf"), recursive=True):
        if ".patched." in open(inf).read():
            rel = os.path.relpath(inf, args.binaries)
            used_patched.add(rel)
            if rel not in bin_refs:
                errors.append(f"patched driver {rel} is not referenced from fdf/inc")
    if len(used_patched) != len(patched):
        errors.append(f"{len(patched)} drivers have patches, but {len(used_patched)} INFs are patched")

    skipped = 0
    for ref in sorted(other_refs):
        if ref.startswith("munchPkg/"):
            if not os.path.isfile(os.path.join(ROOT, "port", ref)):
                errors.append(f"missing port file {ref}")
        elif args.mu:
            if not any(os.path.isfile(os.path.join(args.mu, p, ref)) for p in PACKAGE_PATHS):
                if ref.startswith(SUBMODULES):
                    skipped += 1
                else:
                    errors.append(f"Mu-Silicium has no {ref}")

    print(f"references to Binaries/munch: {len(bin_refs)}, other INFs: {len(other_refs)}"
          f" (skipped in submodules: {skipped}), patched drivers: {len(used_patched)}")
    if errors:
        print("ERRORS:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("port consistent")


if __name__ == "__main__":
    main()
