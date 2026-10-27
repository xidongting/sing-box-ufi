// @ts-check
(() => {
    'use strict';
    const repository = '__REPOSITORY__';
    const pluginVersion = '__PLUGIN_VERSION__';
    const managerBase64 = '__MANAGER_BASE64__';
    const home = '/data/local/tmp/sing-box-ufi';
    let busy = false;
    /** @type {HTMLElement | null} */
    let panel = null;
    /** @param {string} text */
    const quote = text => "'" + text.replace(/'/g, "'\\''") + "'";
    /** @param {string} text */
    const encode = text => btoa(Array.from(new TextEncoder().encode(text), b => String.fromCharCode(b)).join(''));

    /** @param {string} command */
    async function shell(command) {
        const marker = '__SBU_EXIT__';
        const result = await runShellWithRoot(`sh -c ${quote(command)} 2>&1; printf '\\n${marker}%s\\n' "$?"`, 95000);
        if (!result.success) throw new Error(result.content);
        const match = result.content.match(/\n__SBU_EXIT__(\d+)\s*$/);
        if (!match) throw new Error('Shell 未返回退出状态；操作结果未知，请先刷新状态，勿重复提交。');
        const output = result.content.slice(0, match.index);
        if (match[1] !== '0') throw new Error(output || `Shell exit ${match[1]}`);
        return output;
    }
    async function setup() {
        // Install only our interface script; importing/opening the plugin never starts sing-box.
        await shell(`set -eu; umask 077; [ ! -L ${quote(home)} ]; mkdir -p ${quote(home)}; chmod 700 ${quote(home)}; t=$(mktemp ${quote(home + '/.manager.XXXXXX')}); trap 'rm -f "$t"' EXIT; printf '%s' ${quote(managerBase64)} | base64 -d > "$t"; chmod 700 "$t"; mv "$t" ${quote(home + '/manager.sh')}`);
    }
    /** @param {string[]} args */
    const command = (...args) => `sh ${quote(home + '/manager.sh')} ${args.map(quote).join(' ')}`;
    /** @param {string[]} args */
    const manager = (...args) => shell(command(...args));
    /** @param {string} selector */
    function element(selector) {
        const el = panel?.querySelector(selector);
        if (!(el instanceof HTMLElement)) throw new Error(`Missing UI element ${selector}`);
        return el;
    }
    const editor = () => /** @type {HTMLTextAreaElement} */ (element('[data-config]'));
    /** @param {() => Promise<void>} action */
    async function perform(action) {
        if (busy) return;
        busy = true;
        panel?.setAttribute('aria-busy', 'true');
        try { await action(); }
        catch (error) { element('[data-output]').textContent = error instanceof Error ? error.message : String(error); }
        finally { busy = false; panel?.removeAttribute('aria-busy'); }
    }
    /** @param {string} url */
    async function github(url) {
        const response = await fetch(url, { headers: { Accept: 'application/vnd.github+json' }, cache: 'no-store' });
        if (!response.ok) throw new Error(`GitHub HTTP ${response.status}`);
        return response.json();
    }
    async function listVersions() {
        const select = /** @type {HTMLSelectElement} */ (element('[data-version]'));
        select.replaceChildren();
        // Paginate so older installed versions remain selectable as alpha releases accumulate.
        for (let page = 1; ; page++) {
            const releases = await github(`https://api.github.com/repos/${repository}/releases?per_page=100&page=${page}`);
            for (const release of releases) {
                if (release.draft || !/^core-v\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$/.test(release.tag_name)) continue;
                const option = document.createElement('option');
                option.value = release.tag_name;
                option.textContent = `${release.tag_name.slice(5)}${release.prerelease ? ' (预发布)' : ' (稳定版)'}`;
                select.append(option);
            }
            if (releases.length < 100) break;
        }
        element('[data-output]').textContent = select.options.length ? '选择版本后手动安装。升级完成后不会启动。' : '此仓库尚无内核 Release。';
    }
    async function install() {
        const tag = /** @type {HTMLSelectElement} */ (element('[data-version]')).value;
        if (!/^core-v\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$/.test(tag)) throw new Error('请先选择版本');
        const abi = await shell('getprop ro.product.cpu.abilist; getprop ro.product.cpu.abi');
        const arch = abi.includes('arm64-v8a') ? 'arm64' : abi.includes('armeabi-v7a') ? 'arm' : null;
        if (!arch) throw new Error(`不支持的 Android ABI: ${abi}`);
        const release = await github(`https://api.github.com/repos/${repository}/releases/tags/${tag}`);
        const prefix = `https://github.com/${repository}/releases/download/${tag}/`;
        /** @param {string} name */
        const asset = name => {
            const item = release.assets.find(/** @param {{name: string, browser_download_url: string}} a */ a => a.name === name);
            if (!item || item.browser_download_url !== prefix + name) throw new Error(`缺少或无效产物 ${name}`);
            return item.browser_download_url;
        };
        // Fetch small manifests on-device: browser access to release assets is subject to CORS.
        const curl = 'c=$(command -v curl || true); [ -n "$c" ] || c=/data/data/com.minikano.f50_sms/files/curl; "$c" --fail --location --proto "=https" --proto-redir "=https" --connect-timeout 15 --max-time 25 ';
        const sums = await shell(curl + quote(asset(`SHA256SUMS-${arch}`)));
        const metadata = JSON.parse(await shell(curl + quote(asset(`build-${arch}.json`))));
        const sdk = Number((await shell('getprop ro.build.version.sdk')).trim());
        if (!Number.isInteger(sdk) || sdk <= 0 || !Number.isInteger(metadata.minimum_android_sdk) || sdk < metadata.minimum_android_sdk) {
            throw new Error(`系统 API ${sdk} 不满足此版本最低 API ${metadata.minimum_android_sdk}`);
        }
        const name = `sing-box-android-${arch}`;
        const checksum = sums.split('\n').map(line => line.trim().split(/\s+/)).find(parts => parts[1] === name)?.[0];
        if (!checksum || !/^[a-f0-9]{64}$/.test(checksum)) throw new Error('缺少有效 SHA-256');
        if (!confirm(`安装 ${tag.slice(5)} (${arch})？当前实例将停止，完成后需手动启动。配置和自启开关不变。`)) return;
        element('[data-output]').textContent = '下载并安装中，请勿重复操作…';
        element('[data-output]').textContent = await manager('download', asset(name), checksum);
        element('[data-status]').textContent = await manager('status');
    }
    function open() {
        if (panel?.isConnected) { showModal('#sing_box_ufi'); return; }
        const modal = createModal({ name: 'sing_box_ufi', title: `sing-box UFI ${pluginVersion}`, maxWidth: '850px',
            showConfirm: false, onClose: () => !busy,
            content: `<p>工作目录：${home}。插件不接管系统网络。内核仅手动安装、启动。</p>
<pre data-status aria-live="polite"></pre>
<div><button class="btn" data-action="env">环境检测</button> <button class="btn" data-action="status">刷新状态</button>
<button class="btn" data-action="start">启动</button> <button class="btn" data-action="stop">停止</button> <button class="btn" data-action="restart">重启</button></div>
<p><button class="btn" data-action="versions">加载内核版本</button> <label>内核版本 <select data-version></select></label> <button class="btn" data-action="install">安装 / 升级</button></p>
<p><button class="btn" data-action="autostart-on">开启自启</button> <button class="btn" data-action="autostart-off">关闭自启</button></p>
<label for="sbu-config">原生 config.json（保存不会重启）</label>
<textarea id="sbu-config" data-config spellcheck="false" style="width:100%;min-height:240px;font-family:monospace"></textarea>
<label>导入 JSON <input data-import type="file" accept=".json,application/json"></label>
<p><button class="btn" data-action="load">读取已保存配置</button> <button class="btn" data-action="save">校验并保存</button> <button class="btn" data-action="check">校验已保存配置</button> <button class="btn" data-action="logs">日志</button></p>
<p><button class="btn" data-action="uninstall">卸载内核</button></p>
<pre data-output role="status" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:300px;overflow:auto"></pre>` });
        if (!modal) throw new Error('UFI Tools 原生模态框不可用');
        panel = modal.el;
        panel.addEventListener('click', event => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const action = target.dataset.action;
            if (!action) return;
            void perform(async () => {
                if (action === 'versions') return listVersions();
                if (action === 'install') return install();
                if (action === 'load') {
                    if (editor().value && !confirm('覆盖编辑框中尚未保存的内容？')) return;
                    editor().value = await manager('config');
                    return;
                }
                if (action === 'save') {
                    if (new TextEncoder().encode(editor().value).length > 512 * 1024) throw new Error('首版编辑器限制 512 KiB；更大配置请通过终端管理');
                    element('[data-output]').textContent = await shell(`printf '%s' ${quote(encode(editor().value))} | base64 -d | ${command('save')}`);
                } else if (action === 'uninstall') {
                    if (!confirm('停止并卸载内核？配置默认保留。插件界面需在 UFI Tools 插件管理中另行删除。')) return;
                    const purge = confirm('是否同时删除 config.json？此操作不可撤销。取消则保留配置。');
                    element('[data-output]').textContent = await manager('uninstall', purge ? 'purge' : 'keep');
                } else if (action === 'autostart-on' || action === 'autostart-off') {
                    element('[data-output]').textContent = await manager('autostart', action.slice(10));
                } else if (['env', 'status', 'start', 'stop', 'restart', 'check', 'logs'].includes(action)) {
                    element('[data-output]').textContent = await manager(action);
                }
                element('[data-status]').textContent = await manager('status');
            });
        });
        element('[data-import]').addEventListener('change', event => {
            const input = /** @type {HTMLInputElement} */ (event.target);
            void perform(async () => {
                const file = input.files?.[0];
                if (!file) return;
                if (file.size > 512 * 1024) throw new Error('配置超过 512 KiB 编辑器限制');
                if (editor().value && !confirm('覆盖编辑框中尚未保存的内容？')) return;
                editor().value = await file.text();
            });
        });
        showModal(modal.id);
        void perform(async () => {
            await setup();
            element('[data-status]').textContent = await manager('status');
            editor().value = await manager('config');
        });
    }
    function mount() {
        if (document.getElementById('sing-box-ufi-button')) return;
        const anchor = document.getElementById('PLUGIN_SETTING');
        if (!anchor || typeof runShellWithRoot !== 'function' || typeof createModal !== 'function') return;
        const button = document.createElement('button');
        button.id = 'sing-box-ufi-button';
        button.className = 'btn';
        button.textContent = 'sing-box';
        button.addEventListener('click', open);
        anchor.insertAdjacentElement('afterend', button);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
    else mount();
})();
