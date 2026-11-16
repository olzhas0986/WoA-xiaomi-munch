#!/usr/bin/env bash
# Prepare the Windows payload on the PC (needs wimlib and 7z).
#
#   tools/prepare_image.sh <windows.iso> [--index N] [--user NAME] [-o out/win]
#
# Produces in the output directory:
#   install.esd       the chosen edition only, with unattend.xml, solid LZMS
#   BCD-Template      template store for tools/make_bcd.py
#   esp/EFI/...       boot manager files for the ESP (what bcdboot would copy)
#   image.txt         edition name, build and sizes
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO="" INDEX="" USER_NAME="user" OUT="$ROOT/out/win"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --index) INDEX="$2"; shift 2 ;;
    --user)  USER_NAME="$2"; shift 2 ;;
    -o)      OUT="$2"; shift 2 ;;
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) ISO="$1"; shift ;;
  esac
done
[[ -f "$ISO" ]] || { echo "usage: $0 <windows.iso> [--index N]" >&2; exit 2; }
[[ "$USER_NAME" =~ ^[A-Za-z0-9_.-]{1,20}$ ]] || { echo "invalid user name" >&2; exit 2; }
for tool in wimlib-imagex 7z; do
  command -v "$tool" >/dev/null || {
    echo "missing $tool (Arch: sudo pacman -S --needed wimlib 7zip)" >&2; exit 2; }
done

mkdir -p "$OUT"
STAGE="$OUT/stage"
rm -rf "$STAGE" && mkdir -p "$STAGE"

echo "==> install.wim from the ISO"
7z e -y -bso0 -bsp0 -o"$STAGE" "$ISO" sources/install.wim
WIM="$STAGE/install.wim"

if [[ -z "$INDEX" ]]; then
  INDEX="$(wimlib-imagex info "$WIM" | awk -F': *' '
    /^Index:/ {idx=$2}
    /^Name:/ && /IoT Enterprise LTSC/ && !/Subscription/ {print idx; exit}')"
  [[ -n "$INDEX" ]] || { wimlib-imagex info "$WIM" | grep -E '^(Index|Name):'
                         echo "pick an edition with --index" >&2; exit 1; }
fi
wimlib-imagex info "$WIM" "$INDEX" | grep -E '^(Name|Architecture|Build|Total Bytes):' \
  | tee "$OUT/image.txt"
grep -q 'Architecture:.*ARM64' "$OUT/image.txt" || { echo "not an ARM64 image" >&2; exit 1; }

echo "==> export edition $INDEX and add unattend.xml"
wimlib-imagex export "$WIM" "$INDEX" "$STAGE/edition.wim" --compress=LZX
sed "s/@USER@/$USER_NAME/g" "$ROOT/port/windows/unattend.xml" > "$STAGE/unattend.xml"
wimlib-imagex update "$STAGE/edition.wim" 1 \
  --command="add '$STAGE/unattend.xml' /Windows/Panther/unattend.xml"

echo "==> boot files"
rm -rf "$OUT/esp" "$STAGE/boot"
wimlib-imagex extract "$STAGE/edition.wim" 1 --dest-dir="$STAGE/boot" --no-acls \
  /Windows/Boot/EFI /Windows/Boot/Fonts /Windows/System32/config/BCD-Template
mkdir -p "$OUT/esp/EFI/Microsoft/Boot" "$OUT/esp/EFI/Boot"
cp -r "$STAGE/boot/EFI/." "$OUT/esp/EFI/Microsoft/Boot/"
cp -r "$STAGE/boot/Fonts" "$OUT/esp/EFI/Microsoft/Boot/"
cp "$STAGE/boot/EFI/bootmgfw.efi" "$OUT/esp/EFI/Boot/bootaa64.efi"
cp "$STAGE/boot/BCD-Template" "$OUT/BCD-Template"

echo "==> install.esd (solid LZMS, this takes a while)"
rm -f "$OUT/install.esd"
wimlib-imagex export "$STAGE/edition.wim" 1 "$OUT/install.esd" --solid
wimlib-imagex verify "$OUT/install.esd" >/dev/null
rm -rf "$STAGE"

ls -l "$OUT/install.esd" | awk '{printf "install.esd: %.2f GiB\n", $5/2^30}'
sha256sum "$OUT/install.esd" | tee "$OUT/install.esd.sha256"
