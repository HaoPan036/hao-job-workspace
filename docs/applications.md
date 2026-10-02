# 从授权岗位到保存投递结果

先跑一次[虚构模拟申请](../examples/application/README.md)，确认宿主可以操作浏览器、交给独立 Agent 审查，并读取本地文件。不要第一次就用真实简历试工具。

## 准备自己的资料

只提供本次申请需要的资料和确认过的简历。简历可以是已制作好的 PDF；归档工具保存原字节，不负责编辑、提取或检查 PDF 排版。真实资料放入已确认被 Git 忽略、未跟踪的 `private/`，保留原件。

经常填写相同信息时，可以从[资料模板](../templates/application-profile/README.md)复制一份结构化档案，逐项填自己的信息。可以先用[虚构档案](../examples/application/profile/README.md)试读取。模板中没有维护者的个人授权、账号规则或公司例外；执行模式 `review_then_submit` 只说明授权后怎样处理，不能替代具体岗位授权。

从仓库根目录初始化空白记录（已有记录不覆盖）：

```sh
mkdir -p private/recruiting
cp -n templates/recruiting/config.example.json private/recruiting/config.json
cp -n templates/recruiting/history.md private/recruiting/history.md
cp -n templates/recruiting/queue.md private/recruiting/queue.md
git check-ignore -v private/recruiting/config.json private/recruiting/history.md private/recruiting/queue.md
python3 tools/recruiting-sync/sync.py audit
```

首次使用前按[同步工具说明](../tools/recruiting-sync/README.md)修改配置中的地区和表头。上面复制的是空记录与虚构地区配置，不是你的历史。不要把模板中的成功事件放进真实台账。

## 让 AI 执行

把官网链接、岗位 ID、批准的资料与附件告诉 Codex，明确“我授权投递这个岗位”。它先核对是否已经投过，然后检查材料、填表和上传。注册、登录和未确认的必填问题需要你接手时，它应保留页面并说明缺什么。

填写者随后停止操作，由另一个 Agent 读取实际页面、字段、声明和附件，核对与授权和资料是否一致。通过后由审查者点击 Submit 一次；这一步不再增加例行人工确认。工具本身要求当次确认时仍遵守要求。无法安排独立审查时保留草稿，不能用填写者自审代替。

招聘网站上有些保存、填写、上传操作会立即发送数据，不是只有 Submit 才会发送。[数据去向](privacy-and-data-flow.md)和[附件路线](supported-environments.md#附件路线)分别说明处理边界。

## 看结果与找回材料

- 网站明确成功后，Agent 通过[同步工具](../tools/recruiting-sync/README.md)更新历史、待办和计数，再用[归档工具](../tools/application-record/README.md)保存当时的简历与普通项目回答。实习和全职分别计数。
- 页面超时、转圈或无法确定结果时，不重试提交，不计成功。先保留页面和现有证据，核对该申请状态。
- 网站成功而本地写入失败时，只修复记录。归档失败单独报告，不再提交。
- 面试前可以说：“找出这个岗位当时投的简历，按那份版本准备项目介绍。”Agent 根据申请记录中的材料 ID 和哈希找到原件，不把后来修改的简历当成历史版本。

代码能检查哈希、字段、重复和统计是否一致，不能证明输入的经历或成功证据真实。事实核对、授权与独立审查仍是 Agent 必须遵守的工作规则。
