# 可选的 changedetection 桥接

这份桥接把已配置的招聘来源登记为 changedetection.io watch；观察到已登记 watch 的变化后，调用公开版 `collect.py` 重新采集。它迁自现有 Radar 的同步、基线、变化触发与失败重试流程。只有本地 mock 测试；未安装服务、未验证真实 changedetection API，也没有替你部署定时任务。

## 配置

先使用现有初始化建立个人 profile 和 sources。然后从仓库根目录复制桥接模板，已有文件不覆盖：

```sh
cp -n templates/job-search/changedetection.example.json private/job-search/changedetection.json
```

配置、profile、sources、状态、健康记录和可选 token 文件都必须位于 Git 仓库内、被忽略且未跟踪；拒绝符号链接。状态路径相对于桥接配置文件；collector 路径相对于显式 profile。桥接复用 profile 的 `collector.source_health_path`，不新建一份求职状态台账。

默认服务地址是 `http://127.0.0.1:5000`。其他 loopback 地址也可；远端必须明确设 `allow_remote: true` 并使用 HTTPS。服务地址不能包含用户名、密码、查询参数或路径。桥接不安装或启动服务，也不读取服务 datastore 或继承其中的 API key。

token 通过配置中明确命名的环境变量（默认 `CHANGEDETECTION_API_KEY`），或 `api_key_path` 指定的 ignored、untracked 文件读取；文件路径相对于桥接配置。环境变量非空时优先，否则读指定文件。不要把 token 放进公开 JSON、命令行参数、日志或聊天。缺少已配置 token 会阻止 API 调用；只有自己的服务明确关闭 API 认证时才将两种配置都设为空。预览不读取 token 内容。

`source_types` 与 `excluded_source_names` 控制哪些已有来源参与 watch。disabled、manual、portal、wechat_search 及需要登录的飞书表格不会自动登记。来源为空时不创建 watch。`check_interval_hours` 设置 watch 的服务端检查频率，不是本机 poll 调度周期。

## 离线预览

```sh
python3 tools/job-radar/changedetection_bridge.py preview \
  --config private/job-search/changedetection.json \
  --profile private/job-search/profile.json \
  --sources private/job-search/sources.json
```

输出期望 watch、已登记数量和待核对创建数。它仅读本地配置和状态，不访问 API、不调用采集器、不写文件；无法证明远端当前状态。所有命令省略 `--apply`，或添加 `--dry-run`，都采用同样的离线预览。桥接的 dry-run 与 collector 不同：collector 的 `--sources --dry-run` 仍可能联网。

## 明确执行

只有用户授权了对应服务和来源的监控后，才执行这些命令；使用模板或安装 Skill 不产生授权。下面每次显式指定全部路径：

```sh
python3 tools/job-radar/changedetection_bridge.py sync --apply \
  --config private/job-search/changedetection.json \
  --profile private/job-search/profile.json \
  --sources private/job-search/sources.json
```

把 `sync` 换成需要的命令：

| 命令 | 实际作用 |
|---|---|
| `sync --apply` | 读取 watch 清单、创建期望 watch、更新已登记 watch 的差异、删除已移出来源的已登记 watch；保存本地登记与健康状态。 |
| `baseline --apply` | 读取已登记 watch 的变化时间并保存新基线，不调用 collector；会明确放弃从旧基线到当前的待处理变化。 |
| `poll --apply` | 读取变化；首次观察只建基线，以后变化才调用 collector，成功后推进时间。 |
| `run --apply` | 立即用显式 profile、sources 调用 collector 并记录运行结果，不访问 changedetection API。 |

桥接只认领由本地状态登记的创建返回 UUID，并核对服务地址和 URL；标题前缀相同也不会认领他人的 watch。不会删除默认示例或清空整个服务。不要复用维护者的状态文件；不要让多个 bridge 同时写同一状态和健康文件。

collector 只更新配置中的采集 SQLite、来源健康、报告及候选 dossier，不写 queue/history，不投递申请。新候选仍需官方核验和个人条件判断，再按明确保存授权走现有发现流程。监控并不授权自动填表、消息发送或申请。

## 失败与恢复

- collector 退出非零时保留旧 `last_changed`，下次 poll 重试；部分来源结果可能已保存。`source_health.json` 的 `bridge.consecutive_failures` 累加失败，成功后归零。桥接不会回显子进程原文或服务响应正文，避免日志带出敏感数据。
- POST 创建前先保存 `pending_creates`。超时、响应缺少可用 UUID 或后续本地登记失败时，不盲目再创建；后续同步停止并保留待核对状态。用户应先在自己的服务核对该 URL 是否创建成功，再修复本地登记与 pending 项。不能仅凭标题认领其他 watch，不能清空状态后重跑当作恢复。
- DELETE 超时后仍保留登记。再次同步先读服务清单：远端已不存在时清理该登记，否则重试删除同一个已登记 watch。已登记 URL 被外部改动、或配置换了服务时暂停，保留状态核对。
- 状态、健康文件与服务 API 不构成跨系统事务；分别报告服务操作与本地保存的结果。认证错误和其他失败只报告类别，不输出 token、完整请求 URL或响应正文。

可选的后台安装流程见[本机后台服务说明](../../docs/experimental/background-service.md)；安装需要单独明确请求，桥接不会自行部署。

## 离线检查

```sh
python3 -m unittest discover -s tools/job-radar/tests -p 'test_changedetection_bridge.py' -v
```

测试使用临时 Git 仓库、虚构来源和 mock API/collector，覆盖离线预览、路径与 token 边界、只管理已登记 watch、基线、失败重试和错误输出。通过这些测试不代表已验证真实服务或网站兼容性。
