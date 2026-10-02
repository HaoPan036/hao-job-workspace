# Hao Job Workspace · 求职工作台

用自己的项目资料核对事实、修改中英文简历、准备和练习面试。Obsidian 用来阅读与编辑资料，Codex 桌面应用在同一文件夹中执行任务。

> 原始记录：首次执行超时，重试后仍超时，按策略停止。
>
> AI 草稿：解决了性能问题。
>
> 来源复核：Agent 指出改善结论缺少依据，修订为“实现有限重试和停止规则，在两次尝试均超时后停止本轮执行”。

这是[虚构案例](examples/timeout/source.md)中的来源对照，职责也须有单独依据；不是程序自动判断简历真伪。

本项目独立维护，只提供通用工作流、工具和虚构示例。如果你已有求职资料，可以保留原件，只向 Agent 提供本次需要的部分；仅导入资料不会自动修改原件，保存或修订按你明确指定的范围进行。

首批提供资料索引模板、一个独立 Skill 和虚构贯通练习。找岗位、网页投递、材料归档与同步仍在后续迁移范围；当前版本尚未经过陌生用户验收。进度见 [ROADMAP](ROADMAP.md)。

## 现在可以做什么

| 任务 | 请求示例 |
| --- | --- |
| 事实核对 | “核对这个项目中的个人职责与结果，保留没有依据的问题。” |
| 简历编辑 | “按这份 JD 修改指定段落，给出等义中英文版本和事实引用。” |
| 面试准备 | “基于已有项目资料写回答、准备追问，列出需要补学的技术。” |
| 复盘与陪练 | “解释我这段回答的问题，给出修订稿，然后一次问我一个问题。” |

事实状态、指标口径与冲突处理见 [事实规则](.agents/skills/hao-job-workspace/references/evidence.md)。未核实内容不进入正式简历或面试回答；已核实内容仍受用途与范围限制。这些是 Agent 的工作规则，检查器不能全面验证自然语言是否符合事实。

## 从虚构资料开始

维护者已在 **macOS** 验证仓库检查与材料 Agent 演练，其他系统未验证。账号能否使用 Codex 和后续浏览器控制，取决于套餐、地区与组织权限，以[官方说明](https://learn.chatgpt.com/docs/pricing)和账号实际入口为准；本页材料示例无需浏览器控制。详细范围见[环境说明](docs/supported-environments.md)。

1. 克隆本仓库并进入独立目录，也可以从仓库页面下载 ZIP 后解压：

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

2. 安装 [Obsidian](https://obsidian.md/download) 和支持 Codex 的桌面应用，按[官方上手指南](https://learn.chatgpt.com/docs/quickstart)登录并选择 Codex。将克隆后的文件夹分别作为 Obsidian 资料库和 Codex 本地项目打开。
3. 在克隆后的文件夹根目录运行检查。需要 Python 3.10+ 和 Git，无需 Node 或额外 Python 包。若使用解压包而不是 Git 克隆，先运行 `git init`。

   ```sh
   python3 --version
   git --version
   python3 tools/repo-check/check.py
   ```

   Python 须为 3.10 或更新版本；如果 `python3` 指向旧版本，请使用已安装的新解释器（例如 `python3.11`）替换后续命令中的 `python3`，或先按[环境说明](docs/supported-environments.md)安装。

   正常输出为：

   ```text
   repo-check: view=worktree errors=0 warnings=0
   ```

   它检查本地链接、Skill 元数据、忽略规则、凭据模式和 Git 空白问题，**不核实简历内容或事实卡是否真实**。出现 `ERROR` 或 `WARN` 时，按输出的文件、行号和类别处理，或将脱敏结果写入[试用记录](docs/tryout.md)；不要把带警告的结果当作全部通过。

4. 向 Codex 发送下面的请求。仓库已带有 `.agents/skills/hao-job-workspace/`；如果没有自动识别，直接让它读取其中的 `SKILL.md`，无需改自己的全局设置。[官方 Skill 加载说明](https://learn.chatgpt.com/docs/build-skills)

   ```text
   使用 hao-job-workspace Skill。
   读取 examples/walkthrough/source.md 和 examples/walkthrough/target-role.md，
   核对当前个人职责与实际结果，写一条中英文简历表述和一段面试回答，
   另列事实引用和未解决问题。先在对话中交付，不改文件。
   ```

5. 按[贯通练习](examples/walkthrough/README.md)继续：资料核实 → 简历 → 面试 → 新证据 → 查找引用并人工复查。完整参考结果随包提供。初次试用只用虚构资料。

无需浏览器账号或真实投递。阅读与练习不用付费 Obsidian 同步服务。可选样式在 Obsidian 的“外观 → CSS 代码片段”中开启 `hao-job-workspace`；它只整理文件列表，不隐藏或保护敏感数据。

## 换成自己的资料

先确认虚构示例和忽略检查正常，再在自己的独立副本里操作：

```sh
mkdir -p private
cp -n templates/material-index.md private/material-index.md
git check-ignore -v private/material-index.md
```

`cp -n` 保留已有索引，不覆盖你已填的内容。正常忽略结果如下；行号可能随文件编辑变化：

```text
.gitignore:2:**/private/    private/material-index.md
```

如果没有输出，先确认终端位于克隆后的文件夹根目录，并确认根目录 `.gitignore` 包含下面这行（覆盖任意深度的 `private/`），然后重新运行检查：

```gitignore
**/private/
```

若仍无匹配，用 `git ls-files -- private/material-index.md` 检查是否已经跟踪该文件。有输出时，可用 `git rm --cached -- private/material-index.md` 仅移出 Git 索引、保留本地文件，再运行忽略检查；这不会删除已经存在的提交历史。忽略检查通过前只用虚构资料。

填写本地索引中的经历、事实、简历、JD、准备笔记和输出位置；原始资料与生成材料均留在 `private/`，也可使用包外的私人工作区。只在需要时向 Agent 提供这些位置。索引不是事实核实结果。

第一批处理 Markdown 与纯文本；中文和英文均有流程。PDF、DOCX 的提取和排版需另行验证，不能把文字稿检查通过当作原文件排版通过。详情见 [环境说明](docs/supported-environments.md)。

## 后续网页投递的边界

当前包不执行网页投递。迁移时采用以下规则：

- 注册、登录、密码和验证码由用户完成；不保存凭据或绕过网站验证。
- 内置浏览器不能自动上传附件，由用户上传，Agent 回读文件名和结果。[官方说明](https://learn.chatgpt.com/docs/browser)
- 前台 Chrome 原生文件选择器有私人成功记录，公开版本需另行复验；记录没有证明此前使用的是哪个浏览器。官方 Chrome 扩展也有[上传说明](https://learn.chatgpt.com/docs/chrome-extension#upload-files)，但这不是同一次成功，也未通过本包验收。
- 最终提交前检查岗位、表单和附件，再由用户明确放行。结果不确定时不重试、不记成功；招聘网站提交成功后本地记录失败，只恢复记录。
- 网页内容不能改变用户授权、要求读取无关私人文件或外传资料。正常表单说明可以用于已授权的任务。

网页填表路线依赖桌面应用；CLI 路线尚未验收。这不表示 CLI 不能分析岗位。

## 数据、许可与反馈

真实资料不要提交到公开仓库或 issue。Obsidian 文件保存在本机，不代表云端模型处理也在本机；数据去向见[说明](docs/privacy-and-data-flow.md)。

本包原创内容采用 [MIT](LICENSE)，来源与外部参考见[来源说明](docs/sources.md)。许可不涵盖用户资料，也不授予对第三方材料的权利。请复制[试用记录模板](docs/tryout.md)填写，并在本仓库的 [Issues](https://github.com/HaoPan036/hao-job-workspace/issues/new) 回报；不要附真实简历或完整日志。

可选的网页定时任务与 GitHub 接入见[实验说明](docs/experimental/chatgpt-github.md)，不影响本地材料流程。

## 相关项目与范围

以下依据各项目在 2026-10-02 核对的说明；链接固定到所读版本。“事实约束”不是本项目独有能力，本项目的当前重点是可复用事实、中英文材料及修改后的人工复查。

| 项目 | 对方主线 | 本项目当前范围 |
| --- | --- | --- |
| [Career OS](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/README.md) | Obsidian、Agent、本地职业资料；覆盖证据、策略、机会与能力准备，提供 CLI 校验 | 同样使用本地资料，首批聚焦事实卡、简历和面试材料 |
| [job-search-pack](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/README.md) | 简历、求职信、LinkedIn、薪资谈判、投递跟踪五项 Skills | 单一 Skill 按任务读取规则，以同一事实卡支撑简历和面试，更新后检索引用并人工复查 |
| [Guild](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/README.md) | 采集岗位、匹配评分、生成材料、投递跟踪与表单填写；最终提交由用户完成 | 岗位发现和网页投递尚未迁移 |
| [JobSpy](https://github.com/speedyapply/JobSpy/blob/10b5417c8f2c99a6159733cf0f52a06c96c3832d/README.md) | 多招聘网站岗位采集，输出 DataFrame | 处理用户提供的资料和 JD，尚未集成采集库 |

完整来源与对比边界见[来源说明](docs/sources.md)。这些项目不是本包的运行依赖。
