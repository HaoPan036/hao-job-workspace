# 实际提交材料归档

这是一个 Python 标准库工具：在某个具体申请已经有成功证据后，保存当次实际使用的 CV 字节和普通项目回答。相同 SHA256 的 CV 只保存一份，每次申请保留独立记录。工具不联网、不操作浏览器、不解析 PDF，也不改变申请状态。

调用前必须有用户明确确认投递成功，或在获准提交后观察到官方成功证据。准备中、只填不提交、提交结果不明的申请不能记作成功。脚本只校验成功证据字段的结构，无法证明引用足以说明成功，调用者必须先核对。

## 最小调用

从仓库根目录运行，先将根据实际已核对内容制作的输入存入被 Git 忽略的本地文件：

```sh
python3 tools/application-record/record.py --input private/application-record-input.json --validate-only
python3 tools/application-record/record.py --input private/application-record-input.json
```

`--root PATH` 可选择另一个本地 Git 仓库，默认当前工具所在的仓库根目录。相对 `--input` 路径相对执行时的当前目录；输入中的相对 CV 路径相对所选仓库根目录。输入 JSON 和归档路径必须位于该仓库、被 Git 忽略且未被跟踪。CV 由用户显式选择；它可以位于仓库外，真实 CV 不应加入 Git。

工具只读取指定 JSON、指定 CV 和本次所需的对象／记录文件，不扫描私有目录。实现使用 POSIX 目录描述符、`O_NOFOLLOW` 和原子硬链接，在 macOS/Linux 上使用；Windows 未验证。

## 输入格式

沿用现有归档格式 `schema_version: 1`。以下是**不可直接作为真实申请运行的虚构说明**；尖括号必须替换为已核对的值，不能把占位符当作成功证据：

```json
{
  "schema_version": 1,
  "record_id": "example-job001-20990106",
  "application": {
    "company": "Example Company (fictional)",
    "role": "Example Engineering Role (fictional)",
    "job_id": "EXAMPLE-JOB-001",
    "batch": null,
    "official_url": null,
    "submitted_on": null,
    "application_id": null
  },
  "resume": {
    "path": "<explicitly-selected-cv.pdf>",
    "route": "<approved-route>",
    "language": "en",
    "version": "<verified-version>",
    "expected_sha256": "<verified-64-character-sha256>"
  },
  "form_answers": [
    {"field": "Project description", "value": "<actual-confirmed-project-answer>"}
  ],
  "submission_evidence": [
    {"kind": "user_confirmation", "reference": "<success-confirmation-reference>", "observed_at": null}
  ],
  "jd": {"text": null, "source_url": null, "captured_at": null}
}
```

- `record_id` 只含英文字母、数字、下划线、连字符，首位为字母或数字，最长 128 字符。同次申请重跑保持同 ID；不知道提交日期时用稳定的本地编号，不编造日期。
- `job_id`、`batch`、`official_url` 至少有一个。`submitted_on` 是真实提交日，格式 `YYYY-MM-DD`；未知就保留 `null`。
- `resume.expected_sha256` 必填，来自此前核对的 CV 方向、语言和版本。临时对任意文件计算 Hash，不能代替此前版本核对。
- `form_answers` 仅保存当次真实填写并已确认的普通自由文本，如项目介绍；没有就用空数组。不保存密码、验证码、账号、身份资料、电话／地址备份、敏感声明或法律声明。字段名及常见秘密格式检查不能代替人工分类。
- `submission_evidence` 至少一项。`kind` 只允许 `official_confirmation` 或 `user_confirmation`；`reference` 是成功证据的非空索引，不放原始回执、登录链接或凭据。`observed_at` 为带时区 ISO 时间或 `null`。
- `jd` 可省略；存在时只含 `text`、`source_url`、`captured_at`。未知值为 `null`，时间必须带时区；工具不会抓取 URL。

## 写入与失败处理

输出固定保存在所选仓库的忽略目录：

```text
private/application-records/
  objects/<sha256>.pdf
  records/<record_id>.json
```

记录只保存相对对象路径，不保留原始 CV 机器路径。输入、CV 哈希、既有对象和目标忽略规则通过后才开始写入。文件通过原子操作创建，权限 `0600`；新目录权限 `0700`。每个文件的创建是原子的，整批文件不是跨文件事务。

同 ID 内容完全相同返回 `unchanged`，不重写；内容不同报冲突。既有对象损坏、历史对象缺失、输入或目标存在符号链接时拒绝操作并保留历史。写入中断可能留下可复用的 CV 对象；重跑同一输入即可，不会自动清理材料。`--validate-only` 使用同样校验，但不创建目录或文件。

成功输出 `status` 和相对 `record_path`；失败退出 2，错误仅说明类别，不回显申请内容。输入上限 10 MiB，CV 上限 50 MiB。归档成功不等于新的申请已经提交，也不能代替申请状态台账。

## 验证

```sh
python3 -m unittest discover -s tools/application-record/tests -v
```

测试仅使用临时 Git 仓库、虚构申请和明确标注的假 PDF 字节；不读取个人 CV，不生成真实申请记录，也不证明 PDF 视觉效果。
