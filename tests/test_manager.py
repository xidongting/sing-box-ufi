"""Public manager CLI tests. Run on Linux (including the documented container)."""
import os
from pathlib import Path
import subprocess
import tempfile
import hashlib
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.boot = Path(self.tmp.name) / 'ufi_tools_boot.sh'
        self.env = dict(os.environ, SBU_HOME=str(self.home), SBU_BOOT=str(self.boot))

    def run_cli(self, *args, input=None):
        return subprocess.run(['sh', str(ROOT / 'device/manager.sh'), *args],
                              input=input, text=True, capture_output=True, env=self.env)

    def test_save_validates_before_replacing_and_does_not_start(self):
        self.home.mkdir()
        binary = self.home / 'sing-box'
        binary.write_text('#!/bin/sh\nif [ "$1" = check ]; then grep -q valid "$3"; fi\n')
        binary.chmod(0o700)
        result = self.run_cli('save', input='valid configuration')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli('save', input='broken')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / 'config.json').read_text(), 'valid configuration')
        self.assertIn('stopped', self.run_cli('status').stdout)

    def test_autostart_preserves_existing_script_and_is_idempotent(self):
        self.boot.write_text('#!/system/bin/sh\necho existing\nexit 0\n')
        for _ in range(2):
            result = self.run_cli('autostart', 'on')
            self.assertEqual(result.returncode, 0, result.stderr)
        script = self.boot.read_text()
        self.assertEqual(script.count('# sing-box-ufi'), 1)
        self.assertIn('echo existing\nexit 0\n', script)
        self.assertLess(script.index('# sing-box-ufi'), script.index('exit 0'))
        self.assertIn('autostart=on', self.run_cli('status').stdout)
        self.assertEqual(self.run_cli('autostart', 'off').returncode, 0)
        self.assertNotIn('# sing-box-ufi', self.boot.read_text())

    @unittest.skipUnless(sys.platform == 'linux', 'process identity requires Linux /proc')
    def test_upgrade_stops_and_preserves_config_and_autostart(self):
        self.home.mkdir()
        source = Path(self.tmp.name) / 'fixture.c'
        source.write_text('''#include <string.h>
#include <unistd.h>
int main(int argc, char **argv) {
 if (argc > 1 && !strcmp(argv[1], "version")) return 0;
 if (argc > 1 && !strcmp(argv[1], "check")) return 0;
 while (1) sleep(1);
}''')
        binary = Path(self.tmp.name) / 'core'
        subprocess.run(['cc', str(source), '-o', str(binary)], check=True)
        staged = self.home / 'incoming'
        shutil.copy(binary, staged)
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        self.assertEqual(self.run_cli('install', digest).returncode, 0)
        self.assertEqual(self.run_cli('save', input='{}').returncode, 0)
        self.assertEqual(self.run_cli('autostart', 'on').returncode, 0)
        self.assertEqual(self.run_cli('start').returncode, 0)
        self.addCleanup(lambda: self.run_cli('stop'))
        pid = (self.home / 'sing-box.pid').read_text()
        self.assertEqual(self.run_cli('start').returncode, 0)
        self.assertEqual((self.home / 'sing-box.pid').read_text(), pid)
        shutil.copy(binary, staged)
        self.assertNotEqual(self.run_cli('install', '0' * 64).returncode, 0)
        self.assertIn('running', self.run_cli('status').stdout)
        self.assertEqual(self.run_cli('install', digest).returncode, 0)
        status = self.run_cli('status').stdout
        self.assertIn('stopped', status)
        self.assertIn('autostart=on', status)
        self.assertEqual((self.home / 'config.json').read_text(), '{}')
        # Upgrade must not reject an incompatible config or automatically run the new core.
        source.write_text(source.read_text().replace('!strcmp(argv[1], "check")) return 0;',
                                                     '!strcmp(argv[1], "check")) return 9;'))
        subprocess.run(['cc', str(source), '-o', str(staged)], check=True)
        digest = hashlib.sha256(staged.read_bytes()).hexdigest()
        self.assertEqual(self.run_cli('install', digest).returncode, 0)
        self.assertNotEqual(self.run_cli('start').returncode, 0)
        self.assertIn('stopped', self.run_cli('status').stdout)

    def test_uninstall_keeps_configuration_unless_purge_requested(self):
        self.home.mkdir()
        (self.home / 'config.json').write_text('private config')
        (self.home / 'sing-box').write_text('old core')
        self.assertEqual(self.run_cli('uninstall', 'keep').returncode, 0)
        self.assertFalse((self.home / 'sing-box').exists())
        self.assertEqual((self.home / 'config.json').read_text(), 'private config')
        self.assertEqual(self.run_cli('uninstall', 'purge').returncode, 0)
        self.assertFalse((self.home / 'config.json').exists())

    def test_invalid_pid_never_signals_unrelated_process(self):
        self.home.mkdir()
        (self.home / 'sing-box.pid').write_text(str(os.getpid()))
        result = self.run_cli('stop')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / 'sing-box.pid').exists())

    def test_missing_configuration_is_not_created_on_status(self):
        result = self.run_cli('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('stopped', result.stdout)
        self.assertFalse((self.home / 'config.json').exists())


if __name__ == '__main__':
    unittest.main()
