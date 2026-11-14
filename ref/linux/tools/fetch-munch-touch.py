#!/usr/bin/env python3
"""Fetch a bounded set of official munch touch sources for offline review."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

REPO = 'MiCode/Xiaomi_Kernel_OpenSource'
BRANCH = 'munch-s-oss'
API = 'https://api.github.com/repos/'+REPO
FILES = {'Kconfig', 'Makefile', 'focaltech_config.h', 'focaltech_common.h',
         'focaltech_core.h', 'focaltech_core.c', 'focaltech_spi.c',
         'focaltech_flash.h', 'focaltech_flash.c'}
DIRECTORIES = ('focaltech_3658u', 'focaltech_spi', 'focaltech_touch', 'fts_spi')


def fetch(url, limit=4*1024*1024):
    request = urllib.request.Request(url, headers={'User-Agent':'pmos-munch-touch-audit',
                                                  'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('source exceeds download limit')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/munch-touch-stock'))
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('output already exists; use a fresh --output directory')
        commit = json.loads(fetch(API+'/commits/'+BRANCH))['sha']
        if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
            raise ValueError('invalid commit ID')
        manifest = {'repository':REPO, 'branch':BRANCH, 'commit':commit, 'files':{}, 'missing':[]}
        args.output.mkdir(parents=True)
        for directory in DIRECTORIES:
            path = 'drivers/input/touchscreen/'+directory
            try:
                entries = json.loads(fetch(API+'/contents/'+path+'?ref='+commit))
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                manifest['missing'].append(path)
                continue
            for entry in entries:
                name = entry.get('name')
                if entry.get('type') != 'file' or name not in FILES:
                    continue
                relative = directory+'/'+name
                url = 'https://raw.githubusercontent.com/'+REPO+'/'+commit+'/'+path+'/'+name
                data = fetch(url)
                destination = args.output/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                manifest['files'][relative] = {'sha256':hashlib.sha256(data).hexdigest(), 'url':url}
                print(relative, len(data), 'bytes', flush=True)
        if not manifest['files']:
            raise ValueError('no matching touch source files found')
        (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print('Ready for offline review:', args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, 'touch-fetch: '+str(error)+'\n')


if __name__ == '__main__':
    main()
