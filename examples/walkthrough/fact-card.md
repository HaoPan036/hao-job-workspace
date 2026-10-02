# 当前事实卡

以下 `verified` 只表示与本例的虚构来源一致，不证明使用者具有这些经历。正式材料仍必须受 `allowed_use` 和证据范围约束。

## 职责：CLM-WALK-OWN-001

```yaml
evidence_bundle:
  claim_id: CLM-WALK-OWN-001
  claim_text: "参与者为已有 Python 脚本补充重试仍超时后的停止条件和相关测试；重试机制原本已存在。"
  claim_type: ownership
  evidence_status: verified
  source:
    - "source.md#资料-b补充记录2025-01-11"
  scope: "仅限本例虚构脚本中的停止条件与相关测试。"
  date: "2025-01-11"
  ownership: "补充停止条件与相关测试，没有实现原有重试机制。"
  allowed_use:
    - "本例中英文简历练习"
    - "本例中英文面试练习"
  limitations:
    - "不能将原有重试机制或整个系统归为个人成果。"
    - "没有超时根因修复或生产部署的依据。"
```

该 ID 在资料 A 阶段对应的职责仍为 `provisional`；资料 B 解决冲突后，保留 ID、收窄说法并核实当前范围。需要复查的引用位于 [resume.md](resume.md)、[interview.md](interview.md)；不可再用的旧稿保留在 [feedback.md](feedback.md)。这里靠显式引用查找和人工复查，不会自动更新其他文件。

## 结果：CLM-WALK-OUT-001

```yaml
evidence_bundle:
  claim_id: CLM-WALK-OUT-001
  claim_text: "本例首次执行超时，重试一次仍超时，随后停止；超时根因没有解决。"
  claim_type: outcome
  evidence_status: verified
  source:
    - "source.md#行为记录"
    - "source.md#资料-b补充记录2025-01-11"
  scope: "仅限本例预写的虚构行为记录。"
  date: "2025-01-11"
  ownership: "参与者补充停止条件与测试，不据此推断拥有全部执行逻辑。"
  allowed_use:
    - "本例中英文简历练习"
    - "本例中英文面试练习"
  limitations:
    - "不是实际运行报告，不支持性能提升、生产可靠性或超时修复结论。"
```

## 技术范围：CLM-WALK-USE-001

```yaml
evidence_bundle:
  claim_id: CLM-WALK-USE-001
  claim_text: "参与者在本例使用 Python 修改脚本并编写相关测试，没有使用 Kubernetes。"
  claim_type: usage
  evidence_status: verified
  source:
    - "source.md#技术范围"
    - "source.md#资料-b补充记录2025-01-11"
  scope: "仅限本例虚构练习，不代表其他项目或个人的技术范围。"
  date: "2025-01-11"
  ownership: "Python 停止条件与相关测试。"
  allowed_use:
    - "本例中英文简历练习"
    - "本例面试中的经验与学习需求区分"
  limitations:
    - "岗位要求出现某项技术，不构成参与者用过该技术的证据。"
```

## 待核实指标：CLM-WALK-METRIC-001

```yaml
evidence_bundle:
  claim_id: CLM-WALK-METRIC-001
  claim_text: "参与者在初始自述中猜测性能提升 30%；该比例没有测量依据。"
  claim_type: metric
  evidence_status: unverified
  source:
    - "source.md#参与者自述"
    - "source.md#资料-b补充记录2025-01-11"
  scope: "仅记录本例待核实的猜测。"
  date: "2025-01-11"
  ownership: "参与者自述，没有可归属的测量工作。"
  allowed_use:
    - "核实待办和练习反馈"
  limitations:
    - "禁止进入正式简历和作为成绩陈述的面试答案。"
    - "缺少性能指标定义、基线或分母、样本、时间窗口和测量来源。"
    - "重复自述、补全字段或改写措辞不能使该指标变为 verified。"
```

五种现有状态仍为 `verified`、`provisional`、`planned`、`retired`、`unverified`。本例没有计划或撤回项，不为展示状态而添加经历。`provisional` 必须保留条件与限制；`planned` 不能写成已完成；`retired` 不可自动复用；`unverified` 不进入正式材料。若新来源仍无法解决冲突，保持 `provisional` 或 `unverified`，在工作笔记标记 `reconciliation_required`，不挑选更好听的版本。
