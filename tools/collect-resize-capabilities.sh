#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output="$root/out/munch-fresh/resize-capabilities.txt"
adb get-state >/dev/null
adb shell 'echo ID; id; echo ANDROID; getprop ro.build.version.release; getprop ro.build.version.sdk; echo KERNEL; uname -r; echo TOOLS; command -v su; command -v resize.f2fs; command -v fsck.f2fs; echo RESIZE_HELP; resize.f2fs -h 2>&1; echo DM_NAME; cat /sys/block/dm-44/dm/name 2>&1; echo FSTAB; for f in /vendor/etc/fstab* /odm/etc/fstab*; do if [ -f "$f" ]; then echo "$f"; cat "$f"; fi; done; echo END' >"$output" 2>&1
cat "$output"
echo "Saved: $output"
