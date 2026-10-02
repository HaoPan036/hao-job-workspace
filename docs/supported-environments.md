# 环境与资料说明

## 当前范围

| 组成 | 当前范围 | 验证边界 |
| --- | --- | --- |
| Obsidian + Codex 桌面 / macOS | 共享本地目录，Markdown 资料与中英文材料 | 已做下述干净克隆检查；首次安装、新账号与陌生用户尚未验收 |
| hao-job-workspace Skill | 事实核对、简历文字、面试准备/复盘/陪练 | 独立副本 Agent 演练通过；不等于陌生用户验收 |
| Python 与 Git | 运行公开副本检查器 | Python 3.10+，标准库；维护环境为 3.11.14，不代表全部版本实测 |
| 网页填表 | 后续迁移，依赖桌面浏览器能力 | 当前包不含此流程 |
| CLI、IDE、其他系统 | 可能使用文件与 Skill 能力 | 项目路线未验收；官方内置浏览器不在 CLI/IDE 中提供 |

此前私人岗位流程主要用于中国与新加坡；地区、实习与台账假设随岗位和投递功能迁移时参数化，不宣称全球投递支持。中文和英文材料已有流程，语言不能与岗位地区混为一谈。

## 最近一次维护者检查

2026-10-02，在提交 `cbeafe1` 的全新本地 Git 克隆中检查，未复制私人资料或原资料库配置。使用 macOS 15.7.3、Obsidian 1.13.7、Python 3.11.14、Git 2.39.5：

- README 的本地检查输出 `repo-check: view=worktree errors=0 warnings=0`。默认 `python3` 是旧版本时，按文档改用已安装的 `python3.11`。
- 复制虚构索引后，`git check-ignore` 命中 `**/private/`；重复复制没有覆盖已有索引。
- 在 Obsidian 打开 README、切换阅读视图并跳转到贯通练习。实际生成的 `.obsidian/app.json`、`appearance.json`、`core-plugins.json`、`workspace.json` 均被忽略，操作后 `git status --short --untracked-files=all` 无输出。
- 独立 Agent 仅使用克隆中的公开资料与 Skill，生成了中英文简历和面试回答；职责限定为补充停止条件和测试，没有加入性能提升、Kubernetes 或生产部署经历。

这是已安装软件、已有宿主账号下的维护者与 Agent 检查，未覆盖软件首次安装、全新账号、陌生用户或其他操作系统。仓库检查通过也不代表简历事实正确。

同日，另在提交 `163a7c8` 的干净克隆中检查资料导入：在克隆外创建一份虚构 Markdown，用本地复制命令放入 `private/project-notes.md`，确认原件与副本字节一致；独立 Agent 仅读取项目内副本，正确读出项目内容和核对短语。该文件命中 Git 忽略规则，`git ls-files -- private/` 与 `git status --short --untracked-files=all` 均无输出。此检查证明当前宿主下“复制进项目后读取”的路线可用，没有验证新账号或项目外目录授权。

## 安装与账号

- 安装 Obsidian 与支持 Codex 的桌面应用，在 Codex 中登录、打开克隆后的文件夹，并确认可以读取其中的虚构文件及使用 Skill。按[官方上手指南](https://learn.chatgpt.com/docs/quickstart)操作。
- 检查账号当前能选择 Codex、额度是否足够、组织是否允许本地文件和所需工具。后续网页任务还须确认浏览器入口与网站权限。套餐、地区及组织限制以[官方说明](https://learn.chatgpt.com/docs/pricing)和账户显示为准，不要求用户盲买特定套餐。
- 运行检查需要 Python 3.10+ 与 Git。可从 [Python 官方下载](https://www.python.org/downloads/)和 [Git 安装说明](https://git-scm.com/downloads)安装；随后执行 `python3 --version`、`git --version`。
- 如果 `python3` 仍指向旧系统版本，使用新安装的解释器（例如 `python3.11`）替换后续命令里的 `python3`；安装了新版本不等于默认命令已经切换。
- 本包无需 `pip install`、Node、npm 或浏览器扩展。之后增加能力才列出新增依赖。核心文字示例不用任何招聘账号。
- 不提供另一个 AI API 后端；使用者使用自己的 Agent 宿主账号。复制 Skill 不会赋予额外模型或浏览器权限。

官方入口核对日期：2026-10-01。宿主功能说明不等同于本项目跨宿主验收。

## 附件路线

| 路线 | 依据 | 本包处理 |
| --- | --- | --- |
| 内置浏览器 | [官方说明](https://learn.chatgpt.com/docs/browser)不支持自动上传 | 用户手动上传，Agent 回读检查 |
| 前台 Chrome 原生文件选择器 | 维护者记录过一次成功 | 仅私人个案，公开前复验，不推断最初浏览器 |
| 官方 Chrome 扩展 | [官方上传配置](https://learn.chatgpt.com/docs/chrome-extension#upload-files) | 文档说明与历史个案分开，尚未验收 |

注册登录、密码和验证中需要接手的步骤由用户完成。页面说明可用于已授权任务，不能改变授权范围。投递功能迁入公开版后，每位使用者先授权自己的具体岗位，再由独立 Agent 审查实际表单和附件，通过后提交；不继承维护者的个人授权，不额外要求例行人工提交确认。工具确实要求当次确认时仍须遵守。

## 资料格式

Markdown 和 UTF-8 纯文本可直接作为材料来源，原件保留。事实卡使用现有字段，不创建新的数据协议。PDF、DOCX、图片、OCR 和格式导出未列为首批验收范围；需要相应能力时另行选择并验证工具。

默认上手路线是由用户把需要的文件复制到项目内的 `private/`，确认 Git 忽略规则生效，再让 Codex 读取。项目外目录是否可读取决于宿主和用户授予的权限，未列为通用支持能力；本机曾经读到不能证明其他账号也能读到。

Obsidian 只需要打开资料库；可选 CSS 手动启用。不分发插件数据、最近文件或工作区状态。默认所有 private 目录都被忽略，无说明文件例外。
