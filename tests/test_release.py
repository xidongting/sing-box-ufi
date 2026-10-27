import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_package_contains_raw_binary_checksums_and_corresponding_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'sing-box'
            binary.write_bytes(b'example binary')
            source = root / 'source.tar.gz'
            source.write_bytes(b'corresponding source archive')
            license_file = root / 'LICENSE'
            license_file.write_text('GPL-3.0-or-later notice')
            settings = {'go': '1.26.10', 'ndk': '28.0.13004108', 'tags': 'with_quic',
                        'ldflags': '', 'compilers': {'arm64': 'aarch64-linux-android23'}}
            out = root / 'out'
            release.package(out, binary, source, license_file, 'v1.14.4', 'arm64', 'a' * 40, settings)
            self.assertEqual((out / 'sing-box-android-arm64').read_bytes(), b'example binary')
            self.assertIn('sing-box-android-arm64', (out / 'SHA256SUMS-arm64').read_text())
            import json
            metadata = json.loads((out / 'build-arm64.json').read_text())
            self.assertEqual(metadata['minimum_android_sdk'], 23)
            self.assertEqual(metadata['commit'], 'a' * 40)
            self.assertTrue((out / 'sing-box-source-v1.14.4-arm64.tar.gz').exists())
            self.assertTrue((out / 'LICENSE.sing-box').exists())

    def test_discovery_uses_versions_not_api_order_or_draft_channel_flags(self):
        upstream = [
            {'tag_name': 'v1.14.1', 'prerelease': False, 'draft': False},
            {'tag_name': 'v1.15.0-alpha.9', 'prerelease': True, 'draft': False},
            {'tag_name': 'v1.14.4', 'prerelease': False, 'draft': False},
            {'tag_name': 'v1.15.0-alpha.10', 'prerelease': True, 'draft': False},
            {'tag_name': 'v1.15.0-rc.1', 'prerelease': True, 'draft': False},
        ]
        self.assertEqual(set(release.select_versions(upstream, set())), {'v1.14.4', 'v1.15.0-rc.1'})

    def test_latest_stable_and_preview_skip_published_and_drafts(self):
        upstream = [
            {'tag_name': 'v1.15.0-alpha.2', 'prerelease': True, 'draft': False},
            {'tag_name': 'v1.15.0-alpha.1', 'prerelease': True, 'draft': False},
            {'tag_name': 'v1.14.4', 'prerelease': False, 'draft': False},
            {'tag_name': 'v1.16.0', 'prerelease': False, 'draft': True},
        ]
        self.assertEqual(release.select_versions(upstream, {'core-v1.14.4'}), ['v1.15.0-alpha.2'])
        self.assertEqual(release.select_versions(upstream, {'core-v1.14.4', 'core-v1.15.0-alpha.2'}), [])
        with self.assertRaises(ValueError):
            release.validate_tag('v1.2.3; echo unsafe')


if __name__ == '__main__':
    unittest.main()
