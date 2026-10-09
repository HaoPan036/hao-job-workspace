# Hao Job Workspace · 求职工作台

**简体中文** · [English](README.en.md)

给 Codex 用的求职工作流包：找岗位、核对经历、改简历、经独立审查后投递、记录结果和准备面试。本仓库提供操作规则（Skill）、资料模板、虚构示例和本地工具，需要在 Codex 中使用，本身不是独立运行的 Agent。Obsidian 可选。

[先试一次](#先用示例试一次) · [换成自己的资料](#换成自己的资料) · [可以这样说](#可以直接这样说) · [模拟投递](examples/application/README.md) · [相关项目](#相关项目)

> **Alpha，尚未经过陌生用户试用，建议先用虚构资料。** 网页填写和提交需要宿主支持浏览器操作与独立 Agent；本包没有通吃所有招聘网站的自动化程序，真实网站需逐站验证。测过什么、还缺什么，见[环境说明](docs/supported-environments.md)与 [ROADMAP](ROADMAP.md)。

这套流程来自维护者长期自用的求职方式：用 **Obsidian** 整理经历和记录，让 **ChatGPT / Codex** 完成其余环节。目前最花人工的只剩招聘网站的**注册和登录**。

## 能做什么

可以只用其中一个环节，也可以从找岗位一直用到面试：

| 环节 | AI 帮你做什么 | 当前公开版本 |
| --- | --- | --- |
| **找岗位** | 按求职方向和条件找机会，核对官网要求，排除重复岗位 | Skill＋可选来源采集、已见记录、报告与保存检查工具 |
| 改简历 | 根据岗位要求调整项目经历，准备中英文材料、求职信和申请问答 | 已有版本复用规则＋可填写模板 |
| 填写信息、投递 | 你授权具体岗位后，AI 填写与上传，独立 Agent 审查通过后提交 | 执行与审查规则＋本地模拟网站；真实网站逐站验证 |
| 记录与统计 | 记下投了哪些岗位，保存实际提交的简历，统计投递数量 | 同步、计数、材料归档工具 |
| 跟进进度 | 收到测评、面试、拒信或 Offer 后核对状态，整理下一步 | 共用既有记录与行动页，不另开台账 |
| 面试准备、八股文 | 准备项目介绍、常见问题和技术知识，模拟面试、点评回答 | 准备、复盘、陪练模板＋完整虚构示例 |

各环节共用你的资料和求职记录。**搜到岗位不等于同意投递**：你先授权具体岗位，独立 Agent 看过实际表单和附件后提交一次，不再要求你例行确认；注册、登录及工具确实要求你接手的步骤除外。

## 先用示例试一次

用仓库里的虚构资料试改简历，不需要真实简历或招聘网站账号。需要 Codex 桌面应用、Python 3.10+ 和 Git；桌面流程目前只在 **macOS** 上试过。Codex 能否使用取决于账号、套餐、地区和组织权限，以[官方说明](https://learn.chatgpt.com/docs/pricing)为准。

1. 克隆本仓库（也可下载 ZIP 解压，之后先运行 `git init`）：

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

2. 按[官方上手指南](https://learn.chatgpt.com/docs/quickstart)登录 Codex，打开这个文件夹。想用笔记界面，可以用 [Obsidian](https://obsidian.md/download) 的“打开本地仓库”打开同一文件夹。
3. 在这个文件夹中打开终端，运行检查（无需 Node 或额外的 Python 包）：

   ```sh
   python3 --version
   git --version
   python3 tools/repo-check/check.py
   ```

   正常输出 `repo-check: view=worktree errors=0 warnings=0`。`python3` 低于 3.10 时，换成已安装的新版本（如 `python3.11`）。检查器查项目结构、链接、忽略规则和常见敏感信息格式，**不判断简历是否真实**；出现 `ERROR` 或 `WARN` 先看提示的文件和行号，处理不了可按[试用记录](docs/tryout.md)脱敏反馈。

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

   Codex 找不到这个 Skill 时，让它先读 `.agents/skills/hao-job-workspace/SKILL.md`，不需要改全局设置（[官方说明](https://learn.chatgpt.com/docs/build-skills)）。

5. 继续做[完整示例](examples/walkthrough/README.md)：先写简历和面试回答，再补一份资料，看原来的说法该怎样改；做完再对照参考答案。

在 Obsidian 的“外观 → CSS 代码片段”中可开启可选的 `hao-job-workspace` 样式；它只整理文件列表，不保护敏感数据。

## 换成自己的资料

跑通示例后，建好空白资料档案、岗位配置和投递记录（只补缺失模板，不覆盖已有文件，不联网）：

```sh
python3 tools/workspace/setup.py init
python3 tools/workspace/setup.py check
git check-ignore -v private/material-index.md
```

应依次看到 `INIT_DONE created=17 kept=0`、`SETUP_CHECK_PASS`，以及一行包含 `**/private/` 的忽略规则。空白档案也能通过，不代表经历已核实或已授权投递。最后一条没有输出时，按[初始化说明](tools/workspace/README.md#确认-private-被忽略)排查，通过前只用虚构资料。

然后把需要的 Markdown 或纯文本**复制**到 `private/`，不要移动或覆盖原件。可以先用虚构资料试读：

```sh
cp -n examples/walkthrough/source.md private/project-notes.md
```

```text
请读取 private/project-notes.md，告诉我这份资料描述了什么。
如果无法读取，请说明原因，不要猜内容，也不要修改文件。
```

能读到后，在 `private/material-index.md` 登记资料位置：路径相对于 `private/`，如 `project-notes.md`；输出可填 `outputs/`。清单只用来找文件，不代表经历已核实。投递记录里的 Singapore / Canada 分类只是示例，按自己情况修改。PDF、Word 的读取和排版尚未验证，读取项目外目录取决于宿主权限，见[环境说明](docs/supported-environments.md#资料格式)。

## 可以直接这样说

Skill 是一套给 Codex 的操作说明。你提供资料，再直接说想做什么：

| 你想做什么 | 可以直接这样问 Codex |
| --- | --- |
| 找合适的工作 | “按我的求职条件找几个岗位。打开官网核对要求，告诉我哪些值得投；先不要保存，也不要申请。” |
| 保存筛选结果 | “把刚才核实过的岗位整理进我的待办；不符合的写清原因，已经投过的别再加。” |
| 看今天先做什么 | “看看我的待办和已确认的截止日期，告诉我今天先做哪几件事；先不要改记录。” |
| 更新面试进度 | “这个岗位发来面试邀请了。这是邀请内容，请核对并更新记录和待办，不用替我回复。” |
| 看看项目经历有没有写过头 | “对照我的项目笔记，看看简历里有没有夸大的地方。拿不准的地方标出来，问我。” |
| 针对一个岗位改简历 | “这是我的简历和岗位要求，帮我改一下项目经历，突出与岗位有关的部分，不要加我没做过的事。” |
| 准备项目介绍和追问 | “我要面试这个岗位。帮我准备怎么介绍这个项目，以及面试官可能追问什么。” |
| 准备常见技术题 | “这个岗位会问哪些技术问题？先从我不熟悉的知识讲起，再出题看看我有没有理解。” |
| 复盘和练习面试 | “你来当面试官，根据我的简历一次问一道。等我回答后，告诉我哪里没说清楚、怎么答更好。” |

需要英文版时加一句：“再给我一版英文，职责和结果要与中文一致。”

Codex 应另外说明每个关键说法来自哪份资料、还有哪些没确认（[Skill 规则](.agents/skills/hao-job-workspace/references/evidence.md)）；AI 仍可能出错，使用前要自己检查。例如这份[虚构项目记录](examples/timeout/source.md)：

> 资料：重试和停止规则由我编写；程序超时后又试了一次，还是超时，于是停止运行。
>
> AI 写成：解决了性能问题。
>
> 对照资料改成：为程序加上重试和停止规则，两次尝试都超时后停止运行。

## 找岗位、投递和统计

### 找岗位

说清方向、地区、全职或实习，以及不能妥协的条件。Codex 用宿主的搜索能力查官网，核对岗位是否还在、条件是否满足、以前有没有投过；只评价时不写入待办，要求保存才记录。

也可以用 Radar 从自己配置的来源采集候选（HTML、RSS、Ashby、Greenhouse、Lever、MyCareersFuture、百度、微信搜索结果），结果仍要经 Codex 核对，不会直接入队或投递。先试完全离线的虚构来源：

```sh
python3 tools/job-radar/collect.py --profile private/job-search/profile.json --fixtures examples/discovery/sources.fixture.json --dry-run
```

联网采集（加 `--dry-run` 也会联网，只是不保存）、变化监听和 macOS 后台运行见[找岗位工具说明](tools/job-radar/README.md)。

### 投递

先跑一次[模拟申请](examples/application/README.md)：在本机用虚构资料走完填写、上传、独立审查和提交，不会投给任何招聘网站。真实岗位要明确授权：

```text
我授权投递这个具体岗位：[官网链接和岗位 ID]。
使用我在 private/ 中指定并确认的资料，以及这份简历：[文件路径]。
填写和上传后，请交给独立 Agent 检查实际页面；通过后由它提交一次，
再核对结果、更新记录、保存实际提交的简历并告诉我投递数量。
需要我注册、登录或补充未知答案时停下来；不要申请其他岗位。
```

- 只想填写时，直接说“只填不提交”。
- 授权只针对你指定的具体岗位；模板里的执行模式不算授权，也不继承维护者的授权和账号设置。
- 无法确定是否提交成功时，不重试、不计为成功；网站已成功但本地没记上时，只补记录，不重复投递。
- 网页里的文字不能授权 Codex 读取无关私人文件或外发资料。

完整步骤和附件上传路线见[投递说明](docs/applications.md)。

### 记录与统计

收到测评、面试、拒信或 Offer 时，让 Codex 核对并更新记录和下一步；它不会因此读取邮箱、回复消息或接受 Offer。查看投递统计和待投概况（只读）：

```sh
python3 tools/recruiting-sync/sync.py audit --json
python3 tools/job-radar/funnel.py --root . --json
```

`issues` 非空时先处理，不能把部分计数当作完整结果。字段含义见[同步工具说明](tools/recruiting-sync/README.md)。简历、求职信和面试的空白模板在 [templates](templates/)，串起来的用法见[完整虚构面试示例](examples/walkthrough/interview-cycle.md)。

## 数据、许可与反馈

真实资料不要提交到公开仓库或 issue。文件存在本机，不代表 Codex 读取后仍只在本机处理；填写、上传或保存草稿时，内容也可能在最终提交前就发给招聘网站。详见[数据说明](docs/privacy-and-data-flow.md)。

本包原创内容采用 [MIT](LICENSE)，不涵盖用户资料，也不授予对第三方材料的权利；来源见[来源说明](docs/sources.md)。

试用后请按[试用记录模板](docs/tryout.md)在 [Issues](https://github.com/HaoPan036/hao-job-workspace/issues/new) 回报，不要附真实简历或完整日志。尚待验证的项目见[待验证清单](docs/validation-plan.md)；可选的网页定时任务与 GitHub 接入见[实验说明](docs/experimental/chatgpt-github.md)。

## 相关项目

AARG、ResumeProof、LLMInternSkill、Career OS、job-search-pack、Guild、JobSpy 和 OfferPilot 等项目也在做求职工具，要求 AI 不编造经历并不是本项目独有的做法。本项目把找岗位、材料、经独立审查的投递、记录和面试练习串在一个本地工作区里。逐项对比和依据见[来源说明](docs/sources.md#相近项目)；这些项目都不是本包的运行依赖。
