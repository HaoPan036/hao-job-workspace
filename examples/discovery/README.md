# Fictional discovery fixtures

这些文件是手工构造的公开虚构响应，用于检查迁移后的解析器；公司、职位和链接均不是真实招聘资料。`sources.fixture.json` 使用原 sources 列表，额外的 `fixture_path` 和 `detail_fixtures` 只供离线检查读取。

从仓库根目录运行：

```bash
python3 tools/job-radar/collect.py --profile templates/job-search/profile.example.json --fixtures examples/discovery/sources.fixture.json --dry-run
```

应显示 11 条候选、0 个错误，所有候选均等待人工/Agent 官方核验；不联网、不生成目录或运行文件，也不写队列。两个同名 Ashby 职位拥有不同 requisition ID，应分别保留。

样例覆盖 HTML 列表和详情、RSS、Atom、Ashby、Greenhouse、Lever、MyCareersFuture、Baidu 内嵌列表、Sogou WeChat 结果以及 portal/manual 行为。`python3 -m unittest discover -s tools/job-radar/tests -v` 还会把虚构输入复制到临时目录，验证持久化、同日/次日去重、来源失败隔离、隐私路径和只读边界。

正常持久化不应使用公开 fixture 文件作为私人运行配置；测试在临时目录里完成。真实采集使用私人 `sources.json` 和显式 `--sources`；该入口即使附带 `--dry-run` 仍可能联网。这里的检查不证明真实网站可用、后台任务已启用、跨宿主可用或陌生人已经跑通。
