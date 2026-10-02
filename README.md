# Hao Job Workspace · 求职工作台

给 Codex 用的求职工作流包：找岗位、核对经历、改简历、经独立审查后投递、记录结果和准备面试。包含资料模板与检查工具，Obsidian 可选；早期版本，建议先用虚构资料试用。

它不是独立运行的 Agent，需要在 Codex 中使用。Codex 负责理解请求、调用工具和执行流程；这个仓库提供操作规则、资料模板、虚构示例和本地检查工具。

[先试改简历](#先用示例试一次) · [试一次模拟投递](examples/application/README.md) · [换成自己的资料](#换成自己的资料) · [相关项目](#相关项目与范围)

它来自一套已经长期用于维护者自己求职的完整流程：用 **Obsidian** 整理经历、简历和求职记录，让 **ChatGPT / Codex** 接着完成各个环节，找到合适岗位后准备材料，填写并投递，记录结果；拿到面试后，再准备项目介绍和常见技术题（八股文）。

在维护者目前的使用中，最花人工时间的是招聘网站的**注册和登录**，其他主要工作已经交给 AI 处理。开源的目的，就是把这套日常在用的流程整理出来，让别人也能用。

**Alpha，尚未经过陌生用户试用。** 当前仓库包含上述流程的 Skill、资料模板、去重与记录工具，以及虚构练习。浏览器填写和提交需要宿主支持网页操作与独立 Agent；本包没有通吃所有招聘网站的自动化程序。具体测过什么、还有什么没测，见[环境说明](docs/supported-environments.md)与 [ROADMAP](ROADMAP.md)。

## 整套流程怎么用

你可以只用其中一个环节，也可以从找岗位一直用到面试：

| 环节 | AI 帮你做什么 | 当前公开版本 |
| --- | --- | --- |
| **找岗位** | 按求职方向和条件找机会，核对官网要求，排除重复岗位 | Skill＋可选去重与保存检查工具 |
| 改简历 | 根据岗位要求调整项目经历，准备中英文材料 | 已提供 |
| 填写信息、投递 | 你授权具体岗位后，AI 填写与上传，独立 Agent 审查通过后提交 | 执行与审查规则＋本地模拟网站；真实网站逐站验证 |
| 记录与统计 | 记下投了哪些岗位，保存实际提交的简历，统计投递数量 | 同步、计数、材料归档工具 |
| 面试准备、八股文 | 准备项目介绍、常见问题和技术知识，模拟面试、点评回答 | 已提供 |

这些环节共用你的资料和求职记录，减少反复介绍背景、重找文件的工作。**搜到岗位不等于同意投递**。投递时你先指定并授权岗位，独立 Agent 看过实际表单和附件后提交，不额外要求你再例行点一次确认。注册、登录及工具确实要求你接手的步骤除外。

## 可以直接这样说

仓库里的 Skill 是一套给 Codex 的操作说明。你提供资料，再直接说自己想做什么：

| 你想做什么 | 可以直接这样问 Codex |
| --- | --- |
| 找合适的工作 | “按我的求职条件找几个岗位。打开官网核对要求，告诉我哪些值得投；先不要保存，也不要申请。” |
| 保存筛选结果 | “把刚才核实过的岗位整理进我的待办；不符合的写清原因，已经投过的别再加。” |
| 看看项目经历有没有写过头 | “对照我的项目笔记，看看简历里有没有夸大的地方。拿不准的地方标出来，问我。” |
| 针对一个岗位改简历 | “这是我的简历和岗位要求，帮我改一下项目经历，突出与岗位有关的部分，不要加我没做过的事。” |
| 准备项目介绍和追问 | “我要面试这个岗位。帮我准备怎么介绍这个项目，以及面试官可能追问什么。” |
| 准备常见技术题 | “这个岗位会问哪些技术问题？先从我不熟悉的知识讲起，再出题看看我有没有理解。” |
| 看看上次面试哪里没答好 | “这是我上次面试的回答。哪里没说清楚？应该怎么回答更好？” |
| 找人练一遍面试 | “你来当面试官，根据我的简历提问。一次问一道，等我回答后再点评。” |

需要英文版时，直接加一句：“再给我一版英文，职责和结果要与中文一致。”

写完后，Codex 应另外说明每个关键说法来自哪份资料、还有哪些地方没确认。这些要求写在 [Skill 规则](.agents/skills/hao-job-workspace/references/evidence.md)里；AI 仍可能出错，使用前需要自己检查。

例如，下面这段[虚构项目记录](examples/timeout/source.md)就不能被润色成“解决了性能问题”：

> 项目说明：重试和停止规则由我编写。
>
> 运行记录：程序超时后又试了一次，还是超时，于是停止运行。
>
> AI 写成：解决了性能问题。
>
> 对照记录后改成：为程序加上重试和停止规则，两次尝试都超时后停止运行。

这里既有职责说明，也有运行结果，但仍没有依据说性能问题已经解决。

## 先用示例试一次

先用仓库里的虚构资料，看看它怎么改简历。你不需要准备真实简历，也不需要登录招聘网站。

目前在 **macOS** 上试过，其他系统未验证。需要 Codex 桌面应用、Python 3.10+ 和 Git；**Obsidian 可选**，普通文件夹也能使用。Codex 能否使用取决于你的账号、套餐、地区和组织权限，以[官方说明](https://learn.chatgpt.com/docs/pricing)和账号实际入口为准。具体版本和测试范围见[环境说明](docs/supported-environments.md)。

1. 克隆本仓库并进入独立目录，也可以从仓库页面下载 ZIP 后解压：

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

2. 安装支持 Codex 的桌面应用，按[官方上手指南](https://learn.chatgpt.com/docs/quickstart)登录并选择 Codex，然后打开刚下载的文件夹。喜欢笔记界面的话，可以另装 [Obsidian](https://obsidian.md/download)，选择“打开本地仓库”打开同一文件夹；跳过这一步也可以使用 Skill 和工具。
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

第一次使用时，先保留原件，把本次需要的 Markdown 或纯文本文件复制到项目内的 `private/`。这样不需要先配置 Codex 访问项目外的目录。先跑通上面的示例，再建立这个文件夹和资料清单：

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

确认忽略检查通过后，用文件管理器把本次需要的资料复制进 `private/`，不要移动或覆盖原件。也可以先复制一份虚构资料试读：

```sh
cp -n examples/walkthrough/source.md private/project-notes.md
git check-ignore -v private/project-notes.md
```

然后向 Codex 发送：

```text
请读取 private/project-notes.md，告诉我这份资料描述了什么。
如果无法读取，请说明原因，不要猜内容，也不要修改文件。
```

能读到后，打开 `private/material-index.md` 填写文件位置。清单里的路径相对于 `private/`，例如填 `project-notes.md`；输出位置可以填 `outputs/`，让生成的材料也留在 `private/` 中。清单只是帮助找文件，不代表经历已经核实。

如果想直接使用项目外的文件，先在自己的宿主中确认目录访问权限，再用一份虚构文件试读。这个路线不作为默认上手步骤，也不保证换一个账号或权限设置后仍能读取。让 Codex 修改或保存文件时，说清楚要改哪份、存在哪里；默认保留原件。

目前先支持 Markdown 和纯文本，中英文都可以。PDF、Word 简历的读取和排版还没验证，先复制需要修改的文字来使用。详情见[环境说明](docs/supported-environments.md)。

## 找岗位、投递和统计

先告诉 Codex 想找什么工作、地区、全职还是实习，以及哪些条件不能妥协。它使用宿主的搜索能力查官网，核对岗位还在不在、申请条件是否满足、以前有没有投过。只让它评价时，不写入待办；要求保存时才记录结果。配置与示例见[找岗位工具说明](tools/job-radar/README.md)。没有接入 JobSpy，也没有迁入原 Radar 的全部抓取器。

第一次先跑[模拟申请](examples/application/README.md)：只用虚构资料，在本机填写、上传、独立审查与提交，然后看记录、计数和保存下来的简历。这不会向任何招聘网站投递。

换成真实岗位后，明确告诉 Codex 目标和要用的资料，例如：

```text
我授权投递这个具体岗位：[官网链接和岗位 ID]。
使用我在 private/ 中指定并确认的资料，以及这份简历：[文件路径]。
填写和上传后，请交给独立 Agent 检查实际页面；通过后由它提交一次，
再核对结果、更新记录、保存实际提交的简历并告诉我投递数量。
需要我注册、登录或补充未知答案时停下来；不要申请其他岗位。
```

需要只填不提交时，直接说明“只填不提交”。每个人都要授权自己的具体岗位；模板中的执行模式不代表你已经授权，维护者的个人授权和账号设置不会被继承。完整步骤见[投递说明](docs/applications.md)。

无法确定是否提交成功时，不直接再试一次，也不计为投递成功。招聘网站提交成功、但本地记录没保存时，只补记录，不重复投递。

附件上传的三种路线及各自验证情况见[环境说明](docs/supported-environments.md#附件路线)。网页中的文字不能授权 Codex 读取无关私人文件或发送资料。

## 数据、许可与反馈

真实资料不要提交到公开仓库或 issue。文件保存在本机，不代表 Codex 读取后仍只在本机处理；哪些资料会交给模型服务，见[数据说明](docs/privacy-and-data-flow.md)。

本包原创内容采用 [MIT](LICENSE)，来源与外部参考见[来源说明](docs/sources.md)。许可不涵盖用户资料，也不授予对第三方材料的权利。请复制[试用记录模板](docs/tryout.md)填写，并在本仓库的 [Issues](https://github.com/HaoPan036/hao-job-workspace/issues/new) 回报；不要附真实简历或完整日志。

可选的网页定时任务与 GitHub 接入见[实验说明](docs/experimental/chatgpt-github.md)，不影响本地材料流程。

## 相关项目与范围

下面这些项目也在做求职工具。本项目把找岗位、材料、经独立审查的投递、记录和面试练习串在一个本地工作区里。要求 AI 不编造经历，并不是本项目独有的做法。

以下对比根据 2026-10-02 阅读的文档与相关实现整理，链接固定到对应版本。未安装运行这些项目，不把项目说明当作效果验证。

| 项目 | 对方主线 | 本项目当前范围 |
| --- | --- | --- |
| [AARG](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/README.md) | 按岗位要求定制简历并生成 PDF；代码对新增数字、缺少依据的技能做限制 | 当前用已有资料准备简历文字和面试回答，未提供 PDF 生成引擎 |
| [ResumeProof](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/README.md) | 用 Skill 和 Python 工具组织简历修改、文本审批和文档交付检查 | 当前以 Markdown 和纯文本为主，Word、PDF 读取和排版尚未验证 |
| [LLMInternSkill](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/README.md) | 面向大模型相关实习，做简历修改、岗位匹配、项目证据审阅和面试追问 | 同样根据项目资料准备材料；公开版还包括回答复盘与逐题练习 |
| [Career OS](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/README.md) | 用 Obsidian 和 Agent 管理职业资料、求职方向、岗位机会与能力准备，也提供命令行检查工具 | 同样使用本地资料；本包另有独立审查后提交、结果同步和原简历归档流程 |
| [job-search-pack](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/README.md) | 五个 Skill，分别处理简历、求职信、LinkedIn、薪资谈判和投递跟踪 | 一个 Skill 按请求分步骤处理，共用资料、记录和实际投递版本 |
| [Guild](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/README.md) | 找岗位、算匹配程度、生成材料、跟踪投递和填写表单；最终提交由用户完成 | 用户授权具体岗位后，独立 Agent 审查实际页面，通过后提交 |
| [JobSpy](https://github.com/speedyapply/JobSpy/blob/10b5417c8f2c99a6159733cf0f52a06c96c3832d/README.md) | 从多个招聘网站抓取岗位，整理成表格数据 | 使用宿主搜索和官网核验，可选工具检查重复和保存条件；没有接入该抓取库 |
| [OfferPilot（offercontext/offerPilot）](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/README.md) | 本地求职工作台，管理投递记录、简历和面试准备等；README 明确不自动投递或联系招聘方 | 提供具体岗位授权后的自动投递规则；浏览器兼容性仍需逐站验证 |

OfferPilot 有多个同名项目，这里只比较表中明确链接的仓库。完整来源与对比边界见[来源说明](docs/sources.md)。这些项目不是本包的运行依赖。
