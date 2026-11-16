#!/usr/bin/env bash
# Cross-build the static aarch64 tools the recovery installer needs.
#
#   scripts/build_recovery_tools.sh
#
# Output (out/recovery-tools/bin):
#   sfdisk, partx    util-linux: GPT editing, BLKPG partition updates
#   mkntfs           ntfs-3g ntfsprogs: create the Windows NTFS volume
#   wimlib-imagex    apply the ESD directly to the NTFS volume (NTFS-3G mode)
#   mkfs.fat         dosfstools: create the FAT32 ESP
#
# Everything is linked statically against glibc, so the binaries run in any
# Android recovery regardless of its own userspace.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/work/recovery-tools"
DL="$WORK/dl"
SRC="$WORK/src"
PREFIX="$WORK/prefix"
OUT="$ROOT/out/recovery-tools/bin"
HOST=aarch64-linux-gnu
JOBS="$(nproc)"

# name|url|sha256
SOURCES=(
  "util-linux-2.40.4|https://www.kernel.org/pub/linux/utils/util-linux/v2.40/util-linux-2.40.4.tar.xz|5c1daf733b04e9859afdc3bd87cc481180ee0f88b5c0946b16fdec931975fb79"
  "ntfs-3g_ntfsprogs-2022.10.3|https://tuxera.com/opensource/ntfs-3g_ntfsprogs-2022.10.3.tgz|f20e36ee68074b845e3629e6bced4706ad053804cbaf062fbae60738f854170c"
  "wimlib-1.14.5|https://wimlib.net/downloads/wimlib-1.14.5.tar.gz|84221a3abd5b91228f15f8e6065c335a336237b5738197b75bf419eea561a194"
  "dosfstools-4.2|https://github.com/dosfstools/dosfstools/releases/download/v4.2/dosfstools-4.2.tar.gz|64926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527"
)

for tool in "$HOST-gcc" "$HOST-strip" curl make pkgconf; do
  command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 2; }
done

mkdir -p "$DL" "$SRC" "$PREFIX" "$OUT"

fetch() {
  local name="$1" url="$2" sum="$3" file="$DL/${2##*/}"
  [[ -f "$file" ]] || curl -fsSL --retry 3 -o "$file" "$url"
  echo "$sum  $file" | sha256sum -c --quiet - || { echo "checksum mismatch: $file" >&2; exit 1; }
  rm -rf "$SRC/$name"
  tar -xf "$file" -C "$SRC"
}

for entry in "${SOURCES[@]}"; do
  IFS='|' read -r name url sum <<<"$entry"
  fetch "$name" "$url" "$sum"
done

export CC="$HOST-gcc" AR="$HOST-ar" RANLIB="$HOST-ranlib" STRIP="$HOST-strip"
export CFLAGS="-O2 -pipe" LDFLAGS="-static"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig" PKG_CONFIG_SYSROOT_DIR=""
COMMON=(--host="$HOST" --prefix="$PREFIX" --disable-shared --enable-static)

echo "==> util-linux (sfdisk, partx)"
( cd "$SRC/util-linux-2.40.4"
  # --enable-fdisks also selects cfdisk, which needs ncurses; build only sfdisk
  sed -i 's/^enable_cfdisk=\$enable_fdisks$/enable_cfdisk=no/' configure
  ./configure "${COMMON[@]}" --disable-all-programs \
      --enable-libuuid --enable-libblkid --enable-libsmartcols --enable-libfdisk \
      --enable-fdisks --enable-partx \
      --without-python --without-systemd --without-udev --without-ncursesw \
      --without-ncurses --without-tinfo --without-readline --without-cap-ng \
      --without-libmagic --without-btrfs --disable-nls --disable-bash-completion \
      --disable-asciidoc --disable-poman --disable-makeinstall-chown \
      --disable-makeinstall-setuid >/dev/null
  make -j"$JOBS" sfdisk partx LDFLAGS="-all-static" >/dev/null
  install -m755 sfdisk partx "$OUT/" )

echo "==> ntfs-3g (libntfs-3g, mkntfs)"
( cd "$SRC/ntfs-3g_ntfsprogs-2022.10.3"
  ./configure "${COMMON[@]}" --disable-ntfs-3g --enable-ntfsprogs \
      --disable-crypto --disable-extras --disable-mount-helper \
      --disable-ldconfig --with-fuse=internal --without-uuid --without-hd \
      --disable-plugins >/dev/null
  make -j"$JOBS" LDFLAGS="-all-static" >/dev/null
  make install rootlibdir="$PREFIX/lib" rootbindir="$PREFIX/bin" rootsbindir="$PREFIX/sbin" >/dev/null
  install -m755 ntfsprogs/mkntfs "$OUT/" )

echo "==> wimlib (NTFS-3G backend)"
( cd "$SRC/wimlib-1.14.5"
  ./configure "${COMMON[@]}" --with-ntfs-3g --without-fuse --disable-test-support \
      NTFS_3G_CFLAGS="-I$PREFIX/include/ntfs-3g" \
      NTFS_3G_LIBS="-L$PREFIX/lib -lntfs-3g" >/dev/null
  make -j"$JOBS" wimlib-imagex LDFLAGS="-all-static" >/dev/null
  install -m755 wimlib-imagex "$OUT/" )

echo "==> dosfstools (mkfs.fat)"
( cd "$SRC/dosfstools-4.2"
  ./configure "${COMMON[@]}" --without-udev --disable-compat-symlinks >/dev/null
  make -j"$JOBS" -C src mkfs.fat >/dev/null
  install -m755 src/mkfs.fat "$OUT/" )

"$STRIP" "$OUT"/*
for bin in "$OUT"/*; do
  file "$bin" | grep -q "statically linked" || { echo "not static: $bin" >&2; exit 1; }
done
( cd "$OUT" && sha256sum * > SHA256SUMS && file * )
