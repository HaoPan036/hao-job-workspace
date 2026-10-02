# 投递成功后的本地同步

把已经核实的单岗提交结果转为最小 Markdown 补丁。投递历史和待投清单仍是唯一状态来源；事件、计划和补丁只是执行材料。工具只访问本地文件，不联网、不操作浏览器、不提交申请，也不读取简历或档案。

本包使用 Python 3.10+ 和 Git。所有命令在仓库根目录运行，或传入 `--root <仓库根目录>`。

## 准备本地配置和空记录

将以下模板复制到对应的本地路径；已有文件应保留，不能用空模板覆盖：

| 模板 | 本地路径 |
|---|---|
| [config.example.json](../../templates/recruiting/config.example.json) | `private/recruiting/config.json` |
| [history.md](../../templates/recruiting/history.md) | `private/recruiting/history.md` |
| [queue.md](../../templates/recruiting/queue.md) | `private/recruiting/queue.md` |

配置和实时记录都必须处于同一 Git 仓库内、被忽略、未被跟踪。工具每次读取都检查这些条件，拒绝符号链接、越界和路径穿越。公开模板只能保存空记录或明确虚构的示例。

```sh
python3 tools/recruiting-sync/sync.py audit
```

初始输出应为 `AUDIT_PASS history_rows=0`。

配置使用 JSON，`schema_version` 为 `1`。`regions` 必填；`paths` 和 `markdown` 可省略以使用模板默认值：

- `paths.history`、`paths.queue`：仓库内相对路径，默认指向 `private/recruiting/`。
- `regions`：事件使用的地区键，以及该地区的 `label`、`aliases`。别名是字面文本，不是正则表达式。例如可把 `Toronto` 明确映射到 `canada`。
- `markdown.history_heading`、`queue_heading`、`counts_heading`：三个不同的二级节标题。
- `markdown.history_headers`、`count_headers`：八列历史表头与四列计数表头。可改显示文本，列含义和顺序保持模板定义。
- `markdown.employment_labels`：`full_time`、`internship` 的显示名。
- `markdown.total_labels`：`full_time`、`all` 的汇总显示名。
- `markdown.unknown_date`：未知投递日期和缺少链接时的显示文本。

每个地区都有全职与实习两类，类别行名为 `地区 label / 性质显示名`，新加坡实习同样支持。调整地区或显示名后，同步调整本地 Markdown 类别行和表头，再运行 `audit`。配置变化使旧计划失效。

使用者在历史表设置目标数，工具不替使用者决定目标。未设置的目标和剩余都写 `—`；已设置目标必须是非负整数。合计目标仅在所有成员类别都有数值时使用它们的和，否则也写 `—`。

## 同步流程

从已获成功证据的 `application_execution` 交接中提取准确岗位，不重新提交申请。真实事件放入忽略目录，例如 `private/recruiting/event.json`。

```sh
python3 tools/recruiting-sync/sync.py plan --input private/recruiting/event.json --out private/recruiting/plan-001
python3 tools/recruiting-sync/sync.py check --plan private/recruiting/plan-001/plan.json
```

1. `plan` 验证事件、身份、表格与计数，生成 `plan.json` 和 `changes.patch`，不修改台账。
2. 阅读补丁，确认只涉及准确岗位。每次用新计划目录，避免覆盖原计划。
3. 紧接应用前运行 `check`，检查配置、台账和补丁指纹；过期时从当前文件重新计划。
4. 在仓库根目录通过 Agent 的 `apply_patch` 工具应用 `changes.patch`。这是工具格式的补丁，不是 `git apply` 格式；脚本没有自动应用命令。
5. 应用后立即验证，随后才编辑其他说明：

```sh
python3 tools/recruiting-sync/sync.py verify --plan private/recruiting/plan-001/plan.json
python3 tools/recruiting-sync/sync.py audit
```

`verify` 检查最终快照、历史目标唯一、目标不再待投、分类与计数一致。`audit` 是只读检查，发现格式或计数问题返回非零退出码，不创建统计库或仪表板。

所有子命令支持 `--config <本地配置路径>`，默认 `private/recruiting/config.json`。同一计划的各步骤使用同一配置；即使只改别名，配置指纹变化也要求重建计划。

`review_locations` 只列出两份台账内可能受影响的日期和自然语言摘要位置。其他行动页由调用工作流按既有范围维护，工具不猜测位置或自动替换摘要。

## 事件与成功证据

两个完整的虚构事件可用于独立演练：

- [示例用户 A：Singapore internship](../../templates/recruiting/event-singapore-internship.example.json)
- [示例用户 B：Canada full time](../../templates/recruiting/event-canada-full-time.example.json)

演练时复制到独立临时仓库的 `private/recruiting/`，不要把示例成功记录写入真实台账。

事件保留 `schema_version`、`application_execution`、`sync`。`application_execution` 保留 `target`、`outcome`、`result_timestamp`、`application_id`、`submission_evidence`；`sync` 是展示和计数参数，不是另一个申请状态。

- 只接受 `outcome: "success_proven"`，且至少一项 `official_confirmation` 或 `user_confirmation`。字段校验不能证明声明真实。
- `target.job_id`、`target.official_url` 至少一个非空；公司与完整编号或准确链接用于匹配。仅对已核实属于同一投递单元的身份填写 `aliases`。
- 未知提交日、结果时间、申请编号和材料编号使用 `null`，不能用确认日填补提交日。非空时间戳必须含时区。
- `sync.region` 必须是配置地区键；`employment_type` 保留 `full_time` / `internship`。`location` 必须通过配置别名明确归类，不能从候选人的居住地推断。
- `status`、`note` 只保存有依据的状态和必要说明，不放账号、密码、验证码、联系方式、敏感声明、原始回执或认证链接。
- `material_record_id` 不证明归档成功。归档失败应单独重试归档，不撤销提交事实，不重新投递。

## Markdown 契约

历史表按固定含义使用八列：确认日、实际投递日、公司、岗位、地区与性质、当前状态、官方链接、备注。工具不重排历史，不改已有申请的日期、状态或说明。

待投条目沿用现有格式：

```markdown
- [ ] #p1 **Fictional Aurora Labs｜Software Engineering Intern** · [Official job](https://careers.example.com/jobs/DEMO-SG-001)
  - Details belonging to this exact task.
```

支持 `#p0`、`#p1`、`#p2` 和全角 `｜` 或 `|` 分隔符。只移除准确匹配的顶层任务及缩进子项；空行后的无缩进说明、其他任务、表格与后续节保留。子项也支持 `Official job:` / `Official URL:` / `Job link:` 及原有中文链接标签。备注中其他岗位的编号不自动成为本行身份。

性质兼容明确的 `Full Time`、`Full-Time`、`Permanent`、`Graduate`、`Internship`、中文全职与实习及配置标签。`Contract`、`Early Careers` 等模糊文本不推断为全职。地区别名按完整词匹配；多个地区或性质冲突时停止。括号内备选地区沿用原规则，仅以括号前明确选定地点为准。

## 重复事件和中断恢复

| 当前情况 | 下一步 |
|---|---|
| 没有成功结果 | 拒绝成功补丁，继续核实原申请结果 |
| 历史没有目标、队列有目标 | 新增一次历史，移除准确任务并重算 |
| 历史已有目标、队列尚未移除 | 保留历史，只补队列与必要汇总 |
| 历史有目标、队列已无目标 | 不新增，不重复计数 |
| 历史行已新增、汇总未更新 | `strict` 根据当前明细重计划、补齐记录 |
| 多个身份候选或已有事实冲突 | 停止，核实投递单元后处理 |
| 材料归档失败 | 保留提交事实，独立重试归档 |

已有记录缺少部分分类时，可以明确选用原有基线模式：

```sh
python3 tools/recruiting-sync/sync.py plan --input private/recruiting/event.json --out private/recruiting/plan-002 --counts-mode preserve_existing_counts
```

它仅在现有汇总算术、明细行数和可识别分类一致时保留基线，对本次新增历史行加一。已有历史不加一，明确类别冲突仍停止。结果标记 `LEGACY_WARNING`，不能称为全表分类已核实。

基线模式下若历史已新增而汇总未增加，必须按原计划和当前文件补齐遗漏或人工对账后验证。不能盲目重跑、回滚提交事实或重新点击 Submit。

快照检查与实际应用间仍存在并发窗口。`apply_patch` 不是跨文件事务；工具不提供原子提交、自动回滚或互斥锁。遇到计划外改动，保留当前内容并重新计划或定点补余。

## 开发验证

```sh
python3 -m unittest discover -s tools/recruiting-sync/tests -v
python3 tools/repo-check/check.py
```

测试使用临时仓库、虚构岗位和示例域名，覆盖两位示例用户、成功条件、身份匹配、重复事件、局部恢复、并发快照、配置与忽略边界。日常每次投递只需对应的计划、检查和对账。

这些检查证明本地结构与计数一致，不能程序证明浏览器提交成功、证据真实性、工作许可、材料真实性、摘要语义完整性、远端发布或陌生用户独立跑通。
