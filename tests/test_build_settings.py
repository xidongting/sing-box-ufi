"""CLI contract for extracting the actual upstream Android build parameters."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildSettingsTests(unittest.TestCase):
    def extract(self, flags, extra='', shared_flags=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.github/workflows').mkdir(parents=True)
            (root / 'cmd/internal/build_shared').mkdir(parents=True)
            (root / 'cmd/internal/build_shared/sdk.go').write_text('const fixedVersion = "28.0.13004108"')
            if shared_flags is not None:
                (root / 'release').mkdir()
                (root / 'release/LDFLAGS').write_text(shared_flags)
            steps = [
                {'uses': 'actions/setup-go@v5', 'with': {'go-version': '1.24.5'}},
                {'name': 'Set build tags', 'run': "TAGS='with_quic,with_gvisor'"},
                {'name': 'Build Android', 'env': {'CGO_ENABLED': '1', 'BUILD_GOOS': '${{ matrix.os }}', 'BUILD_GOARCH': '${{ matrix.arch }}'},
                 'run': 'GOOS=$BUILD_GOOS GOARCH=$BUILD_GOARCH build go build -v -trimpath -o dist/sing-box -tags "${BUILD_TAGS}" '
                        + extra + ' -ldflags ' + flags + ' \\\n./cmd/sing-box'},
            ]
            entries = [{'os': 'android', 'arch': 'arm64', 'ndk': 'aarch64-linux-android21'},
                       {'os': 'android', 'arch': 'arm', 'ndk': 'armv7a-linux-androideabi21'}]
            (root / '.github/workflows/build.yml').write_text(json.dumps({'jobs': {
                'build': {'steps': steps, 'strategy': {'matrix': {'include': entries}}}}}))
            return subprocess.run([sys.executable, str(ROOT / 'scripts/build-settings.py'), str(root)],
                                  text=True, capture_output=True)

    def test_preserves_legacy_android_linker_flags_without_adding_w(self):
        result = self.extract("'-s -buildid= -X github.com/sagernet/sing-box/constant.Version=${{ needs.calculate_version.outputs.version }}'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['ldflags'],
                         '-s -buildid= -X github.com/sagernet/sing-box/constant.Version=__VERSION__')

    def test_expands_shared_flags_and_preserves_upstream_order(self):
        result = self.extract('"-X \'github.com/sagernet/sing-box/constant.Version=${{ needs.calculate_version.outputs.version }}\' ${LDFLAGS_SHARED} -s -w -buildid="',
                              shared_flags='-checklinkname=0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['ldflags'],
                         "-X 'github.com/sagernet/sing-box/constant.Version=__VERSION__' -checklinkname=0 -s -w -buildid=")

    def test_unrecognized_build_flag_fails_instead_of_silent_omission(self):
        result = self.extract("'-s'", '-race')
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
