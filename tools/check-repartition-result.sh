#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output="$root/out/munch-fresh/repartition32/android-after.txt"
adb get-state >/dev/null
adb shell 'echo DATA; df -k /data; stat -f /data; echo ENCRYPTION; getprop ro.crypto.state; getprop ro.crypto.type; echo PARTITIONS; for name in userdata esp msr win; do echo "$name"; node=$(readlink -f /dev/block/bootdevice/by-name/$name); if [ -z "$node" ]; then node=$(readlink -f /dev/block/by-name/$name); fi; echo "$node"; leaf=${node##*/}; if [ -n "$leaf" ]; then cat /sys/class/block/$leaf/start /sys/class/block/$leaf/size 2>&1; fi; done; echo END' >"$output" 2>&1
cat "$output"
echo "Saved: $output"
