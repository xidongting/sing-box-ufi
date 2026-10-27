const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const os = require('node:os');
const path = require('node:path');

function loadPanel(shell) {
    class Element {
        constructor() { this.listeners = {}; this.dataset = {}; this.textContent = ''; this.value = ''; }
        addEventListener(type, handler) { this.listeners[type] = handler; }
        setAttribute() {}
        removeAttribute() { this.settled?.(); }
    }
    const elements = new Map(['[data-config]', '[data-status]', '[data-output]', '[data-import]']
        .map(key => [key, new Element()]));
    const panel = new Element();
    panel.querySelector = key => elements.get(key);
    let button;
    vm.runInNewContext(fs.readFileSync('plugin/plugin.js', 'utf8'), {
        document: {
            readyState: 'complete',
            getElementById(id) { return id === 'PLUGIN_SETTING' ? {insertAdjacentElement(_, item) { button = item; }} : null; },
            createElement() { return new Element(); },
        },
        HTMLElement: Element, TextEncoder,
        btoa: text => Buffer.from(text, 'binary').toString('base64'),
        runShellWithRoot: shell,
        createModal() { return {el: panel, id: '#sing_box_ufi'}; },
        showModal() {}, confirm: () => true,
    });
    const open = () => new Promise(resolve => { panel.settled = resolve; button.listeners.click(); });
    const click = action => new Promise(resolve => {
        panel.settled = resolve;
        const target = new Element();
        target.dataset.action = action;
        panel.listeners.click({target});
    });
    return {elements, open, click};
}

test('saving an allowed large configuration fits the shell command argument limit', async () => {
    const commands = [];
    const ui = loadPanel(async command => {
        commands.push(command);
        if (Buffer.byteLength(command) > 120 * 1024) return {success: false, content: 'Argument list too long'};
        const output = command.includes('/.upload.XXXXXX') ? '/data/local/tmp/sing-box-ufi/.upload.abc123' : '';
        return {success: true, content: output + '\n__SBU_EXIT__0\n'};
    });
    await ui.open();
    const config = JSON.stringify({log: {level: 'info'}, comment: 'x'.repeat(220 * 1024)});
    ui.elements.get('[data-config]').value = config;
    await ui.click('save');
    assert.ok(!ui.elements.get('[data-output]').textContent.includes('Argument list too long'));
    assert.ok(commands.every(command => Buffer.byteLength(command) <= 120 * 1024));
    assert.ok(commands.some(command => command.includes('base64 -d') && command.includes('.upload.abc123')));
    // Check bytes crossing the Shell interface, not the private encoder implementation.
    const chunks = commands.filter(command => command.includes(' >> ')).map(command => {
        const unquoted = execFileSync('sh', ['-c', command.replace(/^sh -c /, 'printf %s ') .split(' 2>&1;')[0]], {encoding: 'utf8'});
        return unquoted.match(/printf '%s' '([A-Za-z0-9+/=]+)'/)[1];
    });
    assert.equal(Buffer.from(chunks.join(''), 'base64').toString('utf8'), config);
});

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
