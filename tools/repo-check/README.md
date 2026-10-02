# 公开副本检查

需要 Python 3.10+ 和 Git，无第三方 Python 包。此工具由现有仓库检查器抽取，检查范围改为公开包的全部 Markdown 和全部待分发文本。

在独立发行副本根目录运行；解压副本若尚无 Git 仓库，先执行 `git init`。不要在私人母仓库的嵌套目录里运行本工具。

```sh
python3 tools/repo-check/check.py
python3 tools/repo-check/check.py --staged
python3 -m unittest discover -s tools/repo-check/tests -v
```

检查包括本地链接、Skill 元数据、根与嵌套 private/Obsidian 状态忽略规则、凭据及个人联系方式模式、Git 空白错误。默认检查工作树；`--staged` 检查索引版本。两种模式都会扫描该视图中的全部公开文本，不只扫描最近改动。工具不读取 private 文件内容。

程序只输出文件、行号与命中类别，不输出敏感原文。二进制或非 UTF-8 文件会报告未扫描，发布前需要单独审阅。它不能识别任意个人姓名、公司信息或证明事实真实；发布者还须对实际白名单副本做个人残留扫描和内容审阅。它不核实简历语义、不检查招聘网站、不上传数据，也不阻止用户绕过检查手工推送。
