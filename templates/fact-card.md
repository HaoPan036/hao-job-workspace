# 项目事实模板

将模板放入自己的资料库，按已有经历和来源填写。每项可以分别核实的职责、实现、使用范围或结果单独记录；没有依据时保留未知。

以下沿用现有 Evidence Bundle 字段，不定义新格式或新的状态流转：

```yaml
evidence_bundle:
  claim_id: ""
  claim_text: ""
  claim_type: implementation
  evidence_status: unverified
  source: []
  scope: ""
  date: unknown
  ownership: ""
  allowed_use: []
  limitations: []
```

- claim_id 用于稳定识别和引用这项说法；claim_text 写具体内容。
- claim_type 区分 implementation、ownership、usage、outcome、metric、plan。
- evidence_status 沿用 verified、provisional、planned、retired、unverified；不要因为填写完整就变成已核实。
- source 写可查找的资料位置；scope、ownership 和 limitations 交代适用范围、个人责任及限制。
- allowed_use 记录已允许使用的场景。部分有依据的内容保留原有限制；计划不能写成已完成，撤回内容不能自动恢复。

## 准备笔记

项目背景、关键取舍、可能的追问和练习反馈可以写在这里。通用知识与个人经历分开，不把待学习的内容写成自己做过的工作。
