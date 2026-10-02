# 虚构超时案例：参考结果

这是对[虚构记录](source.md)的参考整理，不是真实经历、程序测试结果或实际核验报告。

## 实际结果

```yaml
evidence_bundle:
  claim_id: CLM-TIMEOUT-001
  claim_text: "虚构练习程序首次执行超时，重试仍超时，随后按规则停止。"
  claim_type: outcome
  evidence_status: verified
  source:
    - "source.md#execution-record"
  scope: "仅限本例的虚构执行记录。"
  date: unknown
  ownership: ""
  allowed_use:
    - "虚构简历示例"
    - "虚构面试练习"
  limitations:
    - "未解决超时原因，没有性能改善的依据。"
```

## 个人职责

```yaml
evidence_bundle:
  claim_id: CLM-TIMEOUT-002
  claim_text: "虚构参与者负责实现练习程序的重试和停止规则。"
  claim_type: ownership
  evidence_status: verified
  source:
    - "source.md#execution-record"
  scope: "仅限虚构背景设定的职责。"
  date: unknown
  ownership: "实现重试和停止规则。"
  allowed_use:
    - "虚构简历示例"
    - "虚构面试练习"
  limitations:
    - "职责来自背景设定，不能只凭执行记录推断作者。"
```

这里的 verified 表示参考答案与虚构输入一致，不表示任何使用者具备这段经历。换成个人资料时，仍须按自己的来源核实。

## 简历表述示范

> 为练习程序实现有限重试和停止规则，在首次执行与重试均超时后停止本轮执行。

## 面试回答示范

> 我负责实现练习程序中的重试和停止规则。第一次执行超时后，程序重试了一次，但仍然超时，于是按规则停止。这说明失败处理流程执行到了停止条件；超时原因还需要继续排查，不能说已经修复性能问题。

两段表述分别依赖执行结果与个人职责，不能用一项替代另一项。示例不要求用户手动学习多个 Skill 入口。

## 一个检查

对照原始记录检查：“解决了性能问题”有没有依据？正确结论是没有，因为最终结果仍为超时。无论 Agent 怎样措辞，都要保留这个结果和责任范围。

这是来源对照与语义审阅，不是自动 lint 报告。
