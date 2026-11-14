# Confirm munch USB2 PHY supply wiring

G passed on hardware: user confirmed SMMU enabled and the display remained
visible after about a minute. DMA through DWC3 remains untested.

## Why this input is needed

The old local munch-usb.dtsi explicitly says its regulator topology was copied
verbatim from SM8250 MTP. It is not independent evidence of munch wiring.
Mainline elish uses PM8150 L5A, L12A and L2A for USB2 PHY supplies, but it is a
different board. Do not program those rails on munch solely from that analogy.

The local boot.img is boot header v3 and contains no validated FDT candidate;
no stock vendor_boot/DTBO image was found. Network attempts to retrieve Xiaomi's
munch sources failed. The old full.dtb is modified mainline, not a stock DT.

Collect the effective Android tree to resolve USB2 PHY supply phandles to
regulator nodes, resource IDs, voltage constraints and parent supplies. Verify
Android's USB wrapper/PHY selection too. Do not transplant the vendor tree.

## Read-only collection

Boot the existing Android installation normally. Enable USB debugging and
connect ADB. No flash, partition read, bootloader relock, adb root or installation
of su is required by this script. It writes artifacts only on the host.
From pmos-munch, with host adb, dtc and fdtget installed:

```sh
python3 tools/collect-android-dt.py
```

The tool requires ro.product.device=munch, first reads /sys/firmware/fdt using
adb exec-out, then falls back to adb pull of /sys/firmware/devicetree/base.
If both are denied and Android already has su, the optional --root uses su only
for the raw FDT cat. Do not root the phone just for this collection. Report the
permission error if neither method works; a stock vendor_boot/DTBO file supplied
on the host is another possible source. Multiple ADB devices need --serial.
An existing output directory is rejected; choose --output for a new destination.

Expected host files:

- out/android-dt/active.dtb
- out/android-dt/active.dts
- out/android-dt/source.json (build fingerprint, collection method and DTB hash)

If collection fails, report the complete terminal error. If it succeeds, keep
these files in the shared workspace for analysis. They are ignored build
artifacts and are not automatically committed or sent elsewhere.

The filesystem fallback reconstructs the live OF tree; its memreserve map is
not equivalent to the raw flattened blob. Use it to inspect device properties,
not to replace the validated RAM map or boot DTB.

## Local verification

Python compile/help and a host fixture check passed for raw export/provenance,
existing-output refusal and wrong-device rejection. Actual Android permissions
and fallback collection are not yet hardware-tested. dtc warnings remain visible.

## WSL with Windows ADB

Windows ADB was found at /mnt/c/platform-tools/adb.exe on this host. In a WSL
terminal, use:

```sh
python3 tools/collect-android-dt.py --adb /mnt/c/platform-tools/adb.exe
```

--adb selects the executable. Binary exec-out is captured directly by Python;
for pull, wslpath translates the host destination for Windows ADB. No USBIP
attachment is needed when Windows ADB can access the phone.

The agent's execution environment rejected Windows executable interop with
UtilBindVsockAnyPort, so physical transport has not been tested. If this also
happens in the user's WSL terminal, use Windows CMD (not PowerShell redirection):

```bat
C:\platform-tools\adb.exe devices
C:\platform-tools\adb.exe pull /sys/firmware/devicetree/base C:\platform-tools\munch-dt
```

Then decompile in WSL, provided pull completed without errors:

```sh
mkdir -p out/android-dt-windows
dtc -I fs -O dts -o out/android-dt-windows/active.dts /mnt/c/platform-tools/munch-dt
```

If devices is empty, check Android USB debugging/authorization first. For
permission denied, retain the error; this is different from a WSL transport
failure. Do not install root or modify partitions to collect this information.

## Missing root compatible after pull

The user's Windows-ADB run reached dtc, but fdtget reported FDT_ERR_NOTFOUND for
root compatible. Transport worked; the cause of the incomplete/wrong root was
not established. The earlier collector deleted temporary evidence on failure.

The collector now checks both base and base/base for a nonempty root compatible
before compiling. It never substitutes an arbitrary child device as the root.
On failure it preserves the staging directory, raw-read.log and adb-pull.log,
prints its path, and leaves the final output unpublished. Retry the same command;
if it fails, report its complete output and retain that directory. No su is
inferred from this error. Host regressions cover direct/nested pulls and missing
root with evidence retention; the corrected hardware collection is pending.

The retained hardware log showed exactly `0 files pulled, 0 skipped`, with an
empty destination, so directory nesting did not explain this run. The collector
now tries Android tar via binary adb exec-out when pull yields no root properties.
This bypasses ADB sync directory traversal; host extraction uses tarfile's data
filter. It still requires Android read access and does not grant permissions.
If tar also fails, its stderr/stdout and android-paths.log are retained. Raw FDT
logging now includes exit status, byte count and unsuccessful stdout, because
exec-out errors can appear on stdout. The host fixture covers successful archive
fallback after an empty pull; actual phone result remains pending.

## Confirmed Android shell permission restriction (2026-10-18)

Hardware diagnostics in out/android-dt-dt__koa7 establish read denial:
raw-read.stdout contains `cat: /sys/firmware/fdt: Permission denied` despite
exec-out reporting exit=0. android-paths.log lists root properties as ????????;
the archive contains only an empty mem-offline directory. This is not evidence
that Android's underlying DT has no SoC nodes or supplies. The shell cannot
collect a usable tree with current permissions. No further unprivileged retries
are warranted. SELinux versus other permission enforcement is not established.

Next input must be either an already available Android su context (--root),
or stock firmware vendor_boot/DTBO files on the host. Do not install root,
disable SELinux or read/write partitions as a workaround. Parsing stock files
is offline; flashing them is neither needed nor authorized. The board revision
and applicable overlays still need to be resolved before trusting their wiring.
Root raw-FDT command quoting now retains the complete su -c body as one argument.
