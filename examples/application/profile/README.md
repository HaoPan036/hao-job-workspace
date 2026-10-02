# 虚构档案演练

所有学校、公司、经历和文本都是虚构示例，不能用于真实投递。确认日期为空，政策保持 `NEEDS_CONFIRMATION`，没有授权浏览器或账号操作。

从仓库根目录运行：

```sh
python3 tools/application-profile/read.py --profile examples/application/profile/index.json check
python3 tools/application-profile/read.py --profile examples/application/profile/index.json locate 'education.example.name'
python3 tools/application-profile/read.py --profile examples/application/profile/index.json get-many 'education.example.name' 'employment[0].description.en'
python3 tools/application-profile/read.py --profile examples/application/profile/index.json answers --problem-family self_evaluation
python3 tools/application-profile/read.py --profile examples/application/profile/index.json get 'history.old' --include-history
```

预期结果：结构检查返回 `ok: true`；别名定位到 `education[0].name`；两项批量查询保留顺序；答案返回 `candidate_only: true` 和 `FICTIONAL` 状态。历史读取去掉 `--include-history` 后会退出 2，这是预期的访问限制。

在[空白模板](../../../templates/application-profile/README.md)基础上创建自己的本地副本，不要把这里的虚构内容当作用户事实。[工具说明](../../../tools/application-profile/README.md)解释索引及引用行为。
