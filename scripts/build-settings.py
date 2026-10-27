"""Extract Android CLI settings from the selected upstream tag; fail on unknown layout."""
import json
from pathlib import Path
import re
import sys
import shlex

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
build_env = next(s['env'] for s in steps if s.get('name') == 'Build Android')
if str(build_env.get('CGO_ENABLED')) != '1' or set(build_env) - {'CGO_ENABLED', 'BUILD_GOOS', 'BUILD_GOARCH', 'GITHUB_TOKEN'}:
    raise ValueError('Upstream Android build environment changed')
normalized = build.replace('\\\n', ' ')
match = re.search(r'build go build (.*?\./cmd/sing-box)(?:\s*$|\n)', normalized)
if not match:
    raise ValueError('Upstream Android build command changed')
arguments = shlex.split(match[1])
expected = ['-v', '-trimpath', '-o', 'dist/sing-box', '-tags', '${BUILD_TAGS}', '-ldflags']
if arguments[:7] != expected or len(arguments) != 9 or arguments[-1] != './cmd/sing-box':
    raise ValueError('Upstream Android build flags changed; review adapter')
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
ldflags = arguments[7].replace('${{ needs.calculate_version.outputs.version }}', '__VERSION__')
if '${LDFLAGS_SHARED}' in ldflags:
    ldflags = ldflags.replace('${LDFLAGS_SHARED}', ldflags_file.read_text().strip())
if '$' in ldflags or '__VERSION__' not in ldflags:
    raise ValueError('Upstream Android linker flags changed; review adapter')
if not re.fullmatch(r'[a-z0-9_,]+', tags):
    raise ValueError('Invalid build tags')
compilers = {}
for entry in job['strategy']['matrix']['include']:
    if entry.get('os') == 'android' and entry['arch'] in ('arm', 'arm64'):
        if set(entry) != {'os', 'arch', 'ndk'}:
            raise ValueError('Upstream Android target options changed; review adapter')
        compiler = entry['ndk']
        if not re.fullmatch(r'[a-z0-9_-]+android(?:eabi)?\d+', compiler):
            raise ValueError('Invalid Android compiler')
        compilers[entry['arch']] = compiler
if set(compilers) != {'arm', 'arm64'}:
    raise ValueError('Upstream ARM targets changed')
settings = dict(go=str(go), ndk=ndk[1], tags=tags, ldflags=ldflags, compilers=compilers)
print(json.dumps(settings, indent=2))
