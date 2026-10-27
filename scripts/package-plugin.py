"""Build UFI Tools' HTML-in-.js format and its native plugin-source manifest."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def package(repository, out):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repository):
        raise ValueError('Expected owner/repo')
    version = json.loads((ROOT / 'package.json').read_text())['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Expected semantic plugin version')
    script = (ROOT / 'plugin/plugin.js').read_text()
    script = script.replace('__REPOSITORY__', repository).replace('__PLUGIN_VERSION__', version)
    script = script.replace('__MANAGER_BASE64__', base64.b64encode((ROOT / 'device/manager.sh').read_bytes()).decode())
    if '</script' in script.lower():
        raise ValueError('Script contains HTML closing tag')
    body = ('<!-- [KANO_PLUGIN_START] sing-box-ufi -->\n<script>\n' + script +
            '\n</script>\n<!-- [KANO_PLUGIN_END] sing-box-ufi -->\n').encode()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'sing-box-ufi.js').write_bytes(body)
    manifest = {
        'download_url': f'https://github.com/{repository}/releases/download/plugin-v{version}',
        'res': {'code': 200, 'message': 'success', 'data': {'content': [{
            'name': 'sing-box-ufi.js', 'size': len(body), 'is_dir': False,
            'modified': datetime.now(timezone.utc).isoformat(),
            'hash_info': {'md5': hashlib.md5(body).hexdigest()},
        }]}},
    }
    (out / 'plugins.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}\n'
        for name in ('sing-box-ufi.js', 'plugins.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist/plugin')
    args = parser.parse_args()
    package(args.repo, args.out)
