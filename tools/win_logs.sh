#!/usr/bin/env bash
# Pull Windows setup and boot logs from the phone, read-only, over adb in recovery.
#
#   tools/win_logs.sh [partition number, default 36] [-o out/win-logs]
#
# The recovery kernel has no NTFS driver, so static ntfscat/ntfsls are pushed
# to /tmp and read the volume directly; nothing is mounted or written.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NR=36 OUT="$ROOT/out/win-logs"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) OUT="$2"; shift 2 ;;
    *)  NR="$1"; shift ;;
  esac
done
BIN="$ROOT/out/recovery-tools/bin"
DEV="/dev/block/sda$NR"

adb get-state 2>/dev/null | grep -q recovery || { echo "phone is not in recovery over adb" >&2; exit 2; }
adb shell "test -b $DEV" || { echo "$DEV not found" >&2; exit 2; }
adb push -q "$BIN/ntfscat" "$BIN/ntfsls" /tmp/
adb shell chmod 755 /tmp/ntfscat /tmp/ntfsls

mkdir -p "$OUT"
FILES=(
  /Windows/Panther/setuperr.log
  /Windows/Panther/setupact.log
  /Windows/Panther/UnattendGC/setuperr.log
  /Windows/Panther/UnattendGC/setupact.log
  /Windows/Panther/unattend.xml
  /Windows/INF/setupapi.dev.log
  /Windows/INF/setupapi.offline.log
  /Windows/INF/setupapi.setup.log
  /Windows/System32/LogFiles/Srt/SrtTrail.txt
  /Windows/Logs/CBS/CBS.log
  /Windows/ntbtlog.txt
)
for f in "${FILES[@]}"; do
  name="$(echo "${f#/Windows/}" | tr '/' '_')"
  if adb exec-out "/tmp/ntfscat -f $DEV '$f' 2>/dev/null" > "$OUT/$name" && [[ -s "$OUT/$name" ]]; then
    printf '%-48s %8d bytes\n' "$f" "$(stat -c %s "$OUT/$name")"
  else
    rm -f "$OUT/$name"
  fi
done
adb exec-out "/tmp/ntfsls -f -l $DEV -p /Windows/Panther 2>&1" > "$OUT/panther-listing.txt" || true
adb exec-out "/tmp/ntfsls -f -l $DEV -p /Windows/Minidump 2>&1" > "$OUT/minidump-listing.txt" || true
echo "-> $OUT"
