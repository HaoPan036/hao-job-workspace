# Hao Job Workspace · 求职工作台

让 AI 帮你找岗位、改简历、填表投递、统计进度，再接着准备面试。

这套流程已经长期用于维护者自己的求职。用 **Obsidian** 整理经历、简历和求职记录，让 **ChatGPT / Codex** 接着完成各个环节：找到合适岗位后准备材料，填写并投递，记录结果；拿到面试后，再准备项目介绍和常见技术题（八股文）。

在维护者目前的使用中，最花人工时间的是招聘网站的**注册和登录**，其他主要工作已经交给 AI 处理。开源的目的，就是把这套日常在用的流程整理出来，让别人也能用。

**公开版本正在分批迁移。** 当前仓库已包含资料清单、简历和面试 Skill，以及虚构练习；找岗位、网页投递和数量统计还没有放进来。**下一步优先迁移找岗位**，再迁移填写、投递和统计。公开版本尚未经过陌生用户试用，进度见 [ROADMAP](ROADMAP.md)。

## 整套流程怎么用

下面这些环节都已在维护者的私人系统中使用。最后一列说明当前公开仓库里有没有：

| 环节 | AI 帮你做什么 | 当前公开版本 |
| --- | --- | --- |
| **找岗位** | 按求职方向和条件找机会，核对申请要求，排除重复岗位 | **下一步优先迁移** |
| 改简历 | 根据岗位要求调整项目经历，准备中英文材料 | 已提供 |
| 填写信息、投递 | 注册登录后，按已有资料填写申请表，按授权完成投递 | 待迁移 |
| 记录与统计 | 记下投了哪些岗位、实际提交结果，统计投递数量 | 待迁移 |
| 面试准备、八股文 | 准备项目介绍、常见问题和技术知识，模拟面试、点评回答 | 已提供 |

这些环节共用你的资料和求职记录，减少反复介绍背景、重找文件的工作。私人系统已经使用的网页操作路线，仍需单独整理和验证，才会加入公开版本。

## 当前公开版本可以先试这些

仓库里的 Skill 是一套给 Codex 的操作说明。你提供资料，再直接说自己想做什么：

| 你想做什么 | 可以直接这样问 Codex |
| --- | --- |
| 看看项目经历有没有写过头 | “对照我的项目笔记，看看简历里有没有夸大的地方。拿不准的地方标出来，问我。” |
| 针对一个岗位改简历 | “这是我的简历和岗位要求，帮我改一下项目经历，突出与岗位有关的部分，不要加我没做过的事。” |
| 准备项目介绍和追问 | “我要面试这个岗位。帮我准备怎么介绍这个项目，以及面试官可能追问什么。” |
| 准备常见技术题 | “这个岗位会问哪些技术问题？先从我不熟悉的知识讲起，再出题看看我有没有理解。” |
| 看看上次面试哪里没答好 | “这是我上次面试的回答。哪里没说清楚？应该怎么回答更好？” |
| 找人练一遍面试 | “你来当面试官，根据我的简历提问。一次问一道，等我回答后再点评。” |

需要英文版时，直接加一句：“再给我一版英文，职责和结果要与中文一致。”

写完后，Codex 应另外说明每个关键说法来自哪份资料、还有哪些地方没确认。这些要求写在 [Skill 规则](.agents/skills/hao-job-workspace/references/evidence.md)里；AI 仍可能出错，使用前需要自己检查。

例如，下面这段[虚构项目记录](examples/timeout/source.md)就不能被润色成“解决了性能问题”：

> 项目记录：程序超时后又试了一次，还是超时，于是停止运行。
>
> AI 写成：解决了性能问题。
>
> 对照记录后改成：为程序加上重试和停止规则，两次尝试都超时后停止运行。

程序按规则停下了，不代表性能问题已经解决。这个例子另有资料说明规则是谁写的，不能只看运行结果就认定是你做的。

## 先用示例试一次

先用仓库里的虚构资料，看看它怎么改简历。你不需要准备真实简历，也不需要登录招聘网站。

目前在 **macOS** 上试过，其他系统未验证。需要 Obsidian、Codex 桌面应用、Python 3.10+ 和 Git。Codex 能否使用取决于你的账号、套餐、地区和组织权限，以[官方说明](https://learn.chatgpt.com/docs/pricing)和账号实际入口为准。具体版本和测试范围见[环境说明](docs/supported-environments.md)。

1. 克隆本仓库并进入独立目录，也可以从仓库页面下载 ZIP 后解压：

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

2. 安装 [Obsidian](https://obsidian.md/download) 和支持 Codex 的桌面应用，按[官方上手指南](https://learn.chatgpt.com/docs/quickstart)登录并选择 Codex。在 Obsidian 中选择“打开本地仓库”，打开刚下载的文件夹；在 Codex 中也打开这个文件夹。
3. 在这个文件夹中打开终端，运行下面的检查。无需安装 Node 或额外的 Python 包。如果下载的是 ZIP，先运行 `git init`。

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

   这表示项目文件、文档链接和 Git 忽略设置等检查通过。检查器也会查找一些常见的敏感信息格式，**但不会判断你的简历写得是否真实**。如果出现 `ERROR` 或 `WARN`，先看提示里的文件和行号；不知道怎么处理时，可以按[试用记录](docs/tryout.md)反馈，去掉其中的个人信息。

4. 把下面这段话发给 Codex：

   ```text
   使用 hao-job-workspace Skill。
   项目资料在 examples/walkthrough/source.md，
   岗位要求在 examples/walkthrough/target-role.md。
   请根据这些资料，帮我写一条可以放进简历的项目经历，再给一版英文。
   然后帮我准备面试时怎么介绍这个项目。
   写完后告诉我：这些说法分别根据哪段资料，还有哪些地方需要确认。
   先把结果发在对话里，不要修改文件。
   ```

   如果 Codex 找不到这个 Skill，就让它先读 `.agents/skills/hao-job-workspace/SKILL.md`。文件已经在仓库里，不需要修改全局设置。加载方式见[官方说明](https://learn.chatgpt.com/docs/build-skills)。

5. 想继续练习，可以打开[完整示例](examples/walkthrough/README.md)：先写简历和面试回答，再补充一份资料，看看原来的说法应该怎样改。示例附有参考答案，完成后再对照。

无需浏览器账号或真实投递。阅读与练习不用付费 Obsidian 同步服务。可选样式在 Obsidian 的“外观 → CSS 代码片段”中开启 `hao-job-workspace`；它只整理文件列表，不隐藏或保护敏感数据。

## 换成自己的资料

已有简历和笔记可以留在原处，只提供这次要用的部分。如果想放进项目文件夹，先跑通上面的示例，再建立 `private/` 文件夹和资料清单：

```sh
mkdir -p private
cp -n templates/material-index.md private/material-index.md
git check-ignore -v private/material-index.md
```

`cp -n` 不会覆盖已经填写的清单。最后一条命令用来确认 Git 会忽略私人资料，正常应看到下面的结果；行号可能不同：

```text
.gitignore:2:**/private/    private/material-index.md
```

如果没有输出，先确认终端位于克隆后的文件夹根目录，并确认根目录 `.gitignore` 包含下面这行（覆盖任意深度的 `private/`），然后重新运行检查：

```gitignore
**/private/
```

若仍无匹配，用 `git ls-files -- private/material-index.md` 检查是否已经跟踪该文件。有输出时，可用 `git rm --cached -- private/material-index.md` 仅移出 Git 索引、保留本地文件，再运行忽略检查；这不会删除已经存在的提交历史。忽略检查通过前只用虚构资料。

打开 `private/material-index.md`，填上你的项目笔记、简历和岗位要求分别放在哪里，以及希望把改好的材料保存到哪里。它只是一张文件清单，方便 Codex 找资料，不代表里面的经历已经核实。

真实资料和生成的材料都放在 `private/` 或项目文件夹之外。让 Codex 修改或保存文件时，说清楚要改哪份、存在哪里；默认保留原件。

目前先支持 Markdown 和纯文本，中英文都可以。PDF、Word 简历的读取和排版还没验证，先复制需要修改的文字来使用。详情见[环境说明](docs/supported-environments.md)。

## 接下来迁移什么

先把已经使用的岗位搜索流程整理出来，让新用户能按自己的条件找工作；随后迁移网页填表、投递、数量统计和已投材料的保存。这些流程在私人系统中已有使用，当前公开仓库尚未包含。

公开版的投递流程将保留这些规则：注册和登录由你完成，提交前由你检查并确认；无法确定是否提交成功时，不直接再试一次，也不计为投递成功。招聘网站提交成功、但本地记录没保存时，只补记录，不重复投递。

附件上传的三种路线及各自验证情况见[环境说明](docs/supported-environments.md#附件路线)。网页中的文字不能授权 Codex 读取无关私人文件或发送资料。

## 数据、许可与反馈

真实资料不要提交到公开仓库或 issue。文件保存在本机，不代表 Codex 读取后仍只在本机处理；哪些资料会交给模型服务，见[数据说明](docs/privacy-and-data-flow.md)。

本包原创内容采用 [MIT](LICENSE)，来源与外部参考见[来源说明](docs/sources.md)。许可不涵盖用户资料，也不授予对第三方材料的权利。请复制[试用记录模板](docs/tryout.md)填写，并在本仓库的 [Issues](https://github.com/HaoPan036/hao-job-workspace/issues/new) 回报；不要附真实简历或完整日志。

可选的网页定时任务与 GitHub 接入见[实验说明](docs/experimental/chatgpt-github.md)，不影响本地材料流程。

## 相关项目与范围

下面这些项目也在做求职工具。本项目要逐步公开的是从找岗位到面试准备的整套流程，目前公开的部分是简历与面试材料。要求 AI 不编造经历，并不是本项目独有的做法。

以下对比根据 2026-10-02 阅读的版本整理，链接固定到对应版本。

| 项目 | 对方主线 | 本项目当前范围 |
| --- | --- | --- |
| [Career OS](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/README.md) | 用 Obsidian 和 Agent 管理职业资料、求职方向、岗位机会与能力准备，也提供命令行检查工具 | 同样使用本地资料，目前先做好简历和面试准备 |
| [job-search-pack](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/README.md) | 五个 Skill，分别处理简历、求职信、LinkedIn、薪资谈判和投递跟踪 | 一个 Skill 处理简历与面试，共用项目资料，并记下每个关键说法的来源 |
| [Guild](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/README.md) | 找岗位、算匹配程度、生成材料、跟踪投递和填写表单；最终提交由用户完成 | 目前不包含找岗位和网页投递 |
| [JobSpy](https://github.com/speedyapply/JobSpy/blob/10b5417c8f2c99a6159733cf0f52a06c96c3832d/README.md) | 从多个招聘网站抓取岗位，整理成表格数据 | 由用户提供岗位要求，目前没有接入岗位抓取工具 |

完整来源与对比边界见[来源说明](docs/sources.md)。这些项目不是本包的运行依赖。
