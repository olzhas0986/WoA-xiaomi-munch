#!/usr/bin/env python3
"""Read the active Android device tree over ADB; never access block devices."""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile


@contextmanager
def collection_directory(parent):
    staging = Path(tempfile.mkdtemp(dir=parent, prefix='android-dt-'))
    try:
        yield staging
    except BaseException:
        print(f'Collection failed; diagnostics retained at: {staging}', file=sys.stderr)
        raise
    else:
        shutil.rmtree(staging)


def live_tree_root(tree):
    # adb versions differ in whether a directory pull creates base/base.
    # Do not search arbitrary descendant compatible properties: those may be devices.
    for candidate in (tree, tree/'base'):
        compatible = candidate/'compatible'
        if compatible.is_file() and compatible.read_bytes().strip(b'\0'):
            return candidate
    listing = '\n'.join(str(p.relative_to(tree)) for p in sorted(tree.glob('*'))[:20])
    raise SystemExit('Pulled tree has no readable, nonempty root compatible at '
                     f'{tree} or {tree / "base"}.\nTop-level entries:\n{listing}\n'
                     'See adb-pull.log in the retained diagnostic directory.')


def collect_tree_archive(adb, staging, root):
    command = 'tar -c -C /sys/firmware/devicetree/base .'
    remote = ['su', '-c', command] if root else ['sh', '-c', command]
    # ADB joins remote arguments into a shell command; quote the -c body once.
    result = subprocess.run([*adb, 'exec-out', shlex.join(remote)], capture_output=True)
    (staging/'adb-tar.log').write_bytes(result.stderr)
    if result.returncode:
        (staging/'adb-tar.stdout').write_bytes(result.stdout)
        raise SystemExit(f'Android tar failed ({result.returncode}); see adb-tar.log '
                         'and adb-tar.stdout in the retained directory.')
    tree = staging/'archive-tree'
    tree.mkdir()
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:') as archive:
            archive.extractall(tree, filter='data')
    except (tarfile.TarError, OSError) as error:
        (staging/'adb-tar.stdout').write_bytes(result.stdout)
        raise SystemExit(f'Invalid live-tree archive: {error}; see adb-tar.stdout.') from error
    return live_tree_root(tree)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb', help='ADB executable, including a Windows adb.exe path in WSL')
    parser.add_argument('--serial', help='ADB transport serial, when multiple devices exist')
    parser.add_argument('--output', type=Path, default=Path('out/android-dt'))
    parser.add_argument('--root', action='store_true',
                        help='use existing Android su for the raw FDT read only')
    args = parser.parse_args()
    adb = [args.adb] + (['-s', args.serial] if args.serial else [])

    def run(*command):
        return subprocess.run([*adb, *command], capture_output=True, check=True)

    for program in (args.adb, 'dtc', 'fdtget'):
        if not shutil.which(program):
            parser.error(f'{program} is required on the host')
    if args.output.exists():
        parser.error('output already exists; choose a new directory')
    run('get-state')
    device = run('shell', 'getprop', 'ro.product.device').stdout.decode().strip()
    if device != 'munch':
        parser.error(f'expected Android ro.product.device=munch, received {device!r}')
    fingerprint = run('shell', 'getprop', 'ro.build.fingerprint').stdout.decode().strip()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with collection_directory(args.output.parent) as staging:
        dtb = staging/'active.dtb'
        command = (['exec-out', shlex.join(['su', '-c', 'cat /sys/firmware/fdt'])] if args.root
                   else ['exec-out', 'cat', '/sys/firmware/fdt'])
        result = subprocess.run([*adb, *command], capture_output=True)
        (staging/'raw-read.log').write_bytes(
            f'exit={result.returncode} stdout_bytes={len(result.stdout)}\n'.encode()
            + result.stderr)
        data = result.stdout
        raw_valid = (result.returncode == 0 and len(data) >= 40 and
                     data[:4] == b'\xd0\x0d\xfe\xed' and
                     40 <= struct.unpack_from('>I', data, 4)[0] <= len(data))
        if raw_valid:
            dtb.write_bytes(data[:struct.unpack_from('>I', data, 4)[0]])
            method = '/sys/firmware/fdt'
        else:
            (staging/'raw-read.stdout').write_bytes(data)
            print('Raw FDT unavailable; trying the readable live OF tree.')
            tree = staging/'base'
            destination = str(tree)
            if args.adb.lower().endswith('.exe'):
                # Windows ADB needs a Windows host path, including for WSL files.
                if not shutil.which('wslpath'):
                    parser.error('Windows ADB requires wslpath when used from WSL')
                destination = subprocess.run(
                    ['wslpath', '-w', str(tree.resolve())], capture_output=True,
                    text=True, check=True).stdout.strip()
            try:
                pulled = run('pull', '/sys/firmware/devicetree/base', destination)
            except subprocess.CalledProcessError as error:
                (staging/'adb-pull.log').write_bytes(error.stdout + error.stderr)
                raise SystemExit('ADB cannot read the live tree. No artifact published.\n'
                                 + error.stderr.decode(errors='replace') +
                                 '\nIf Android already has su, retry with --root.') from error
            (staging/'adb-pull.log').write_bytes(pulled.stdout + pulled.stderr)
            try:
                tree = live_tree_root(tree)
            except SystemExit:
                print('Pull has no root properties; trying Android tar over exec-out.')
                try:
                    tree = collect_tree_archive(adb, staging, args.root)
                except SystemExit:
                    diagnostic = subprocess.run(
                        [*adb, 'shell', 'ls -ld /sys/firmware/fdt '
                         '/sys/firmware/devicetree/base /proc/device-tree; '
                         'ls -la /sys/firmware/devicetree/base/'], capture_output=True)
                    (staging/'android-paths.log').write_bytes(
                        diagnostic.stdout + diagnostic.stderr)
                    raise
            subprocess.run(['dtc', '-I', 'fs', '-O', 'dtb', '-o', str(dtb), str(tree)],
                           check=True)
            method = '/sys/firmware/devicetree/base (reconstructed)'
        subprocess.run(['fdtget', str(dtb), '/', 'compatible'], check=True)
        subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', '-o',
                        str(staging/'active.dts'), str(dtb)], check=True)
        metadata = {'device': device, 'fingerprint': fingerprint, 'method': method,
                    'dtb_sha256': hashlib.sha256(dtb.read_bytes()).hexdigest()}
        (staging/'source.json').write_text(json.dumps(metadata, indent=2)+'\n')
        # Publish only validated artifacts; raw tree and temporary failures stay private.
        args.output.mkdir()
        for name in ('active.dtb', 'active.dts', 'source.json'):
            shutil.copyfile(staging/name, args.output/name)
    print('Saved:', args.output)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f'Command failed ({error.returncode}): {error.cmd}', file=sys.stderr)
        for stream in (error.stdout, error.stderr):
            if stream:
                print(stream.decode(errors='replace'), file=sys.stderr)
        raise SystemExit(1) from error
