#!/usr/bin/env python3
"""Package small Phosh helpers for installation into the existing RAM rootfs."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'usr/local/bin/pmos-connect': ('pmos-connect', 0o755),
    'usr/local/bin/pmos-save-current': ('pmos-save-current', 0o755),
    'usr/local/bin/phosh-start': ('phosh-start', 0o755),
    'usr/local/libexec/pmos-munch-phosh-session': ('phosh-session', 0o755),
    'usr/local/share/pmos-munch/display-panels/xiaomi,munch.json': ('xiaomi,munch.json', 0o644),
}


def build():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for target, (source, mode) in sorted(FILES.items()):
            data = (ROOT/'phone'/source).read_bytes()
            entry = tarfile.TarInfo(target)
            entry.mode, entry.size = mode, len(data)
            tar.addfile(entry, io.BytesIO(data))
    return gzip.compress(buf.getvalue(), mtime=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/phosh-tools.tar.gz')
    args = parser.parse_args()
    data = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    args.output.with_name(args.output.name+'.sha256').write_text(
        hashlib.sha256(data).hexdigest()+'  '+args.output.name+'\n')
    print(args.output, len(data), 'bytes')
