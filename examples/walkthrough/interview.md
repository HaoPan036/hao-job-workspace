# 当前面试回答：中英文

仅供本虚构练习。两种语言都依据补充资料后的事实，不把 [岗位要求](target-role.md) 当成个人经历。

## 讲一个你处理失败分支的例子

> 这个练习脚本在首次超时后已经会重试一次，但重试仍超时后缺少明确的停止条件。我的工作是阅读已有逻辑，补充停止条件，并增加相关测试。练习记录中，首次执行和一次重试都超时，之后流程停止，没有继续尝试。这个结果说明本例执行到了停止分支，超时根因还没有解决。我没有实现原有的重试机制，也没有性能提升的测量结果。

依据：[CLM-WALK-OWN-001](fact-card.md#职责clm-walk-own-001)、[CLM-WALK-OUT-001](fact-card.md#结果clm-walk-out-001)。

## Describe a time you worked on a failure path

> The exercise script already retried once after the initial timeout, but it lacked an explicit stop condition if the retry also timed out. I reviewed the existing logic, added the stop condition, and wrote related tests. In the exercise record, both the initial attempt and the retry timed out, and the flow then stopped without another attempt. This shows that the stop branch was reached in this example; the underlying timeout cause remains unresolved. I did not implement the original retry mechanism or measure a performance improvement.

Sources: [CLM-WALK-OWN-001](fact-card.md#职责clm-walk-own-001), [CLM-WALK-OUT-001](fact-card.md#结果clm-walk-out-001).

## 如果被问到 Kubernetes

> 这个练习没有使用 Kubernetes，我不能把它作为相关实战经验。这里能够具体说明的是 Python 失败处理和测试；对于 Kubernetes，我需要补充学习和独立练习。

> I did not use Kubernetes in this exercise. I can discuss the Python failure handling and tests I worked on, but I would need further study and separate practice with Kubernetes.

依据 / Source：[CLM-WALK-USE-001](fact-card.md#技术范围clm-walk-use-001)。

## 练习时检查

追问“重试机制原来就有吗？”时，回答应与当前职责一致。追问“提高了多少？”时，说明没有测量结果，不把待核实比例当成成绩。反馈和旧草稿见 [feedback.md](feedback.md)。
