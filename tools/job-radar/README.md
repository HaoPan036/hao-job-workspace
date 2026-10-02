# Optional Job Radar

岗位搜索可由宿主 Agent 使用搜索和浏览工具完成，也可先用 `collect.py` 从用户配置的来源采集线索，再由 Agent 核验官方岗位。前台工具只需 Python 3.10+ 标准库，不需要 AI API key、容器或后台服务：

- `collect.py`：显式前台采集、现有来源解析器、详情提取、SQLite 已见状态、来源健康和 Markdown 报告。结果使用同一份 `JobDossier`，核验为 `PENDING`，可行性、能力和战略为 `UNKNOWN`，建议为 `MANUAL_REVIEW`。
- `radar.py`：保留离线 dossier 去重、严格队列门和同步审计；不联网，也不自行判断输入评估是否真实。

完整发现步骤见 [discovery reference](../../.agents/skills/hao-job-workspace/references/discovery.md)。候选事实和用户匹配由 Agent 核验；本脚本不能从 `VERIFIED` 字符串判断证据是否真实。

## Foreground collection

先运行完全离线的虚构示例，不生成文件：

```bash
python3 tools/job-radar/collect.py --profile templates/job-search/profile.example.json --fixtures examples/discovery/sources.fixture.json --dry-run
```

预期 `collected_count=11`、`visible_count=11`、`queue_added=0`、`writes_enabled=false`。`--fixtures` 仅读取虚构响应并走同一套解析器和详情提取；这些结果不是有效招聘信息。[示例说明](../../examples/discovery/README.md) 列出数据和检查边界。

使用统一初始化生成的 `private/job-search/profile.json` 和 `sources.json`，或把 [空来源模板](../../templates/job-search/sources.example.json) 复制到获准的私人目录。模板是 `{"sources": []}`，没有启用任何来源。配置用户授权的具体来源后再执行：

```bash
python3 tools/job-radar/collect.py --profile private/job-search/profile.json --sources private/job-search/sources.json --dry-run
python3 tools/job-radar/collect.py --profile private/job-search/profile.json --sources private/job-search/sources.json
```

**`--sources` 是显式联网入口，`--dry-run` 只禁止持久化，不禁止联网。** dry-run 不创建目录、SQLite、health、报告、dossier 或日志，也不读取旧 seen 状态；它把本次候选都作为预览。无 `--dry-run` 时才保存采集产物。`--no-details` 跳过额外详情请求，结构化列表中已有 JD 仍保留；`--include-seen` 包含过去日期的已见候选。两种运行都不写 queue/history、不执行申请、不启动后台服务。

运行路径按 **profile 所在目录** 解析；仓库内输入配置和产物必须 ignored 且 untracked，用户选定的包外目录也可使用。输出不能覆盖输入，用户符号链接路径被拒绝，避免覆盖其指向的文件。默认产物：

```text
private/job-search/radar/seen_jobs.sqlite3
private/job-search/radar/source_health.json
private/job-search/radar/reports/YYYY-MM-DD_Job_Radar.md
private/job-search/radar/dossiers.json
```

SQLite 只保存已见岗位标识和首次/最近时间，不是 HTTP 内容缓存。同一自然日重跑仍显示首次发现的岗位，次日隐藏；旧 URL key 在再次遇到时迁移。日报与 `dossiers.json` 表示本次可见候选，重复运行会更新生成文件。源抓取失败按来源隔离：其他结果仍写出，报告保留异常并返回退出码 `2`；成功返回 `0`。来源健康的连续失败按自然日计数，同日重复失败不累加，成功清零。

来源使用原有 `sources` 列表，每项至少有 `name`、`type`、`url`；名称必须唯一，可选 `enabled`、`company`、`location`、`employment_type`、`priority`，以及 `require_location_any`、`require_title_any`、`require_title_all`、`require_any`。示例地址虚构，需替换为用户选定的实际端点：

```json
{
  "sources": [
    {
      "name": "My selected employer",
      "type": "greenhouse",
      "url": "https://careers.example.test/configured-jobs-endpoint",
      "company": "My selected employer",
      "employment_type": "Full Time",
      "enabled": true
    }
  ]
}
```

已迁入原 HTML、RSS/Atom、Ashby、Greenhouse、Lever、MyCareersFuture、Baidu 内嵌职位列表和 Sogou WeChat 结果解析器；`portal` 保留用户声明的入口，`manual` 跳过抓取。WeChat 使用原 `query` 字段构建 Sogou 搜索 URL，只产生线索。MCF 的地区字段来自其平台/来源配置，不代表用户具有申请资格。平台解析器只覆盖原响应格式，不包含登录、动态浏览器、分页或站点变化自适应；本轮未验证真实网站兼容性。

`collector` 对象配置产物路径、超时、详情请求数量及报告/详情召回分阈值。默认阈值为 `0`，空画像不施加地区、届次、工龄或角色限制；`target_roles` 等现有字段只影响召回分。`allowed_graduation_years`、`internship_excluded_locations`、`blocked_keywords` 等显式筛选结果只显示复核提示，不升级 dossier 判断。`detail_sections` 配置 JD/要求章节标题。

将 `radar/dossiers.json` 与对应 Markdown 报告交给 Agent，逐项核对官方状态、用户条件、能力证据和材料；完成判断后将评估结果另存为 `private/job-search/dossiers.json`，再进入下面的离线 helper 流程。这样下次采集不会覆盖已完成的评估。

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

写回前，Git 工作区内的 profile、candidate、queue 和 history 必须同时满足 ignored 和 untracked。离线 `radar.py` 不创建日报、数据库、日志或候选文件，不写已提交状态。保存前的重读可以发现常见并发修改，但不是文件锁或跨文件事务；不要让两个执行者同时写队列。

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

## Read-only funnel health

漏斗摘要使用现有 recruiting-sync 配置和同一份 queue/history，不需要另一套账本：

```bash
python3 tools/job-radar/funnel.py --root . --config private/recruiting/config.json --json
```

去掉 `--json` 可在终端查看 Markdown。命令只读 Git 工作区内 ignored 且 untracked 的配置与记录，不创建输出文件；`--root` 是用户实际工作区根目录，配置中的路径按它解析。

摘要保留原 Radar 的 P0/P1/P2、最近 7 天已记录的入队/转记录流量、入队超过 7 天、临期和过期项目。入队流量只取日期批次下的 disposition 批注，转记录只取 history 的 `Confirmed on` 列；后者不是实际提交日期。任务年龄来自 `Queued on` / `Added on` 字段或所属日期批次标题，`verified` 日期不替代入队日期。截止日期来自任务的 `Deadline` / `Apply by` / `截止` 等明确字段；只有日期时，临期沿用“今天到第三个后续自然日”的近似。

未记录的入队日期、截止日期、实际提交日期和缺少批注的近期批次单独报告，不推断缺失日期或转化率。标题和 history 表头沿用共享配置，未知表结构、冲突日期、重复/不一致的批次计数会报错。

## Checks

```bash
python3 -m unittest discover -s tools/job-radar/tests -v
```

测试仅创建临时虚构资料，不联网，不读取私人求职记录。覆盖八类来源和 RSS/Atom、详情、同日/次日已见状态、来源健康、dry-run 零写入、符号链接保护、共享漏斗摘要，以及原有两个用户、严格队列门、CRLF 保留和四结果审计。它们是本地复现检查，不代表真实网站验证或已有陌生用户跑通。
