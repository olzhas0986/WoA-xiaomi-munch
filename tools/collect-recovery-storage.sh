#!/usr/bin/env bash
# Read-only recovery inspection and GPT backup to the PC.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
out="$root/out/munch-fresh/recovery-storage"
mkdir -p "$out"
adb get-state >/dev/null
identity=$(adb shell id | tr -d '\r')
if [[ "$identity" != *'uid=0('* ]]; then
  echo 'Boot recovery with root ADB first; no disk operation was performed.' >&2
  exit 1
fi
adb shell 'echo ID; id; echo RECOVERY; getprop ro.twrp.version; getprop ro.build.version.release; echo MOUNTS; cat /proc/mounts | grep " /data "; echo USAGE; df -k /data; echo TOOLS; command -v resize.f2fs; command -v fsck.f2fs; echo RESIZE_HELP; resize.f2fs -h 2>&1; echo F2FS_VERSION; fsck.f2fs -V 2>&1; echo DATA_LINK; readlink -f /dev/block/bootdevice/by-name/userdata; echo END' >"$out/info.txt" 2>&1
partition=$(adb shell readlink -f /dev/block/bootdevice/by-name/userdata | tr -d '\r\n')
leaf=${partition##*/}
if [[ ! "$leaf" =~ ^sd[a-z]+[0-9]+$ ]]; then
  echo "Unexpected userdata device: $partition; stopped before backup." >&2
  exit 1
fi
diskleaf=${leaf%%[0-9]*}
disk="/dev/block/$diskleaf"
geometry=$(adb shell "cat /sys/class/block/$diskleaf/queue/logical_block_size; cat /sys/class/block/$diskleaf/size" | tr -d '\r')
printf '%s\n' "$geometry" >"$out/geometry.txt"
blocksize=$(printf '%s\n' "$geometry" | sed -n '1p')
sectors=$(printf '%s\n' "$geometry" | sed -n '2p')
if [[ "$blocksize" != 4096 || ! "$sectors" =~ ^[0-9]+$ ]]; then
  echo 'Unexpected disk geometry; stopped before backup.' >&2
  exit 1
fi
blocks=$((sectors / 8))
if (( sectors % 8 != 0 || blocks < 64 )); then exit 1; fi
# Each snapshot holds 32 logical blocks. This covers this phone's 64-entry GPT.
for side in primary backup; do
  offset=0
  if [[ "$side" == backup ]]; then offset=$((blocks - 32)); fi
  tmp="$out/gpt-$side.new.bin"
  adb exec-out "dd if=$disk bs=4096 skip=$offset count=32 2>/dev/null" >"$tmp"
  [[ $(wc -c <"$tmp") == 131072 ]] || { echo 'Short GPT backup' >&2; exit 1; }
  target="$out/gpt-$side.bin"
  if [[ -e "$target" ]]; then
    cmp "$target" "$tmp" || { echo 'Existing GPT backup differs; retained both files.' >&2; exit 1; }
    rm "$tmp"
  else
    mv "$tmp" "$target"
  fi
done
printf '%s\n' "$disk" >"$out/disk.txt"
sha256sum "$out"/gpt-*.bin >"$out/SHA256SUMS"
cat "$out/info.txt"
echo "Saved recovery inspection and GPT snapshots: $out"
