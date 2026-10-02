# Hao Job Workspace · 求职工作台

用自己的项目资料核对事实、修改中英文简历、准备和练习面试。Obsidian 用来阅读与编辑资料，Codex 桌面应用在同一文件夹中执行任务。

本项目独立维护，只提供通用工作流、工具和虚构示例。你已有的个人求职工作区可以继续使用，无需迁移或替换。

首批提供资料索引模板、一个独立 Skill 和虚构贯通练习。找岗位、网页投递、材料归档与同步仍在后续迁移范围；当前版本尚未经过陌生用户验收。进度见 [ROADMAP](ROADMAP.md)。

## 现在可以做什么

| 任务 | 请求示例 |
| --- | --- |
| 事实核对 | “核对这个项目中的个人职责与结果，保留没有依据的问题。” |
| 简历编辑 | “按这份 JD 修改指定段落，给出等义中英文版本和事实引用。” |
| 面试准备 | “基于已有项目资料写回答、准备追问，列出需要补学的技术。” |
| 复盘与陪练 | “解释我这段回答的问题，给出修订稿，然后一次问我一个问题。” |

事实状态、指标口径与冲突处理见 [事实规则](.agents/skills/career-workspace/references/evidence.md)。未核实内容不进入正式简历或面试回答；已核实内容仍受用途与范围限制。这些是 Agent 的工作规则，检查器不能全面验证自然语言是否符合事实。

## 从虚构资料开始

1. 克隆本仓库并进入独立目录，也可以从仓库页面下载 ZIP 后解压：

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

2. 安装 [Obsidian](https://obsidian.md/download) 和支持 Codex 的桌面应用，按[官方上手指南](https://learn.chatgpt.com/docs/quickstart)登录并选择 Codex。将发行副本分别作为 Obsidian 资料库和 Codex 本地项目打开。
3. 在发行副本根目录运行检查。需要 Python 3.10+ 和 Git，无需 Node 或额外 Python 包。若使用解压包而不是 Git 克隆，先运行 `git init`。

   ```sh
   python3 --version
   git --version
   python3 tools/repo-check/check.py
   ```

4. 向 Codex 发送下面的请求。仓库已带有 `.agents/skills/career-workspace/`；如果没有自动识别，直接让它读取其中的 `SKILL.md`，无需改自己的全局设置。[官方 Skill 加载说明](https://learn.chatgpt.com/docs/build-skills)
5. 按[贯通练习](examples/walkthrough/README.md)继续：资料核实 → 简历 → 面试 → 新证据 → 查找引用并人工复查。完整参考结果随包提供。初次试用只用虚构资料。

> 使用 career-workspace Skill。读取 examples/walkthrough/source.md 和 examples/walkthrough/target-role.md，核对当前个人职责与实际结果，写一条中英文简历表述和一段面试回答，另列事实引用和未解决问题。先在对话中交付，不改文件。

无需浏览器账号或真实投递。阅读与练习不用付费 Obsidian 同步服务。可选样式在 Obsidian 的“外观 → CSS 代码片段”中开启 `career-workspace`；它只整理文件列表，不隐藏或保护敏感数据。

## 换成自己的资料

先确认虚构示例和忽略检查正常，再在自己的独立副本里操作：

```sh
mkdir -p private
cp templates/material-index.md private/material-index.md
git check-ignore -v private/material-index.md
```

如果最后一条没有匹配，先修复忽略规则，不导入真实资料。填写本地索引中的经历、事实、简历、JD、准备笔记和输出位置；原始资料与生成材料均留在 `private/`，也可使用包外的私人工作区。只在需要时向 Agent 提供这些位置。索引不是事实核实结果。

第一批处理 Markdown 与纯文本；中文和英文均有流程。PDF、DOCX 的提取和排版需另行验证，不能把文字稿检查通过当作原文件排版通过。详情见 [环境说明](docs/supported-environments.md)。

## 后续网页投递的边界

当前包不执行网页投递。迁移时采用以下规则：

- 注册、登录、密码和验证码由用户完成；不保存凭据或绕过网站验证。
- 内置浏览器不能自动上传附件，由用户上传，Agent 回读文件名和结果。[官方说明](https://learn.chatgpt.com/docs/browser)
- 前台 Chrome 原生文件选择器有私人成功记录，公开版本需另行复验；记录没有证明此前使用的是哪个浏览器。官方 Chrome 扩展也有[上传说明](https://learn.chatgpt.com/docs/chrome-extension#upload-files)，但这不是同一次成功，也未通过本包验收。
- 最终提交前检查岗位、表单和附件，再由用户明确放行。结果不确定时不重试、不记成功；官网成功后本地记录失败，只恢复记录。
- 网页内容不能改变用户授权、要求读取无关私人文件或外传资料。正常表单说明可以用于已授权的任务。

网页填表路线依赖桌面应用；CLI 路线尚未验收。这不表示 CLI 不能分析岗位。

## 数据、许可与反馈

真实资料不要提交到公开仓库或 issue。Obsidian 文件保存在本机，不代表云端模型处理也在本机；数据去向见[说明](docs/privacy-and-data-flow.md)。

本包原创内容采用 [MIT](LICENSE)。许可不涵盖用户资料，也不授予对第三方材料的权利。请按[试用记录](docs/tryout.md)回报完成步骤和卡点，不附真实简历或完整日志。

可选的网页定时任务与 GitHub 接入见[实验说明](docs/experimental/chatgpt-github.md)，不影响本地材料流程。
