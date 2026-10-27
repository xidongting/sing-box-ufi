const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const os = require('node:os');
const path = require('node:path');

test('native plugin package mounts one button without running device commands', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sbu-plugin-'));
    try {
        execFileSync('python3', ['scripts/package-plugin.py', '--repo', 'example/sing-box-ufi', '--out', dir]);
        const packaged = fs.readFileSync(path.join(dir, 'sing-box-ufi.js'), 'utf8');
        assert.ok(packaged.startsWith('<!-- [KANO_PLUGIN_START] sing-box-ufi -->'));
        const script = packaged.match(/<script>\n([\s\S]*)\n<\/script>/)[1];
        assert.ok(!script.includes('__REPOSITORY__'));
        const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'plugins.json')));
        assert.equal(manifest.res.code, 200);
        assert.equal(manifest.res.data.content[0].name, 'sing-box-ufi.js');
        assert.equal(manifest.download_url, 'https://github.com/example/sing-box-ufi/releases/download/plugin-v0.1.0');
        let mounts = 0;
        let button;
        const context = vm.createContext({
            document: {
                readyState: 'complete',
                getElementById(id) {
                    if (id === 'sing-box-ufi-button') return button;
                    if (id === 'PLUGIN_SETTING') return {insertAdjacentElement(_, item) { button = item; mounts++; }};
                },
                createElement() { return {addEventListener() {}}; },
            },
            runShellWithRoot() { assert.fail('loading plugin must not run shell commands'); },
            createModal() {},
        });
        vm.runInContext(script, context);
        vm.runInContext(script, context);
        assert.equal(mounts, 1);
        assert.equal(button.textContent, 'sing-box');
    } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});
