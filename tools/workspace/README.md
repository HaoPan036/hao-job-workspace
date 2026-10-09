# 初始化自己的工作区

从仓库根目录运行（Python 3.10+、Git，标准库）：

```sh
python3 tools/workspace/setup.py init --dry-run
python3 tools/workspace/setup.py init
python3 tools/workspace/setup.py check
```

`init` 只复制白名单里的缺失模板到 `private/`，不覆盖已有文件，不扫描或导入其他目录。默认建立：资料索引、空白申请档案、岗位搜索与来源配置、公司覆盖/行动/首页、空投递历史和待办。它不放入虚构成功事件，也不授权岗位、不联网、不建立定时任务。`--dry-run` 只预览路径，不创建文件夹或文件。

新目录会输出 `INIT_DONE created=17 kept=0`；重复运行为 `created=0 kept=17`。中途失败可查看错误后再次运行，已存在文件继续保留。目标必须是一个 Git 仓库根目录；所有目标文件必须被忽略且未跟踪，不能经符号链接写入其他位置。工具不替用户修改 `.gitignore`。

## 确认 private 被忽略

放入真实资料前，先确认 Git 会忽略 `private/`：

```sh
git check-ignore -v private/material-index.md
```

正常会看到下面的结果，行号可能不同：

```text
.gitignore:2:**/private/    private/material-index.md
```

没有输出时，先确认终端位于仓库根目录，且根目录 `.gitignore` 包含下面这行（覆盖任意深度的 `private/`），然后重新检查：

```gitignore
**/private/
```

仍无匹配时，用 `git ls-files -- private/material-index.md` 查看该文件是否已被跟踪。有输出时，`git rm --cached -- private/material-index.md` 只把它移出 Git 索引、保留本地文件，再重新检查；这不会删除已有提交历史中的内容。忽略检查通过前只用虚构资料。

## 填写哪些文件

| 位置（相对仓库根目录） | 怎么填写 |
|---|---|
| `private/material-index.md` | 本次要用的资料、简历、岗位要求和输出位置；保留原件 |
| `private/application-profile/index.json` 及模块 | 按[档案说明](../../templates/application-profile/README.md)填写；空白项保持待确认，不能编造 |
| `private/job-search/profile.json` | 方向、地区、求职限制；初始条件为空、写队列默认关闭 |
| `private/job-search/sources.json` | 按[采集说明](../job-radar/README.md)填写明确要读取的来源；默认没有启用来源 |
| `private/recruiting/config.json`、`history.md` | Singapore / Canada 是示例分类，按自己的地区调整配置和计数表，保留已有投递历史 |
| `private/job-search/current-actions.md`、`dashboard.md` | 当前要做的事；空模板不代表已经查过岗位 |

找岗位与投递同步共用 `private/recruiting/queue.md` 和 `history.md`。如改路径，要同时调整搜索 profile 与 recruiting config；`check` 会报告两边指向不一致。其他初始化文件位置固定；自定义更多目录时可直接使用各工具，不必改动已有资料来适配此入口。

`check` 复用档案结构检查和投递计数审计，检查默认文件是否齐全、资料引用能否解析、共用记录路径是否一致。空模板也能得到 `SETUP_CHECK_PASS`：它只表示结构能用，**不表示资料填完、经历真实、来源可抓取，或已授权投递**。检查只输出结构结果，不打印个人字段值。

已存在的配置不会因包升级而自动新增字段；遇到缺项时，对照模板按需补充，不重新覆盖个人配置。单元测试使用临时 Git 仓库和虚构数据：

```sh
python3 -m unittest discover -s tools/workspace/tests -v
```
