#!/usr/bin/env python3
"""Make a GPU28E variant of the previous port's PEP installer that never starts PEP.

The GPU28D package (munch-pep-fix-windows.zip) disables the PEP device,
installs the original qcpep package, writes the test policy and finally runs
`pnputil /enable-device`. The original qcpep8250 then stops with bugcheck
0x14B at the display RSC TCS check (docs/rpmh-config.md).

GPU28E keeps every step up to the verified policy and replaces the final
enable with `sc config qcpep start= disabled`, leaving the state the LMH test
expects for prepare.cmd: driver installed from the DriverStore, service
Start = 4, device disabled (code 22). manifest.json is updated for the
changed script; everything else is copied unchanged.

Example:
    package_pep_install_disabled.py munch-pep-fix-windows.zip -o out/qcpep/munch-pep-gpu28e.zip
"""
import argparse
import hashlib
import json
import sys
import zipfile

SRC, DST = "GPU28D/", "GPU28E/"
SCRIPT = "bootstrap.ps1"
ENABLE = (
    "$null=Native 'pnputil.exe' @('/enable-device',$p[0].PNPDeviceID) 'enable.log'\n"
    "$state.phase='enabled';Save-State\n"
    "Report\n"
    "$p=@(Pep)\n"
    "if($p.Count -eq 1 -and $p[0].Service -ieq 'qcpep' -and $p[0].ConfigManagerErrorCode -eq 0)"
    "{Write-Host 'PEP core started: code 0. CPU management and system low power remain disabled.'}\n"
    "else{Write-Host 'PEP core did not start. Send the status table; report saved.'}"
)
DISABLED = (
    "# GPU28E: the original qcpep8250 stops at the display RSC TCS check, so it is\n"
    "# never started here. Leave it installed, disabled and with Start = 4 for the\n"
    "# signed LMH + display TCS test copy (MunchPepLmh prepare/start).\n"
    "$null=Native 'sc.exe' @('config','qcpep','start=','disabled') 'start-disabled.log'\n"
    "$start=Optional-RegistryValue 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\qcpep' 'Start'\n"
    "if($start -ne 4){Report;throw 'qcpep Start readback is not 4'}\n"
    "$state.phase='installed-disabled-start4';Save-State\n"
    "Report\n"
    "Write-Host 'PEP installed, device disabled (22), qcpep Start = 4. Not started.'\n"
    "Write-Host 'Next: MunchPepLmh prepare.cmd, reboot, start.cmd.'"
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    with zipfile.ZipFile(args.package) as z:
        files = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    script = files.get(SRC + SCRIPT)
    if script is None:
        sys.exit("not a GPU28D package")
    text = script.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    enable = ENABLE.replace("\n", newline)
    if text.count(enable) != 1:
        sys.exit("GPU28D bootstrap.ps1 does not end with the expected enable step")
    text = text.replace(enable, DISABLED.replace("\n", newline))
    text = text.replace("Boot Windows28 again, then rerun this same setup.cmd.",
                        "Reboot, then rerun this same setup.cmd.")
    files[SRC + SCRIPT] = (b"\xef\xbb\xbf" if script.startswith(b"\xef\xbb\xbf") else b"") + \
        text.encode("utf-8")

    manifest = json.loads(files[SRC + "manifest.json"])
    for f in manifest["files"]:
        f["sha256"] = hashlib.sha256(files[SRC + f["path"]]).hexdigest().upper() \
            if f["sha256"].isupper() else hashlib.sha256(files[SRC + f["path"]]).hexdigest()
    manifest["stage"] = "PEP installed disabled (GPU28E); original qcpep not started"
    files[SRC + "manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            z.writestr(DST + name[len(SRC):], files[name])
    print(f"{args.out}: {hashlib.sha256(open(args.out, 'rb').read()).hexdigest()}")


if __name__ == "__main__":
    main()
