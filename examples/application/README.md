# 本机模拟投递演练

这是一份浏览器工作流验证夹具，不是生产网申产品。它只接受一个固定的虚构岗位、虚构申请人和生成的 PDF，不连接雇主系统，不创建真实申请。所有运行状态、上传字节、同步输入与材料归档都保存在新建演练仓库的 ignored `private/`。

需要 Python 3.10+、Git 和 macOS/Linux。网站只绑定 `127.0.0.1`，拒绝其他 Host 和外部 Origin；不提供账号、条款、敏感声明或邮件功能。纯 Python 标准库运行，无第三方网站依赖。

## 1. 初始化全新目录

从本包根目录运行，下面路径必须尚不存在；存在时会报错，不覆盖个人资料：

```sh
python3 examples/application/mock_site.py setup --root /tmp/job-workspace-demo
```

`setup` 明确白名单复制三个工具实现（profile、record、recruiting-sync），八个 profile JSON 模板，以及 recruiting 的 config、history、queue 模板。它初始化独立 Git 仓库和 `**/private/` 忽略规则，生成一页有效的虚构 PDF，并在 stdout 输出绝对路径、实际 SHA256、字段全文和岗位。不会读取个人档案或导入私有历史。

生成内容包括：

- `private/demo-resume.pdf`：仅供演练的上传文件。
- `private/state.json`：原始 mock 状态，包含草稿和 `submit_count`；只服务此测试，不是新的生产协议。
- `private/application-profile/`：空白 profile 模板副本，没有具体岗位授权。
- `private/recruiting/`：虚构待投岗位、空投递历史和同步配置。

## 2. 启动后填写

在一个终端中运行，结束时按 Ctrl+C：

```sh
python3 examples/application/mock_site.py serve --root /tmp/job-workspace-demo --port 8765
```

浏览器打开 [本机模拟页](http://127.0.0.1:8765)。在当前任务获准演练这个具体虚构岗位后，填写下列精确值，选择 setup 生成的 `demo-resume.pdf`，点击 **Save draft for review**。

| 字段 | 精确值 |
| --- | --- |
| Company | Fictional Aurora Labs |
| Role | Software Engineering Intern |
| Job ID | DEMO-SG-001 |
| Name | Example Candidate |
| Email | example@example.invalid |
| Resume PDF | setup 输出的 `private/demo-resume.pdf` |

Project answer：

```text
Implemented retry and stop rules for a fictional exercise. The first execution timed out, one retry also timed out, and the program stopped. The root cause remains unknown; no performance improvement is claimed.
```

回答和 PDF 的职责、结果范围来自[虚构超时来源](../timeout/source.md)：实现重试和停止规则，两次执行仍超时后停止；没有解决超时或改善性能的证据。网站拒绝其他字段、其他值、其他文件名及不同 PDF 字节，不能用于真实个人资料。

## 3. 独立审查与一次提交

保存后进入 `/review`。独立审查者从该页面重新读取姓名、邮箱、项目回答、实际上传文件名及 SHA256，并打开 **Read uploaded PDF** 核对附件。核对岗位和原始虚构事实，确认与 setup 输出的文件及哈希一致。

获准岗位按工作流完成独立审查，得到 `REVIEW_PASS` 后，由指定提交者点击一次 **Submit once**；主执行者此时不改表单。夹具本身不验证谁是审查者，也不把打开 review 页当作独立审查证明。实际浏览器工具的动作确认要求照常适用。

成功模式跳转 `/result`，显示岗位、`Application submitted successfully (synthetic)`、`SYNTHETIC-001` 和 `submit_count: 1`。这些只是模拟页面证据，不能证明任何真实雇主收到申请。再次提交返回 409，计数和结果不变。

## 4. 成功后同步与归档

仅在成功页已经得到实际浏览器核对后运行：

```sh
python3 examples/application/mock_site.py reconcile --root /tmp/job-workspace-demo
```

命令要求 mock 状态为 success、`submit_count = 1`，且所有字段和上传字节仍与固定夹具一致。它生成既有格式的 `private/mock-execution.json` 和 `private/mock-record-input.json`，调用 recruiting-sync `plan`／`check`，再调用 application-record。结果中的 `official_confirmation` 只作为现有协议的模拟测试值；证据引用明确标注 synthetic，不代表真实官方回执。

输出包括：

- `private/mock-plan/changes.patch` 和 `plan.json`：针对虚构 history、queue 的可审阅补丁，**尚未应用**。
- `private/application-records/records/synthetic-demo-sg-001.json`：实际模拟上传的材料记录；CV 对象按 SHA256 保存。

让执行 Agent 审阅并在演练根目录用 `apply_patch` 应用该补丁，再验证：

```sh
python3 /tmp/job-workspace-demo/tools/recruiting-sync/sync.py verify --root /tmp/job-workspace-demo --plan private/mock-plan/plan.json
python3 /tmp/job-workspace-demo/tools/recruiting-sync/sync.py audit --root /tmp/job-workspace-demo
```

预期是 `VERIFY_PASS`、`AUDIT_PASS`，待投条目已移除，Singapore / Internship 和 All submitted 各增加 1。补丁应用前重跑 reconcile 会复用计划并返回归档 `unchanged`；应用后直接使用 `verify`，不要重跑旧计划的 `check`。任何本地同步失败都只修复本地记录，不能再点击 Submit。

## 5. 不明确结果分支

在另一个全新目录初始化后，用另一个端口运行：

```sh
python3 examples/application/mock_site.py setup --root /tmp/job-workspace-ambiguous --mode ambiguous
python3 examples/application/mock_site.py serve --root /tmp/job-workspace-ambiguous --port 8766
```

照常填写、审查并点击一次 Submit。结果页显示 `Submission outcome unknown`，没有成功编号，`submit_count` 保持 1。不得盲目重试；重复提交被拒绝。此时 reconcile 会失败，不生成成功事件或材料归档。

## 自动检查与范围

```sh
python3 -m unittest discover -s examples/application/tests -v
```

测试在临时 Git 仓库和临时 loopback 端口验证草稿回读、输入限制、PDF 结构、只读页面无写入、重复提交、未知结果拒绝、同步计划和归档幂等。自动检查不是浏览器独立审查，也不是陌生使用者验收；实际浏览器演练应另行记录结果。
