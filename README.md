# sing-box-ufi

A native [UFI Tools](https://github.com/kanoqwq/UFI-TOOLS) interface for unmodified [sing-box](https://github.com/SagerNet/sing-box), with daily Android CLI builds from upstream releases.

Community project. Not affiliated with SagerNet or UFI Tools.

## Compatibility

Targets rooted **ZTE U30 Air and F50** running Android and **UFI Tools v4.1.5**. Neither device has been verified yet. Linux/OpenWrt firmware is outside this plugin's scope.

Builds target Android ARM64 and ARM. Installation checks the device ABI and the selected build's minimum Android API. Available binaries are listed under [Releases](https://github.com/xidongting/sing-box-ufi/releases); a published plugin does not guarantee that core builds are available.

## Install

1. Download [sing-box-ufi.js](https://github.com/xidongting/sing-box-ufi/releases/latest/download/sing-box-ufi.js).
2. Import it in **UFI Tools → Plugin Management**, save, and refresh the page.
3. Open **sing-box** in the toolbar. Check the environment, load available core versions, and install one.
4. Paste or import your native `config.json`, validate and save, then click **Start**.

Alternatively, add this URL as a custom plugin source:

```text
https://github.com/xidongting/sing-box-ufi/releases/latest/download/plugins.json
```

The plugin downloads and verifies the appropriate binary; no manual core copy is needed. Both your browser and device need access to GitHub. The device also needs HTTPS-capable `curl` and standard Android shell utilities.

## Behavior

- Plugin and core releases are independent. Core installation and upgrades are always manual.
- Upgrades preserve configuration and boot-start preferences, but **leave sing-box stopped**. Start it manually afterward.
- Configuration is checked with `sing-box check` before saving. Saving does not restart the process.
- No configuration migration, automatic rollback, subscription conversion, or crash-restart loop.
- Closing the page does not stop sing-box. Optional boot startup is disabled by default and uses UFI Tools' existing boot script.
- The plugin does **not** configure TProxy, TUN, firewall rules, routing, or DNS interception. Native sing-box configuration and device capabilities determine network behavior; installing this plugin does not automatically proxy hotspot clients.

Working directory: `/data/local/tmp/sing-box-ufi`. Place certificates and local rule sets there yourself. The editor accepts configurations up to 512 KiB; manage larger files through the terminal. Uninstall keeps `config.json` unless you explicitly confirm deletion.

## Builds

GitHub Actions checks daily at **03:23 UTC** for the latest stable and prerelease versions, including alpha, beta, and RC. Manual builds can target a supported official release tag.

Builds use the selected upstream version's Android CLI toolchain and flags. Releases include SHA-256 checksums, build metadata, corresponding source, and build scripts. Unknown upstream build layouts fail rather than silently guessing settings.

- `core-v*`: Android binaries; never triggers device auto-updates.
- `plugin-v*`: interface and plugin-source index; published separately.

See [Actions](https://github.com/xidongting/sing-box-ufi/actions) for build status.

## Development

```sh
npm ci --ignore-scripts
npm run check
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
sh -n device/manager.sh
```

Run tests on Linux for process-lifecycle coverage; macOS skips that test. Tests do not replace Android device verification.

Package the plugin locally:

```sh
python3 scripts/package-plugin.py --repo xidongting/sing-box-ufi
```

Output: `dist/plugin/`. Detailed [specification](docs/spec.md) and [self-review](docs/review.md) are available in Chinese.

## Security and limitations

This plugin runs with root privileges. Install only trusted binaries and configurations, keep the management interface private, and secure any proxy/API listeners you configure. UFI Tools may log shell commands containing configuration secrets; do not share full debug logs. SHA-256 checks detect corruption, not independent authenticity.

Logs rotate only on startup and can grow during long sessions. An interrupted management operation may leave `.lock` in the working directory; remove it only after confirming no operation is running.

## License

[GPL-3.0-or-later](LICENSE). Upstream sing-box and its dependencies retain their respective copyrights and license requirements.
