"""Extract Android CLI settings from the selected upstream tag; fail on unknown layout."""
import json
from pathlib import Path
import re
import sys

import yaml

source = Path(sys.argv[1])
workflow = yaml.safe_load((source / '.github/workflows/build.yml').read_text())
jobs = [job for job in workflow['jobs'].values()
        if any(step.get('name') == 'Build Android' for step in job.get('steps', []))]
if len(jobs) != 1:
    raise ValueError('Upstream Android CLI build job changed; review adapter')
job = jobs[0]
steps = job['steps']
go = next(s['with']['go-version'] for s in steps if s.get('uses', '').startswith('actions/setup-go@'))
if not re.fullmatch(r'\^?\d+\.\d+\.\d+', str(go)):
    raise ValueError('Unsupported upstream Go version expression')
ndk_source = (source / 'cmd/internal/build_shared/sdk.go').read_text()
ndk = re.search(r'const fixedVersion = "([0-9.]+)"', ndk_source)
if not ndk:
    raise ValueError('Upstream NDK discovery changed')
build = next(s['run'] for s in steps if s.get('name') == 'Build Android')
if 'CGO_ENABLED' not in next(s['env'] for s in steps if s.get('name') == 'Build Android'):
    raise ValueError('Upstream Android build environment changed')
if 'build go build' not in build or './cmd/sing-box' not in build:
    raise ValueError('Upstream Android build command changed')
tag_step = next(s['run'] for s in steps if s.get('name') == 'Set build tags')
tags_file = source / 'release/DEFAULT_BUILD_TAGS_OTHERS'
if 'release/DEFAULT_BUILD_TAGS_OTHERS' in tag_step and tags_file.exists():
    tags = tags_file.read_text().strip()
else:
    match = re.search(r"TAGS='([a-z0-9_,]+)'", tag_step)
    if not match:
        raise ValueError('Upstream build tags changed; refusing guessed feature set')
    tags = match[1]
ldflags_file = source / 'release/LDFLAGS'
ldflags = ldflags_file.read_text().strip() if ldflags_file.exists() else ''
if not re.fullmatch(r'[a-z0-9_,]+', tags):
    raise ValueError('Invalid build tags')
compilers = {}
for entry in job['strategy']['matrix']['include']:
    if entry.get('os') == 'android' and entry['arch'] in ('arm', 'arm64'):
        compiler = entry['ndk']
        if not re.fullmatch(r'[a-z0-9_-]+android(?:eabi)?\d+', compiler):
            raise ValueError('Invalid Android compiler')
        compilers[entry['arch']] = compiler
if set(compilers) != {'arm', 'arm64'}:
    raise ValueError('Upstream ARM targets changed')
settings = dict(go=str(go), ndk=ndk[1], tags=tags, ldflags=ldflags, compilers=compilers)
print(json.dumps(settings, indent=2))
