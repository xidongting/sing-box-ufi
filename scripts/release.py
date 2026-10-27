"""Release discovery and packaging; only Python standard library and gh CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil


def validate_tag(tag):
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?', tag):
        raise ValueError(f'Unsupported official version tag: {tag!r}')
    return tag


def version_key(tag):
    validate_tag(tag)
    core, _, preview = tag[1:].partition('-')
    numbers = tuple(map(int, core.split('.')))
    if not preview:
        return (*numbers, 3, 0)
    channel, number = preview.split('.')
    return (*numbers, {'alpha': 0, 'beta': 1, 'rc': 2}[channel], int(number))


def select_versions(upstream, published):
    latest = {}
    for item in upstream:
        if item['draft']:
            continue
        try:
            tag = validate_tag(item['tag_name'])
        except ValueError:
            # Historical release names (e.g. v1.3-rc2) are not current build targets.
            continue
        channel = item['prerelease']
        if channel not in latest or version_key(tag) > version_key(latest[channel]):
            latest[channel] = tag
    return [tag for tag in latest.values() if 'core-' + tag not in published]


def releases(repo):
    result = subprocess.check_output(['gh', 'api', '--paginate', '--slurp',
                                     f'repos/{repo}/releases?per_page=100'], text=True)
    return [item for page in json.loads(result) for item in page]


def discover(repo, tag):
    upstream = releases('SagerNet/sing-box')
    if tag:
        validate_tag(tag)
        if not any(r['tag_name'] == tag and not r['draft'] for r in upstream):
            raise ValueError('Tag must belong to a published upstream Release')
        tags = [tag]
    else:
        tags = select_versions(upstream, {r['tag_name'] for r in releases(repo) if not r['draft']})
    print(json.dumps(tags))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write('tags=' + json.dumps(tags) + '\n')


def package(out, binary, source, license_file, tag, arch, commit, settings):
    validate_tag(tag)
    if arch not in ('arm', 'arm64') or not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Invalid build identity')
    out.mkdir(parents=True, exist_ok=True)
    name = f'sing-box-android-{arch}'
    shutil.copyfile(binary, out / name)
    shutil.copyfile(source, out / f'sing-box-source-{tag}-{arch}.tar.gz')
    shutil.copyfile(license_file, out / 'LICENSE.sing-box')
    sdk = int(re.search(r'(\d+)$', settings['compilers'][arch])[1])
    metadata = dict(tag=tag, commit=commit, architecture=arch, minimum_android_sdk=sdk,
                    source=f'https://github.com/SagerNet/sing-box/tree/{commit}', **settings)
    (out / f'build-{arch}.json').write_text(json.dumps(metadata, indent=2) + '\n')
    names = [name, f'build-{arch}.json', f'sing-box-source-{tag}-{arch}.tar.gz', 'LICENSE.sing-box']
    (out / f'SHA256SUMS-{arch}').write_text(''.join(
        f'{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}\n' for n in names))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    discovery = commands.add_parser('discover')
    discovery.add_argument('--repo', required=True)
    discovery.add_argument('--tag', default='')
    pack = commands.add_parser('package')
    for name in ('out', 'binary', 'source', 'license'):
        pack.add_argument('--' + name, required=True, type=Path)
    for name in ('tag', 'arch', 'commit'):
        pack.add_argument('--' + name, required=True)
    pack.add_argument('--settings', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'discover':
        discover(args.repo, args.tag)
    else:
        package(args.out, args.binary, args.source, args.license, args.tag, args.arch,
                args.commit, json.loads(args.settings.read_text()))
