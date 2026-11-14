#!/usr/bin/env python3
"""Export only tracked, pinned kernel sources; verify and extract BusyBox archive."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

KERNEL_REV = '58161ead29e50d70a317ea26b472e0c7508e69da'
BUSYBOX_SHA = '3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel-repo', type=Path, required=True)
p.add_argument('--kernel-tar', type=Path)
p.add_argument('--kernel-sha256', help='required expected SHA256 for --kernel-tar')
p.add_argument('--busybox-tar', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--patch', type=Path, action='append', default=[])
a = p.parse_args()
revision = KERNEL_REV
if a.kernel_tar:
    if not a.kernel_sha256 or len(a.kernel_sha256) != 64:
        p.error('--kernel-tar requires --kernel-sha256')
    with a.kernel_tar.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != a.kernel_sha256:
        raise SystemExit('kernel archive SHA256 mismatch')
    revision = 'archive-sha256:' + digest
elif a.kernel_sha256:
    p.error('--kernel-sha256 requires --kernel-tar')
a.out.mkdir(parents=True, exist_ok=True)
patches = [path.resolve() for path in a.patch]
patch_ids = [hashlib.sha256(path.read_bytes()).hexdigest() for path in patches]
patch_marker = a.out/'kernel.patches.json'
kernel = a.out/'linux-src'
if not kernel.exists():
    archive = a.out/'linux-source.tar'
    if not a.kernel_tar:
        with archive.open('wb') as f:
            subprocess.run(['git', '-C', str(a.kernel_repo), 'archive', KERNEL_REV], stdout=f, check=True)
    with tempfile.TemporaryDirectory(dir=a.out, prefix='kernel-extract-') as temporary:
        staged = Path(temporary)/'linux-src'
        if a.kernel_tar:
            with tarfile.open(a.kernel_tar) as t:
                t.extractall(temporary, filter='data')
            roots = list(Path(temporary).iterdir())
            if len(roots) != 1 or not roots[0].is_dir() or roots[0].is_symlink():
                raise SystemExit('expected one kernel archive directory')
            roots[0].rename(staged)
            if not (staged/'Makefile').is_file() or not (staged/'arch/arm64').is_dir():
                raise SystemExit('not a Linux ARM64 source archive')
        else:
            staged.mkdir()
            with tarfile.open(archive) as t:
                t.extractall(staged, filter='data')
        for path in patches:
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(path)],
                           cwd=staged, check=True)
        staged.rename(kernel)
    patch_marker.write_text(json.dumps(patch_ids)+'\n')
    if not a.kernel_tar:
        archive.unlink()
    (a.out/'kernel.revision').write_text(revision+'\n')
elif not (a.out/'kernel.revision').exists() or (a.out/'kernel.revision').read_text().strip() != revision:
    raise SystemExit('existing linux-src has no matching revision marker; use a fresh OUT')
applied = json.loads(patch_marker.read_text()) if patch_marker.exists() else []
if applied != patch_ids:
    raise SystemExit('source patch set changed: use a fresh OUT; never mutate the baseline source')
if hashlib.sha256(a.busybox_tar.read_bytes()).hexdigest() != BUSYBOX_SHA:
    raise SystemExit('BusyBox 1.37.0 archive SHA-256 mismatch')
if not (a.out/'busybox-1.37.0').exists():
    with tempfile.TemporaryDirectory(dir=a.out, prefix='busybox-extract-') as temporary:
        with tarfile.open(a.busybox_tar) as t:
            t.extractall(temporary, filter='data')
        (Path(temporary)/'busybox-1.37.0').rename(a.out/'busybox-1.37.0')
print('Sources ready:', kernel, revision)
