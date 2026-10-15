# 悉尼租房评估报告（模拟数据）

> 仅供课程演示；房源、通勤、设施和证据全部虚构，不可据此租房或签约。

评估快照：2026-09-17T09:00:00+10:00；评分版本：rules-1.0；偏好版本：1。

推荐批次 ID：rr-3148921b0c4fd38aeec972f51db964f6d8fd1974c7c98ef843f13c4001ee57a5

## 需求与结果概况

预算：AUD 450–550/周，计价对象 per&#95;person；含账单口径：True。

目的地：demo-usyd；到达时段：09:00；期望/上限通勤：25/40 分钟。

权重：通勤 35.0%、费用 30.0%、居住 20.0%、便利 15.0%。

数量：input=1；eligible=0；pending=1；excluded=0；duplicates=0。

## Top 5 推荐

| 排名 | 房源 | 可比周费用 AUD | 模拟通勤/分钟 | 超市直线距离/米 | 通勤/费用/居住/便利分 | 总分 |
|---|---|---:|---:|---:|---|---:|

没有满足完整条件的候选；未自动放宽预算、通勤或其他要求。

## 待确认（不进入正式排名）

| 房源 | 分数可能范围 | 已知评分权重比例 | 硬条件待确认项 / 信息问题 |
|---|---|---:|---|
| AC-A | 88.60–88.60 | 100% | permission: 数据使用权限须明确 |

区间仅反映缺失评分项的可能贡献，不是统计置信区间；已知权重比例也不是可信概率。

## 排除

| 房源 | 已知不满足的条件 |
|---|---|

## 重复记录

无。

## 需要确认的问题

- 仅有 0 套符合完整条件；请确认待补信息，或由 Agent 1 询问是否调整指定条件。未自动放宽条件。
- 请逐项确认待确认清单中的未知、过期或冲突字段，再重新评估。

## 模拟证据索引

fixture: 是本地模拟记录定位符，不是真实网页。每个已使用字段的观测时间和来源也保存在同名 JSON 报告的 evidence_refs 中。

| 房源 | 已使用的字段证据 |
|---|---|
| AC-A | fixture:AC-A&#35;available&#95;from；fixture:AC-A&#35;bills&#95;included；fixture:AC-A&#35;commute；fixture:AC-A&#35;currency；fixture:AC-A&#35;furnished；fixture:AC-A&#35;last&#95;checked&#95;at；fixture:AC-A&#35;latest&#95;start&#95;date；fixture:AC-A&#35;listing&#95;status；fixture:AC-A&#35;location&#95;precision；fixture:AC-A&#35;mandatory&#95;fees&#95;weekly；fixture:AC-A&#35;minimum&#95;lease&#95;months；fixture:AC-A&#35;private&#95;bathroom；fixture:AC-A&#35;private&#95;bedroom；fixture:AC-A&#35;rent&#95;amount；fixture:AC-A&#35;rent&#95;period；fixture:AC-A&#35;rent&#95;scope；fixture:AC-A&#35;rental&#95;mode；fixture:AC-A&#35;source&#95;permission；fixture:AC-A&#35;supermarket&#95;distance&#95;m |

## 数据限制

- 全部房源、路线、设施和证据均为模拟数据，不可用于真实租房决策。
- 本原型仅为 Agent 2 的确定性工具核心，未接入 LLM、房源平台或 TfNSW。
- as&#95;of 是输入快照时点，不代表今天仍可租；分数是偏好匹配，不是房屋安全或签约保证。
- 不支持自动换汇、按人数分摊、真实市场租金估值或未来班次保证。
