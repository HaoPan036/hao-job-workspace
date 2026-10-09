# 来源、许可与对比依据

本仓库的工作流、事实卡约定、材料与求职运营模板、repo-check、application-profile、application-record、recruiting-sync，以及 job-radar 的前台采集、解析、已见岗位记录、来源健康、报告、去重、受控保存和漏斗摘要，从维护者自有的求职工作流抽取并去个人化。可选 changedetection 桥接与 macOS 安装器同样迁自既有实现，改为显式配置与执行；本包不分发第三方 changedetection.io 服务。示例、本地模拟网站与模板初始化入口是新写的配套内容。地区、路径、表头、采集来源及求职条件均改为配置。公开版本不包含原私人仓库历史、真实简历、公司材料或原始面试记录。

[LICENSE](../LICENSE) 为完整 MIT 文本，版权声明为 `Copyright (c) 2026 Hao Job Workspace contributors`。它覆盖本仓库原创内容，不重新授权用户资料、招聘网站内容或下面链接到的项目与官方文档。

## 运行环境与文档引用

- [Obsidian](https://obsidian.md/) 用于阅读与编辑本地 Markdown；本仓库不分发 Obsidian 程序或第三方插件。
- [Python](https://www.python.org/) 与 [Git](https://git-scm.com/) 是本机检查工具；repo-check 只使用 Python 标准库，本仓库不打包这些程序。
- Codex 使用说明链接到 [OpenAI 上手指南](https://learn.chatgpt.com/docs/quickstart)、[Skill 文档](https://learn.chatgpt.com/docs/build-skills)、[账号与套餐](https://learn.chatgpt.com/docs/pricing)及[浏览器说明](https://learn.chatgpt.com/docs/browser)。官方功能说明与本项目的实际验收分别记录。

## 相近项目

以下对比于 2026-10-02 核对，是对照阅读，不表示本项目移植自这些仓库；它们也未作为本包运行依赖或分发内容。引用固定到本次所读版本，后续可能变化。仅静态阅读文档与相关实现，未安装、运行或执行这些项目的测试，不评价实际生成效果。本项目把找岗位、材料、经独立审查的投递、记录和面试练习串在一个本地工作区里；要求 AI 不编造经历并不是本项目独有的做法。

| 项目 | 对方主线 | 本项目当前范围 |
| --- | --- | --- |
| [AARG](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/README.md) | 按岗位要求定制简历并生成 PDF；代码对新增数字、缺少依据的技能做限制 | 当前用已有资料准备简历文字和面试回答，未提供 PDF 生成引擎 |
| [ResumeProof](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/README.md) | 用 Skill 和 Python 工具组织简历修改、文本审批和文档交付检查 | 当前以 Markdown 和纯文本为主，Word、PDF 读取和排版尚未验证 |
| [LLMInternSkill](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/README.md) | 面向大模型相关实习，做简历修改、岗位匹配、项目证据审阅和面试追问 | 同样根据项目资料准备材料；公开版还包括回答复盘与逐题练习 |
| [Career OS](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/README.md) | 用 Obsidian 和 Agent 管理职业资料、求职方向、岗位机会与能力准备，也提供命令行检查工具 | 同样使用本地资料；本包另有独立审查后提交、结果同步和原简历归档流程 |
| [job-search-pack](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/README.md) | 五个 Skill，分别处理简历、求职信、LinkedIn、薪资谈判和投递跟踪 | 一个 Skill 按请求分步骤处理，共用资料、记录和实际投递版本 |
| [Guild](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/README.md) | 找岗位、算匹配程度、生成材料、跟踪投递和填写表单；最终提交由用户完成 | 用户授权具体岗位后，独立 Agent 审查实际页面，通过后提交 |
| [JobSpy](https://github.com/speedyapply/JobSpy/blob/10b5417c8f2c99a6159733cf0f52a06c96c3832d/README.md) | 从多个招聘网站抓取岗位，整理成表格数据 | 宿主搜索与官网核验，另有可选来源采集、重复和保存检查；没有接入该抓取库 |
| [OfferPilot（offercontext/offerPilot）](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/README.md) | 本地求职工作台，管理投递记录、简历和面试准备等；README 明确不自动投递或联系招聘方 | 提供具体岗位授权后的自动投递规则；浏览器兼容性仍需逐站验证 |

逐项依据：

- **AARG**：仓库 `joseym/aarg`，版本 `7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d`。[README](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/README.md)与[循环设计](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/docs/design/adversarial-loop.md)说明按 JD 定制、审阅修改和生成 PDF 的流程。[装配代码](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/crates/aarg-domain/src/tailor.rs#L480-L637)按已有 bullet ID 找来源，并过滤无 evidence 的技能；[数字检查](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/crates/aarg-domain/src/tailor.rs#L894-L908)支持对新增数字的限制。这些具体检查不能证明全部自然语言事实真实。仓库提供 [MIT](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/LICENSE-MIT) 或 [Apache 2.0](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/LICENSE-APACHE) 许可。
- **ResumeProof**：仓库 `caihhhhhh/resume-proof`，版本 `0213db759582da9addbcf1e142ace92a5d95a0dd`。[README](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/README.md)与 [Skill](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/SKILL.md)规定证据台账、JD 匹配、文本审批和双语修改流程。[Python CLI](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/scripts/resume_proof.py#L87-L272)记录审批文本的 SHA-256，并在交付时检查审批状态、文本变化、QA 状态和文件冲突；其中事实与视觉复核状态仍依赖复核者提供，CLI 不会自动证明内容真实或用户确实批准。许可证为 [MIT](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/LICENSE)。
- **LLMInternSkill**：仓库 `wanyichen06/LLMInternSkill`，版本 `e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933`。[README](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/README.md)、[Skill](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/SKILL.md)和 [Evidence Contract](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/skill-references/evidence-contract.md)要求强主张有证据，并收窄依据不足的经历表述；[项目推荐规则](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/skill-references/project-scout.md)将推荐项目作为后续学习与复现机会。这些是工作规则，不是已证明能阻止所有编造的程序保证。仓库为 [MIT](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/LICENSE)，README 另记录简历模板的上游许可。

- **Career OS**：版本 `370274792e6259d5b874ec627c5e31140309f03c`。[README](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/README.md)描述 Obsidian/Agent 职业工作区；[数据模型](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/docs/data-model.md#L63-L69)也有 Claim 状态、用途与来源约束，不能把这些约束称为本项目独有。
- **job-search-pack**：版本 `d603672432ad67d5b26d1b320044d9cd1a05c980`。[README](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/README.md)列出五项求职 Skills；[Resume Tailor](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/skills/resume-tailor/SKILL.md#L89-L91)也明确禁止虚构，不用“它只润色、我们才核实”来概括差异。
- **Guild**：对应仓库 `arafa-dev/ai-job-application-automation`，版本 `de8cc9343bd046613b1f4b59e436fb517eb93131`。[README](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/README.md)说明全流程定位与用户最终提交；[校验代码](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/packages/cv-engine/src/validators.ts#L132-L177)包含 bullet ID、改写距离、新增数量词与已知技能检查。它有程序约束，但这些约束也不等于完整的语义真实性保证。
- **JobSpy**：版本 `10b5417c8f2c99a6159733cf0f52a06c96c3832d`。[README](https://github.com/speedyapply/JobSpy/blob/10b5417c8f2c99a6159733cf0f52a06c96c3832d/README.md)说明多来源岗位采集与 DataFrame 输出；本项目尚未集成该库。

- **OfferPilot**：此处特指 `offercontext/offerPilot`，版本 `c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac`；该名称存在多个独立项目，不据名字认定为同一仓库。[README](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/README.md)说明本地优先的求职工作台范围，也明确不自动投递或联系招聘方。[记录创建实现](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/src/offerpilot/repositories/application_creation.py)和[工具确认策略](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/src/offerpilot/ai/tool_specs/applications.py#L600-L678)支持其记录持久化与 Agent 写操作确认机制。AI 功能仍使用配置的模型服务，不能因“本地优先”就称所有处理都在本机。许可证为 [AGPLv3](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/LICENSE)，README 另说明 Live2D 资产许可。

本项目的工作规则也不证明事实卡本身真实，repo-check 不核实简历语义。未来若实际复用第三方代码或 Skill，应另行记录文件来源、版本、许可证及必要版权声明，不能以这张对比表代替来源审查。
