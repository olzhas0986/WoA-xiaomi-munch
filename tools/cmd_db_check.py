#!/usr/bin/env python3
"""Check the PEP resource list (PPPM) against the phone's RPMh Command DB.

qcpep8250 classifies every non-GPIO resource in PPPM by looking it up in
the Command DB (RVA 0x11F1B8 via 0x114600). The lookup fails with
STATUS_UNSUCCESSFUL, which ends in bugcheck 0x14E, unless

  * an entry with the derived name exists,
  * its slave header version is 1.x (0x100..0x1FF),
  * its aux data is exactly 4 bytes.

Names are derived as in RVA 0x11EA10 (prefix + index within the PPRR range):
SMPSn_X -> smpXn, LDOn_X -> ldoXn, VSn_X -> vsXn, BUCK_BOOSTn_X -> bobXn,
CXO_BUFFERS_BBCLKn_X -> lnbclkXn, _RFCLKn_X -> rfclkXn, _DIVCLKn_X -> divclkXn.
GPIO DV resources are not looked up.

Input is either the Linux debugfs text (/sys/kernel/debug/cmd-db) or the raw
reserved region (128 KiB at 0x80860000 on munch) that RpmhPeek saves as
\\cmddb.bin on the ESP.

Example:
    cmd_db_check.py cmd-db.txt SSDT-GPU-PEP.asl
"""
import argparse
import re
import struct
import sys

CMD_DB_MAGIC = bytes([0xDB, 0x30, 0x03, 0x0C])
SLAVES = {3: "ARC", 4: "VRM", 5: "BCM"}

RULES = [
    (r"SMPS(\d+)_([A-Z])$", "smp{1}{0}"),
    (r"LDO(\d+)_([A-Z])$", "ldo{1}{0}"),
    (r"VS(\d+)_([A-Z])$", "vs{1}{0}"),
    (r"BUCK_BOOST(\d+)_([A-Z])$", "bob{1}{0}"),
    (r"CXO_BUFFERS_BBCLK(\d+)_([A-Z])$", "lnbclk{1}{0}"),
    (r"CXO_BUFFERS_RFCLK(\d+)_([A-Z])$", "rfclk{1}{0}"),
    (r"CXO_BUFFERS_DIVCLK(\d+)_([A-Z])$", "divclk{1}{0}"),
]


def cmd_db_name(resource):
    short = resource.replace("PPP_RESOURCE_ID_", "")
    if "GPIO_DV" in short:
        return None
    for pattern, fmt in RULES:
        m = re.match(pattern, short)
        if m:
            return fmt.format(m.group(1), m.group(2).lower())
    return "?"


def parse_debugfs(text):
    """Linux cmd_db_debugfs_dump: 'Slave X (vM.m)' then '0x00030: name [aux]'."""
    entries, slave, version = {}, None, None
    for line in text.splitlines():
        m = re.match(r"Slave (\S+) \(v(\d+)\.(\d+)\)", line)
        if m:
            slave, version = m.group(1), (int(m.group(2)) << 8) | int(m.group(3))
            continue
        m = re.match(r"(0x[0-9a-f]+): (\S+)(?: \[([0-9a-f ]*)\])?", line.strip())
        if m and slave:
            aux = bytes.fromhex(m.group(3).replace(" ", "")) if m.group(3) else b""
            entries[m.group(2)] = (slave, version, int(m.group(1), 16), aux)
    return entries


def parse_binary(data):
    """Layout as in Linux drivers/soc/qcom/cmd-db.c and qcpep RVA 0x114600."""
    if data[4:8] != CMD_DB_MAGIC:
        sys.exit(f"bad Command DB magic {data[4:8].hex()}")
    entries = {}
    for i in range(8):
        slv, hoff, doff, cnt, ver = struct.unpack_from("<5H", data, 8 + 16 * i)
        if not cnt:
            continue
        for j in range(cnt):
            o = 0x90 + hoff + 24 * j
            ident = data[o:o + 8].split(b"\0")[0].decode("latin-1")
            addr, length, aoff = struct.unpack_from("<IHH", data, o + 16)
            a = 0x90 + doff + aoff
            entries[ident] = (SLAVES.get(slv, str(slv)), ver, addr, data[a:a + length])
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd_db", help="debugfs cmd-db dump")
    ap.add_argument("ssdt", help="ASL with the PPPP package")
    ap.add_argument("--list", action="store_true", help="also print every Command DB entry")
    args = ap.parse_args()

    raw = open(args.cmd_db, "rb").read()
    db = parse_binary(raw) if raw[4:8] == CMD_DB_MAGIC else parse_debugfs(raw.decode("latin-1"))
    if not db:
        sys.exit("no Command DB entries parsed")
    if args.list:
        for k, (slave, ver, addr, aux) in sorted(db.items(), key=lambda e: e[1][2]):
            print(f"{slave:4} v{ver >> 8}.{ver & 0xff} {addr:#07x} {k:10} {aux.hex()}")
    asl = open(args.ssdt).read()
    block = asl[asl.index("Name (PPPP"):]
    block = block[:block.index("})")]
    resources = re.findall(r'"(PPP_RESOURCE_ID_\w+)"', block)

    bad = 0
    for r in resources:
        name = cmd_db_name(r)
        if name is None:
            continue
        e = db.get(name)
        if e is None:
            verdict = "MISSING"
        else:
            slave, ver, addr, aux = e
            ok = 0x100 <= ver < 0x200 and len(aux) == 4
            verdict = (f"ok   {slave} v{ver >> 8}.{ver & 0xff} addr {addr:#x} aux {aux.hex()}" if ok else
                       f"FAIL {slave} v{ver >> 8}.{ver & 0xff} addr {addr:#x} aux len {len(aux)}")
        bad += not verdict.startswith("ok")
        print(f"{r:44} {name:10} {verdict}")
    print(f"{bad} resource(s) would fail the qcpep lookup")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
