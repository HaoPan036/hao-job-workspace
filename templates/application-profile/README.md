# 本地申请资料模板

这里是一组空白 JSON 模板，沿用 `schema_version: 2` 的索引和模块格式。字段尚未确认，教育和工作经历为空，答案与时间为 `null`。结构校验通过不代表资料已准备好。

在仓库根目录将整个模板目录复制到一个尚不存在的、被 Git 忽略的本地位置：

```sh
python3 -c 'from pathlib import Path; import shutil; target=Path("private/application-profile"); target.parent.mkdir(parents=True, exist_ok=True); shutil.copytree("templates/application-profile", target)'
python3 tools/application-profile/read.py --profile private/application-profile/index.json check
```

`copytree` 在目标已存在时退出，不覆盖已有个人资料。命令只复制包内空白模板，不读取旧档案。之后只编辑本地副本：在 `facts.json` 填入本人确认的记录，在 `answers.json` 填入确切答案及复用条件，在 `zh.json`／`en.json` 填入相应文字；不确定的值继续保留为空。参考[虚构示例](../../examples/application/profile/README.md)理解路径、别名和分离的正文引用。

`preferences.json` 默认没有任何个人授权。`review_then_submit` 只是执行模式，不授权开始填表；用户授权具体岗位后，执行者填写，独立审查者核对实际表单与附件，`REVIEW_PASS` 后由指定提交者提交，无须额外例行确认。实际工具的动作时确认要求仍然有效；显式“只填不提交”则使用 `fill_only`。注册、登录、密码与验证码由用户处理。不要把示例答案或测试中的 `CONFIRMED_REUSABLE` 复制成自己的确认记录。

[工具说明](../../tools/application-profile/README.md)包含命令、历史读取边界和输出失败处理。
