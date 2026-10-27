# sing-box-ufi

官方 sing-box 源码构建 + UFI Tools 原生管理插件。**社区项目，非 SagerNet 或 UFI Tools 官方发行。**

插件是 interface，内核是未经修改的 sing-box。无额外 Web 服务、订阅转换、TProxy/防火墙/DNS/路由接管。网络行为由你提供的原生配置及设备系统能力决定；安装后不会自动代理整个热点。

## 当前状态

公开仓库：[xidongting/sing-box-ufi](https://github.com/xidongting/sing-box-ufi)。插件 v0.1.0 已发布，远程 Checks 与插件发布工作流通过；首次内核构建正在验证，设备尚未实测。内核是否可下载以 [Releases](https://github.com/xidongting/sing-box-ufi/releases) 为准。

| 目标 | 状态 |
| --- | --- |
| 已 Root 的 Android U30 Air + UFI Tools v4.1.5 | 目标环境，未实测 |
| 已 Root 的 Android F50 + UFI Tools v4.1.5 | 兼容目标，未实测；不是首版验收门槛 |
| 刷入 Linux / OpenWrt 的设备 | 不在插件适配范围 |

构建 Android `arm64` 和 `arm` CLI，按 Android ABI 选择，不仅依据 CPU 型号。最低 Android API 从对应上游编译目标读取，不满足就明确拒绝安装。新版本可能停止支持旧 Android；不要把同型号的不同固件视为等价。

## 使用

设备首次使用：下载 [sing-box-ufi.js](https://github.com/xidongting/sing-box-ufi/releases/latest/download/sing-box-ufi.js)，按下述步骤在 UFI Tools 导入。不要把 GitHub 的 Source code ZIP 当成插件，也不用把内核手动复制到设备。

本地生成绑定该仓库的插件（维护者使用）：

```sh
python3 scripts/package-plugin.py --repo xidongting/sing-box-ufi
```

1. UFI Tools 插件管理中导入 `dist/plugin/sing-box-ufi.js`，保存并刷新页面。
2. 原生工具栏会出现 **sing-box** 按钮。第一次打开仅安装管理脚本，不安装或启动内核。
3. 环境检测，加载内核版本，手动选择稳定版或 alpha/beta/RC 安装。
4. 粘贴或导入自己的 `config.json`，校验并保存，再手动启动。
5. 开机自启默认关闭，按需启用。

发布插件后可添加原生插件源：

```text
https://github.com/xidongting/sing-box-ufi/releases/latest/download/plugins.json
```

插件 Release 被设为 latest；内核 Release 不占用 latest。内核升级不要求重装插件。GitHub API/Release 在浏览器和设备均需可达；浏览器只访问 API，资产通过设备 curl 下载，以避开 Release 跨域限制。不使用公共下载代理或要求填写 GitHub 凭证。未认证 API 可能限流。

### 行为约定

- 单实例，独立于页面运行；异常退出不自动重启。
- 保存前执行 `sing-box check`，失败不覆盖；成功保存不重启。
- 升级只由用户点击触发。下载和 SHA-256 校验完成后停止旧实例、替换内核，**始终保持停止**；不按旧状态恢复。
- 升级不检查现有配置能否被新版本接受，不迁移配置，不自动回滚。不兼容时由下一次手动启动报告原始错误。
- 升级保留配置及开机自启偏好；设备下次启动仍按该偏好运行。
- 可选择已发布旧版重新安装，但没有自动回退槽位。
- 卸载移除内核、自启入口、运行日志；config.json 默认保留，删除需二次确认。管理脚本留作重装入口；UI 插件需在 UFI Tools 插件管理中删除，二者是不同操作。

### 文件与权限

固定工作目录：`/data/local/tmp/sing-box-ufi`，权限 `0700`，文件默认仅所有者可读写。

```text
manager.sh       管理命令（随插件更新）
sing-box         当前内核
config.json      用户原生配置（不会自动生成）
sing-box.log     当前标准输出/错误
sing-box.log.old 上次启动时轮转的日志（若超过 4 MiB）
sing-box.pid     单实例进程标识
```

相对证书/本地规则集路径相对于此工作目录；自行用终端上传。远程规则集由 sing-box 原生处理。编辑器暂限 512 KiB；更大配置通过终端管理。调用示例：

```sh
sh /data/local/tmp/sing-box-ufi/manager.sh status
sh /data/local/tmp/sing-box-ufi/manager.sh start
sh /data/local/tmp/sing-box-ufi/manager.sh stop
```

自启使用 UFI Tools 已有 `/sdcard/ufi_tools_boot.sh`，仅增删带 `# sing-box-ufi` 标记的一行，保留其他脚本。不安装 Magisk 模块，不修改系统分区。该入口是否在具体固件上执行仍需实测。

Shell 需要 `base64`、`sha256sum`、`mktemp`、`nohup`、`readlink` 及 `/proc`，下载需要 HTTPS curl（优先 PATH，回退 UFI Tools files/curl）。设备单次下载超时 65 秒，以适配 UFI Tools Shell 最长 100 秒的接口；慢速网络可失败并重试，不会先停止旧实例。

**安全提示：** 配置可能包含密钥，root_shell 会经过 UFI Tools，部分版本会记录命令。不要共享后台或完整调试日志。不要公开管理端口；为你配置的代理监听及 API 设置认证与访问限制。SHA-256 检测下载损坏，不等于独立签名。此插件以 Root 权限运行，只安装你信任的插件/内核与配置。

日志只在手动启动时轮转；长时间高日志量可能占满存储。建议自行在原生配置中设置合适日志级别。被强制终止的管理操作可能留下 `.lock`；确认无管理操作运行后再手动删除，禁止在下载/保存时删除。

## 自动构建与发布

- `core.yml`：UTC 03:23 每天检查一次最新稳定版和最新预发布版，各渠道有新版本才构建；支持手动指定官方已发布 tag。每日检查会跳过同一天已被更新版本取代的中间版本，按需手动补构建。
- 按版本号选取各渠道最新版本，不依赖 GitHub API 的返回顺序。读取对应 tag 官方 Android CLI workflow、Go 版本、NDK 固定版本、默认功能标签、完整链接参数。未知编译参数或目标选项会失败，人工更新适配器，不静默猜参数。
- ARM64/ARM 构建成功后才发布完整 Release；失败产物不会作为可安装 Release 出现。
- `core-vX.Y.Z…`：内核 Release。包含原始二进制、分架构 SHA-256、源码 commit 与构建信息、上游许可证，以及含 vendor 依赖的对应源码包、此次构建使用的仓库脚本快照。
- `plugin-vX.Y.Z`：插件独立 Release。先改 `package.json` 及 lockfile 版本，再创建对应 tag；也可手动运行 workflow。已公开 Release 不自动覆盖。
- GitHub 定时任务只在默认分支运行，执行可能延迟；长期无活动的公共仓库可能被 GitHub 暂停 schedule。

公开仓库已启用工作流。设备不会随 Release 自动升级；仍须在插件里选择版本并点击安装。

## 本地检查

```sh
npm ci --ignore-scripts
npm run check                          # JS 语法、TypeScript checkJs、原生插件加载检查
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
sh -n device/manager.sh
```

macOS 会跳过依赖 Linux `/proc` 的进程测试。完整轻量测试可用 Linux 容器：

```sh
docker run --rm -v "$PWD:/work" -w /work python:3.12-bookworm \
  sh -c 'pip install -r requirements-dev.txt && python -m unittest discover -s tests -v'
docker run --rm -v "$PWD:/work" -w /work koalaman/shellcheck:stable \
  -s sh device/manager.sh
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.11 -shellcheck=''
```

测试只覆盖管理命令与发布产物接口；C 测试进程只模拟 CLI 生命周期，不能证明真实 sing-box 网络功能或 Android 兼容性。无大型浏览器测试体系。`scripts/build-settings.py` 在 CI 使用 PyYAML 6.0.2；运行时无此依赖。

## 待实机验证

只需 U30 Air：记录 Android/API/ABI，安装、导入原生配置、实际 HTTP/SOCKS 连接、启停、升级后停止、启用自启后重启验证。F50 不作为首版门槛，未经验证不标记兼容已确认。不包含 Root、刷机、固件能力补齐。

确认规格见 [docs/spec.md](docs/spec.md)。

## 许可证与上游

本仓库采用 GPL-3.0-or-later。sing-box 的版权归原作者，构建时同时分发对应许可证及源码。发布者应审查上游第三方依赖通知及再分发要求。

- [SagerNet/sing-box](https://github.com/SagerNet/sing-box)
- [kanoqwq/UFI-TOOLS](https://github.com/kanoqwq/UFI-TOOLS)
