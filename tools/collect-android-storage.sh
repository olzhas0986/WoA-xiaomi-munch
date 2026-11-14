#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output="$root/out/munch-fresh/android-storage.txt"
adb get-state >/dev/null
adb shell 'echo DATA_FILESYSTEM; stat -f /data; echo DATA_USAGE; df -k /data; echo ENCRYPTION_STATE; getprop ro.crypto.state; getprop ro.crypto.type; echo DATA_MOUNT; cat /proc/mounts | grep " /data "; echo RECOVERY; getprop ro.bootmode' >"$output" 2>&1
cat "$output"
echo "Saved: $output"
