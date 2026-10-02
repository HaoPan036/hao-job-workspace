# 可选的 macOS 后台服务

核心找岗和材料流程不依赖后台服务。本安装器只迁移本机 changedetection.io 服务与 bridge 的 LaunchAgent 配置；默认打印计划，只有 `install --apply` 才创建文件并调用 macOS 的 `launchctl bootstrap`。本轮仅完成模拟测试，没有启动服务、安装依赖或验收后台运行。

第三方 changedetection.io 的可用版本、安装方式和命令行兼容性仍待按其官方资料核对。这里不提供固定版本的安装命令，也不自动下载程序。计划沿用原安装器的 `-h`、`-d`、`-p` 启动参数及环境设置；实际使用前应核对用户选定版本，不能把计划生成成功当成兼容性证明。

## 先准备本地配置

沿用统一初始化生成的 `private/job-search/` 中的 `profile.json`、`sources.json` 与 `changedetection.json`，将 `installer.json` 保存在同一目录；不另复制一套找岗配置。安装配置、凭据与运行目录也必须 ignored 且 untracked。本地 LaunchAgent plist 通常位于自己的 `~/Library/LaunchAgents/`，不进入公开 Git。

将以下配置保存为本地 `installer.json`。路径相对这份文件；`server_executable` 必须替换为用户自行安装并核对过的可执行文件绝对路径。不要把 API key 写进此配置或 plist。

```json
{
  "components": ["server"],
  "label_prefix": "local.job-workspace.changedetection",
  "runtime_dir": "background",
  "base_url": "http://127.0.0.1:5000",
  "server_executable": "/absolute/path/to/changedetection.io",
  "bridge_config": "changedetection.json",
  "profile": "profile.json",
  "sources": "sources.json",
  "poll_interval_seconds": 300
}
```

- `components` 可选 `server`、`bridge` 或两者。首次可以只安装 server；确认本机服务与认证配置后，再以 `bridge` 安装另一份 plist。同名组件不会被重新加载或覆盖。
- `label_prefix` 决定两个标签的前缀，末尾分别添加 `.server` 与 `.bridge`。已有同名 plist、管理记录、日志目标、已加载标签，或 server 数据目录已存在时拒绝安装；不要指向其他服务或已有数据。
- `launch_agents_dir` 可显式指定，否则使用当前用户的 `~/Library/LaunchAgents/`。`python_executable` 默认当前 Python，可显式选择；`timezone` 未设置时不固定地区。
- `base_url` 必须是带端口的 `http://127.0.0.1`，与 bridge 配置相同。安装器只配置本机服务，不设置远端服务。
- `poll_interval_seconds` 是 bridge 定期轮询间隔，区别于 bridge 配置的 `check_interval_hours`（网页检查频率）。

bridge 配置从 [空模板](../../templates/job-search/changedetection.example.json) 开始，按 [bridge 说明](../../tools/job-radar/CHANGEDETECTION.md) 配置来源与输出。后台安装要求显式填写 `api_key_path`，指向同一 Git 工作区里 ignored、untracked、权限为 `0600` 的本地文件。凭据由用户通过所选服务的正常配置方式提供，必须与服务实际设置一致；安装器不读取服务 datastore，不获取或打印 token，也不把 shell 环境变量值复制进 plist。令 `api_key_env` 为空可让 bridge 只使用指定文件。

## 预览与显式安装

从仓库根目录运行；下面使用的是用户自己的本地配置：

```sh
python3 tools/job-radar/install_changedetection.py plan --config private/job-search/installer.json
```

省略 `plan`，或使用 `install` 但不带 `--apply`，同样只输出计划。`--dry-run` 始终禁止写入和服务调用，包括与 `install --apply` 同时出现的情况。预览会读取指定配置文件，但不读取凭据内容、不访问网络、不运行 `launchctl`。

检查计划中的路径、启动参数、端口与组件后，用户明确决定安装时才运行：

```sh
python3 tools/job-radar/install_changedetection.py install --config private/job-search/installer.json --apply
```

该动作仅适用于 macOS。安装器先检查文件与已加载标签冲突，再以 `0600` 独占创建 plist 和管理记录，并 bootstrap 新服务；不使用 shell，不执行 `bootout`、`enable` 或替换别人的任务。服务数据与日志保存在指定运行目录，凭据文件保持原样。

bridge LaunchAgent 的命令是 `poll --config … --profile … --sources … --apply`。安装器不会自动执行 `sync`、`baseline` 或删除 watch；来源同步和基线准备遵循 bridge 自身的显式动作流程。

## 完成状态与失败处理

成功结果中的 `bootstrapped_labels` 只表示 macOS 接受了加载命令，`service_readiness` 仍是 `NOT_CHECKED`。本安装器不声明服务已就绪、认证有效或网页监控成功。

`runtime_dir/manifests/` 记录安装器创建的 plist 路径与 SHA-256，仅证明文件归属，不证明任务当前运行。发生部分失败时保留这些文件、数据和凭据，按记录核对 macOS 的服务状态与日志；不要用重复安装覆盖或自动删除现场。需要停用、移除或更新时，由用户依据管理记录通过 macOS 的 LaunchAgent 管理方式处理自己的组件。本安装器不提供卸载、自动重载或数据清理。

离线回归使用临时 Git 仓库、虚构配置与被替换的服务调用：

```sh
python3 -m unittest discover -s tools/job-radar/tests -p test_install_changedetection.py -v
```

模拟检查涵盖默认无写入、显式动作、接口参数、同名冲突、已加载任务、Git 与 symlink 边界、凭据权限及部分失败保留；不代表 macOS 后台实机、第三方依赖或其他宿主已经通过验收。
