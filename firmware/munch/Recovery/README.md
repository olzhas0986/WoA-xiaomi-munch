# Munch WinPE files recovery package

Build with `python3 tools/package-winpe-recovery.py` after preparing the 4Kn
images with `tools/prepare-winpe-disk.py`. Output:
`out/winpe/munch-winpe-files-twrp.zip`.

The shell update-binary targets the user's Android 12-based TWRP 3.7.1 with
/system/bin/sh, root ADB/recovery utilities, and the already-created 32GiB
layout. It verifies munch product properties, exact by-name device mappings,
4Kn logical sectors, exact ESP/win sizes and absence of mounts. It extracts
512MiB ESP and 640MiB WinPE raw images into recovery RAM, verifies both hashes
before the first write, writes win then ESP, syncs and verifies each readback.
Only those two new partitions are targeted. UEFI launch remains separate, as
requested; boot slots/GPT/Android partitions are not flashed by this installer.

`tools/tests/check-recovery-installer.py` runs the actual shell logic on host
file-backed fake partitions, changing only command lookup for mock utilities.
Wrong device, wrong size and wrong hash cases are rejected before writes. The
success case writes only the intended two fake partitions and verifies both
readbacks. ZIP CRC and decompressed image hashes also pass host checks.
Host fixtures do not validate device-side recovery writes. The confirmed
Windows desktop and foundation-driver status is recorded in
[STATUS.md](../../../STATUS.md); follow the normal cable/VBUS sequence in
[README.md](../../../README.md) for temporary firmware boot.
