#!/usr/bin/env python3
"""Import the PEP0 configuration of the Xiaomi pipa DSDT into the previous port's SSDT.

The previous port's SSDT-GPU-PEP.asl describes PEP0 with only the methods
the PEP driver failed on so far. The pipa DSDT (Silicium-ACPI, SM8250-AC,
written for the same PEP generation) carries the full PEP0 configuration.
This copies every PEP0 object the SSDT does not define yet, plus the
platform names those objects reference, and leaves out:

  THTZ  thermal configuration referencing 40 thermal zones that do not exist
  NPUR  references AGR0, which does not exist

Device paths inside the configuration packages are strings, so devices that
are not present (GPU0, cameras, PCIe, ...) do not need to exist for the
table to compile.

Example:
    import_pipa_pep0.py pipa/Decompiled/DSDT.dsl SSDT-GPU-PEP.asl -o SSDT-GPU-PEP.asl
"""
import argparse
import re
import sys

SKIP = {"THTZ", "NPUR", "_SUB"}
# simple \_SB names the imported objects use (name, kind)
PLATFORM = ["PSUB", "SOID", "PLST", "SVMJ", "STOR", "PUS3",
            "DPP0", "DPP1", "MPP0", "MPP1", "BSID"]


def block(t, i):
    """Return the end line of the object starting at line i."""
    ind = len(t[i]) - len(t[i].lstrip())
    if not (i + 1 < len(t) and t[i + 1].strip().startswith("{")):
        return i
    j = i + 1
    while not (t[j].strip() in ("}", "})") and len(t[j]) - len(t[j].lstrip()) == ind):
        j += 1
    return j


def reindent(lines, new):
    ind = len(lines[0]) - len(lines[0].lstrip())
    return [(" " * new + l[ind:]) if l.strip() else "" for l in lines]


def pep0_objects(t):
    found = {}
    for i, l in enumerate(t):
        m = re.match(r"(\s*)(Method|Name) \((\w{4})", l)
        if not m:
            continue
        ind = len(m.group(1))
        k = i - 1
        while k > 0 and not (len(t[k]) - len(t[k].lstrip()) == ind - 4
                             and re.match(r"\s*(Device|Scope) \(", t[k])):
            k -= 1
        if "PEP0" in t[k] and m.group(3) not in found:
            found[m.group(3)] = (i, block(t, i))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pipa_dsdt")
    ap.add_argument("ssdt")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    t = open(args.pipa_dsdt).read().split("\n")
    s = open(args.ssdt).read()
    have = set(re.findall(r"(?:Method|Name) \((\w{4})", s))

    objs = pep0_objects(t)
    pep = []
    imported = []
    for name, (a, b) in objs.items():
        if name in have or name in SKIP:
            continue
        imported.append(name)
        pep += [f"            // pipa PEP0.{name}"] + reindent(t[a:b + 1], 12)

    sb = []
    for name in PLATFORM:
        if name in have:
            continue
        hits = [i for i, l in enumerate(t)
                if re.match(r"\s{8}(Name|Method) \(%s," % name, l)]
        if not hits:
            sys.exit(f"pipa DSDT has no \\_SB.{name}")
        i = hits[0]
        sb += reindent(t[i:block(t, i) + 1], 8)

    anchor = "    Scope (\\_SB)\n    {\n"
    tail = "            Method (PPPM, 0, NotSerialized) { Return (PPPP) }"
    if s.count(anchor) != 1 or s.count(tail) != 1:
        sys.exit("SSDT layout not recognised (expected one \\_SB scope and PPPM)")
    s = s.replace(anchor, anchor + "        // Platform names used by the pipa PEP0 objects below\n"
                  + "\n".join(sb) + "\n", 1)
    s = s.replace(tail, tail + "\n" + "\n".join(pep))
    open(args.out, "w").write(s)
    print(f"imported {len(imported)} PEP0 objects ({len(pep)} lines) "
          f"and {len(PLATFORM)} platform names; skipped {sorted(SKIP & set(objs))}")


if __name__ == "__main__":
    main()
