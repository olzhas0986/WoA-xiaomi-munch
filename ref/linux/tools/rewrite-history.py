#!/usr/bin/env python3
"""Prepare/apply the reviewed single-commit project history, with local backups."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT/'out/rebrand-backup'
PLAN = BACKUP/'rewrite-plan.json'
DIRECTORIES = ('configs', 'docs', 'dts', 'initramfs', 'kernel-drivers',
               'loader', 'native', 'patches', 'phone', 'tests', 'tools')
TOP_FILES = ('.gitattributes', '.gitignore', 'Makefile', 'README.md')
MESSAGE = '''pmos-munch: establish postmarketOS bring-up for POCO F4

Include the EL1 boot path, board profiles, USB recovery, RAM userspace,
Wi-Fi, native display, Freedreno rendering, touch and Phosh helpers.
Keep the native OpenRC handoff experimental pending a successful device boot.
'''


def git(*args, capture=False):
    return subprocess.run(['git', *args], cwd=ROOT, check=True,
                          text=True, capture_output=capture)


def files():
    paths = [ROOT/name for name in TOP_FILES]
    for name in DIRECTORIES:
        paths.extend(p for p in (ROOT/name).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    if any(p.is_symlink() for p in paths):
        raise RuntimeError('review source symlinks before rewriting history')
    return sorted({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in paths}.items())


def prepare():
    BACKUP.mkdir(parents=True, exist_ok=True)
    branch = git('symbolic-ref', '--short', 'HEAD', capture=True).stdout.strip()
    heads = git('for-each-ref', '--format=%(refname)', 'refs/heads', capture=True).stdout.splitlines()
    if heads != ['refs/heads/'+branch]:
        raise RuntimeError('multiple local branches require a separate history review')
    if git('remote', capture=True).stdout.strip():
        raise RuntimeError('remote configured; review publication separately before rewriting')
    # Always keep a fresh backup of every current local ref.
    bundle = BACKUP/'history-before-rewrite.bundle'
    if bundle.exists():
        git('bundle', 'verify', str(bundle))
    else:
        git('bundle', 'create', str(bundle), '--all')
    entries = dict(files())
    snapshot = BACKUP/'reviewed-sources.tar.gz'
    with tarfile.open(snapshot, 'w:gz') as archive:
        for name in entries:
            archive.add(ROOT/name, arcname=name, recursive=False)
    index = ROOT/'.git/index'
    if index.is_file() and not (BACKUP/'index.before').exists():
        shutil.copyfile(index, BACKUP/'index.before')
    refs = git('show-ref', capture=True).stdout
    plan = {'branch': branch, 'head': git('rev-parse', 'HEAD', capture=True).stdout.strip(),
            'refs': refs, 'files': entries, 'message': MESSAGE,
            'backup': str(bundle.relative_to(ROOT)),
            'result': 'one new root commit; existing tags removed; no push'}
    PLAN.write_text(json.dumps(plan, indent=2)+'\n')
    print('Prepared:', PLAN)
    print('Reviewed source files:', len(entries))
    print('Backup:', bundle)


def apply(rename_directory=False):
    plan = json.loads(PLAN.read_text())
    if git('rev-parse', 'HEAD', capture=True).stdout.strip() != plan['head']:
        raise RuntimeError('HEAD changed since review; prepare a new plan')
    if git('show-ref', capture=True).stdout != plan['refs']:
        raise RuntimeError('refs changed since review; prepare a new plan')
    if dict(files()) != plan['files']:
        raise RuntimeError('sources changed since review; prepare a new plan')
    git('bundle', 'verify', str(ROOT/plan['backup']))
    git('var', 'GIT_AUTHOR_IDENT', capture=True)
    destination = ROOT.with_name('pmos-munch')
    if rename_directory and destination != ROOT and destination.exists():
        raise RuntimeError('destination directory already exists: '+str(destination))
    # Fail on a read-only .git before changing HEAD or branches.
    git('add', '--', '.gitignore')
    git('checkout', '--orphan', 'pmos-munch-clean')
    git('read-tree', '--empty')
    git('add', '--', *plan['files'])
    git('diff', '--cached', '--check')
    message = BACKUP/'commit-message.txt'
    message.write_text(plan['message'])
    git('commit', '--file', str(message))
    git('branch', '-M', plan['branch'])
    for line in plan['refs'].splitlines():
        old, ref = line.split(' ', 1)
        if ref.startswith('refs/tags/'):
            git('update-ref', '-d', ref, old)
    git('log', '--oneline', '--all')
    git('status', '--short')
    if rename_directory and destination != ROOT:
        ROOT.rename(destination)
        print('Project directory:', destination)
        print('Reopen the workspace at this path; rebuild path-dependent caches if needed.')
    print('History rewritten locally. No remote was contacted. Backups are under out/rebrand-backup/.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--rename-directory', action='store_true')
    args = parser.parse_args()
    if args.rename_directory and not args.apply:
        parser.error('--rename-directory requires --apply')
    try:
        prepare() if args.prepare else apply(args.rename_directory)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'History rewrite stopped: {error}\n')
