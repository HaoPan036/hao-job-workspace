# Optional Job Radar helper

岗位搜索的主路线是由宿主 Agent 使用搜索和浏览工具核验公司官方页面。这个无第三方依赖的 Python 3 工具仅迁移现有 Job Radar 的 dossier 字段、去重、队列门和同步审计。**它没有迁入整个 Radar 抓取器**，不联网、不运行后台服务，也不需要 changedetection、容器、数据库或 API key。

完整发现步骤见 [discovery reference](../../.agents/skills/hao-job-workspace/references/discovery.md)。候选事实和用户匹配由 Agent 核验；本脚本不能从 `VERIFIED` 字符串判断证据是否真实。

## Read-only example

从仓库根目录执行，仅读取公开虚构样例并打印计数：

```bash
python3 tools/job-radar/radar.py --profile templates/job-search/singapore-internship.profile.example.json --candidates templates/job-search/dossiers.example.json
```

默认 `standalone_review`，预期 `evaluated_count=2`、`unique_count=2`、`eligible_count=1`、`queue_added=0`、`writes_enabled=false`。新加坡实习因虚构用户的工作许可未知而人工复核；另一位虚构用户的加拿大岗位符合入队门。不存在地区性实习禁令。这不是实际求职建议或官方职位核验。

`--mode workspace_discovery` 本身也不写入；`standalone_review --write-queue` 会报错。评价文案或网页内“保存”字样不能启用写入。

## User configuration

把 [templates/job-search](../../templates/job-search/) 中需要的配置、覆盖和行动文件复制到忽略且未跟踪的 `private/job-search/`，或用户选择的包外目录。队列与申请历史共用 [recruiting 模板](../../templates/recruiting/) 对应的 `private/recruiting/queue.md` 和 `private/recruiting/history.md`，不建立第二份账本。已有记录时直接引用，不覆盖。保留公开模板；配置、队列、已申请历史、dossier 与 handoff 都是私人运行数据。不要把真实记录放入 tests、examples 或公开 Git。

- `target_roles`、`locations`、`target_companies`、`discovery_domain_hints` 是 Agent 的搜索范围；空数组表示未配置，不表示无限搜索授权。
- `allowed_graduation_years`、`internship_excluded_locations`、`feasibility` 记录用户已确认条件；空值保持未知。Agent 核对具体 JD 的 required/preferred/nice-to-have，脚本不推断匹配。
- 在用户资料索引中指定已有简历、事实和用户确认的叙事路径；每个 dossier 的 `application_route` 指向实际选择的材料。不要复制示例的履历到用户档案。
- `application_queue.path` 与 `application_history_path` 默认分别为 `../recruiting/queue.md` 和 `../recruiting/history.md`，以私人 profile 所在目录解析。必须引用申请同步也在用的同一份记录；缺少历史或缺少唯一有序 marker 时写入失败，不自行创建历史。
- `company_coverage`、`current_actions`、`dashboard` 指定同步审计需读的记录。
- 所有相对配置路径均以 **profile 文件所在目录** 为基准，与启动命令的工作目录无关。`--candidates` 和 `--validate-sync` 则是普通 CLI 输入路径。

有 [空白配置](../../templates/job-search/profile.example.json)、[虚构新加坡学生](../../templates/job-search/singapore-internship.profile.example.json) 和 [虚构加拿大开发者](../../templates/job-search/canada-full-time.profile.example.json) 三种起点。两个虚构用户只示范不同地区和履历条件；工作许可必须按真实用户当前事实核实。

## Authorized queue write

用户明确要求搜索并保存后，Agent 在私人副本中完成官方核验、去重、现有材料路由，准备 `JobDossier` 列表，并将 `application_queue.enabled` 设为 `true`。只改本轮明确授权的配置与记录。示例命令（须先准备文件）为：

```bash
python3 tools/job-radar/radar.py --profile private/job-search/profile.json --candidates private/job-search/dossiers.json --mode workspace_discovery --write-queue
```

队列门保留 `VERIFIED + PASS + APPLY_NOW/APPLY_BATCH`，且要求开放的具体岗位、核验/个人证据、独立匹配判断与可用 URL；可行性未知不能因高匹配被放行。`retrieval_score` 不决定申请优先级。`#p0`、`#p1` 只对应上述两个行动。

只追加共享 queue 的 `## Pending applications` 中的 `job-radar:auto` 标记区，并保留外部字节和换行形式；与待投和已申请记录中的规范化 URL 去重。已有记录的公司别名、不同 URL 同岗、requisition ID、届次等仍需 Agent 核对。相同标题但不同官方 Job ID 不会仅凭标题被工具合并。

URL 中的括号、非 ASCII 字符和空格统一到与 Markdown 写入相同的编码；已编码的路径分隔符和查询分隔符保持区分，有效查询参数的顺序及重复键也保留，避免把不同职位标识合并。

写回前，Git 工作区内的 profile、candidate、queue 和 history 必须同时满足 ignored 和 untracked。脚本不创建日报、数据库、日志或候选文件，不写已提交状态。保存前的重读可以发现常见并发修改，但不是文件锁或跨文件事务；不要让两个执行者同时写队列。

这一步仅负责满足队列门的新增项。Agent 仍需保存 `manual_review`、`excluded`、`duplicate` 指针，更新公司覆盖/当前行动，再核对完整批次。达到 `max_new_per_run` 的其他已评价项不能消失；继续处理或明确报告剩余写回未完成。

## Audit a completed batch

使用原有 handoff 字段：`mode`、`requested_writeback`、`evaluated_candidates`、`companies`，以及可选的 `batch_date` 和 `stale_markers`。[虚构示例](../../templates/job-search/handoff.example.json) 展示两个评价结果。岗位无官方 Job ID 时在 handoff 的 `job_id` 中使用其稳定官方岗位 URL，同一值写入对应记录，不能编造官方编号。

本轮 queue 日期标题后使用现有计数批注，例如：

```text
### 2026-10-01: Fictional batch

2 evaluated = 1 queued + 1 manual review + 0 excluded + 0 duplicate
```

```bash
python3 tools/job-radar/radar.py --profile private/job-search/profile.json --validate-sync private/job-search/handoff.json
```

审计只读：核对候选标识、四类计数、孤儿、重复 disposition、候选与申请历史冲突、公司覆盖及给定过期文字；通过返回 `0`，失败返回 `2`。公开模板是空白，直接把示例 handoff 对着空模板审计会失败，这是预期。审计只证明这些文本一致性，不证明职位仍开放、材料事实真实、某一行的语义正确或外部申请成功；Agent 必须逐项重读结果与官方证据。

## Checks

```bash
python3 -m unittest discover -s tools/job-radar/tests -v
```

测试仅创建临时虚构资料，不联网，不读取私人求职记录。覆盖两个用户、只读字节不变、严格门、去重、CRLF 保留、历史缺失、隐私写入检查和四结果审计。它们是本地复现检查，不代表已有陌生用户跑通。
