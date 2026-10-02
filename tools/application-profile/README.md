# 按需读取申请资料

这是一个只读的 Python 标准库工具。显式选择本地索引后，工具读取其中注册的模块，按逻辑路径返回选定字段；不联网、不填写浏览器、不修改档案，也不自动跟随正文中的文本引用。

[空白模板](../../templates/application-profile/README.md)用于建立自己的本地档案；[虚构示例](../../examples/application/profile/README.md)可直接用于演练。真实资料放在被 Git 忽略的 `private/` 或用户选择的仓库外位置。不要把真实资料写入模板、示例或测试。

## 最小调用

从仓库根目录运行：

```sh
python3 tools/application-profile/read.py --profile examples/application/profile/index.json check
python3 tools/application-profile/read.py --profile examples/application/profile/index.json context --kind full_time --language en
python3 tools/application-profile/read.py --profile examples/application/profile/index.json get 'education.example.name'
python3 tools/application-profile/read.py --profile examples/application/profile/index.json get-many 'education[0].degree' 'employment[0].description.en'
python3 tools/application-profile/read.py --profile examples/application/profile/index.json families
python3 tools/application-profile/read.py --profile examples/application/profile/index.json answers --problem-family self_evaluation
```

换成自己的档案时，显式传入实际索引路径。工具拒绝索引、模块及其父路径中的符号链接；在存在系统目录别名的机器上使用解析后的实际路径。

## 现有格式

索引和模块都使用 JSON 语法。扩展名可以是 `.json` 或包含 JSON 语法的 `.yaml`；不支持普通 YAML 缩进语法，也不需要 YAML 依赖。继续使用既有 `schema_version: 2`，没有新增档案协议：

- 索引的 `modules` 将模块 ID 映射到相对文件名，`aliases` 将别名映射到逻辑路径。
- 模块包含 `schema_version: 2` 和逻辑路径到值的 `entries`。
- `current_fill_index` 必须有 `required_refs`、`internship_refs` 数组，以及将 `zh`、`en` 映射到模块 ID 的 `language_modules`。
- 其他以 `_refs` 结尾的索引可以用数组或字典组织引用。模板不预置公司例外。
- 路径支持点号键、数字索引和 `[*]`，例如 `education[0].name`。父子条目可共存，最长路径优先；同深度的重叠条目、重复键、缺失引用、路径穿越和符号链接会报错。

模板中的 `fill_policy.mode: review_then_submit` 是执行模式，**不是具体岗位授权**。`status: NEEDS_CONFIRMATION`、空 `reuse_scope` 和空确认日期表示没有个人授权。用户负责注册、登录、密码和验证码。用户授权具体岗位后，执行者填写、独立审查者检查实际表单及附件；`REVIEW_PASS` 后由指定提交者提交，无须额外例行确认。实际工具的动作时确认要求仍然有效；显式“只填不提交”则采用 `fill_only`。档案命中不能产生授权。

## 命令与输出

| 命令 | 行为 |
| --- | --- |
| `check` | 校验模块、别名、索引及可识别的内部引用，只返回计数。 |
| `locate REF` | 返回模块相对路径、匹配条目和剩余路径，不返回个人值。 |
| `get REF` | 返回所选值及祖先元数据；近层元数据覆盖远层同名项。 |
| `get-many REF...` | 按输入顺序一次读取多个字段；默认单行 JSON，`--verbose` 可加定位信息。 |
| `families` | 只列出问题类别的键。 |
| `answers --problem-family KEY` | 读取该类别的候选答案并去重，始终标记 `candidate_only: true`。 |
| `context --kind full_time\|internship --language zh\|en` | 返回当前政策值和所选范围的事实、答案引用；不展开整份事实。 |

`context` 可加 `--company KEY`、`--problem-family KEY` 选择已有的索引项。实习模式追加实习政策，全职模式排除实习模块；两者只列所选语言模块，隐藏历史模块。政策值引用必须来自 `preferences` 或 `internship` 模块。实现会载入所有注册模块作结构解析，但只输出命令选定的值；它不是按文件延迟加载器。

`get` 和 `get-many` 读取历史模块或具有历史祖先的值时，必须显式加 `--include-history`。`answers`、`context` 不提供历史读取开关。`check`、`locate` 只定位引用，不受值读取限制。元数据包括状态、证据状态、记录 ID、复用范围、确认日期、刷新条件、来源和日期填写规则。

`get-many` 返回 `ok` 和 `results`。每个输入按从 0 开始的 `index` 对应一项；成功项有 `matches`，失败项只有不含输入值的 `error`。重复查询保留各自位置；一个通配符查询有任何失败时，该查询整项失败。全部成功退出 0；部分失败退出 2，但 stdout 仍保留独立成功项和错误项，调用者必须逐项检查。档案初始化失败则 stdout 为空，stderr 返回结构错误。

`Reference not found` 表示定位未完成，不代表用户没有这项事实。类别命中也不是适用性判定：执行者仍须核对实际问法、复用范围、刷新条件及当前用户更正。`check` 通过只证明结构和引用能解析，不证明资料完整、真实、当前有效或已经获得用户授权。工具不接收自然语言问题，不自动作出 Yes / No 决定。

## 验证

```sh
python3 -m unittest discover -s tools/application-profile/tests -v
```

测试只创建虚构资料；不读取本地生产档案。`test_answers.py` 中的确认记录仅用于检索回归测试，不是个人模板或任何真实申请的授权。程序测试不能证明 Agent 在真实表单中会正确判断所有适用范围。
