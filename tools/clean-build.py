#!/usr/bin/env python3
"""Preview or remove known local build products, refusing tracked sources."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    'out',
    'Mu-Silicium/Build',
    'Mu-Silicium/Platforms/Xiaomi/munchFreshPkg',
    'Mu-Silicium/Binaries/munchFresh',
)


def candidates():
    paths = [ROOT / name for name in OUTPUTS if (ROOT / name).exists()]
    paths.extend((ROOT / 'firmware/munch/Acpi').glob('*.aml'))
    # Keep dependency checkouts, templates, environments and repository metadata.
    # Only Python bytecode is selected outside the explicit generated paths.
    for directory, dirs, files in os.walk(ROOT, followlinks=False):
        base = Path(directory)
        dirs[:] = [name for name in dirs if name not in (
            '.git', '.venv', '.agents', '.aws', '.codex', 'vendor-templates')
            and not (base / name).is_symlink()
            and not any((base / name).is_relative_to(p) for p in paths)]
        if '__pycache__' in dirs:
            paths.append(base / '__pycache__')
            dirs.remove('__pycache__')
        paths.extend(base / name for name in files if name.endswith(('.pyc', '.pyo')))
    return sorted(set(paths))


def check(path):
    if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
        raise RuntimeError(f'Refusing path outside checkout or symlink: {path}')
    # Query the owning repository (including Mu submodules), not just the root.
    repo = Path(subprocess.check_output(
        ['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'], text=True).strip())
    tracked = subprocess.check_output([
        'git', '-C', str(repo), 'ls-files', '-z', '--', str(path.relative_to(repo))])
    if tracked:
        raise RuntimeError(f'Refusing path containing tracked files: {path}')
    if path.is_dir():
        for directory, dirs, files in os.walk(path, followlinks=False):
            if '.git' in dirs or '.git' in files:
                raise RuntimeError(f'Refusing nested repository: {directory}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Delete after checking every path; default is preview')
    args = parser.parse_args()
    paths = candidates()
    for path in paths:
        check(path)
    for path in paths:
        print(('Remove ' if args.apply else 'Would remove ') + str(path.relative_to(ROOT)))
        if args.apply:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    print(f'{len(paths)} generated paths; ' + ('removed' if args.apply else 'preview only'))


if __name__ == '__main__':
    main()
