# M3 参考与 M4 消费端合成输入

原始三份 ContractReview 按字节复制自 M3 PR #3 分支 `codex/m3-m4-handoff-20261017`，commit `a4d9f2ed85f82d65310e15954d54c1849729b9b0`：

| 本目录文件 | 原 agent3/reports 文件 |
|---|---|
| normal-review.json | scrum25-agent2-receive-2026-10-17.json |
| human-review.json | m3-m4-human-review-2026-10-17.json |
| corrected-v2-review.json | m3-m4-corrected-v2.json |

`normal-confirmation-stub-packet.json` 中的 **confirmation 是 M4 测试替身**，不是 M3 已实现的确认接口输出，也不表示真实用户签约。confirmed_fields 的合同事实来自原复核快照；NSW/standard_residential 是测试中单独声明的实际类型，不是从 private_room 自动映射。房间/家具信息保留未知。

`missing-confirmation-packet.json`、`human-review-packet.json`、`v2-old-confirmation-packet.json` 分别覆盖缺确认、人工复核、v2 配旧确认。三份原始 review 均没有实际租约确认，单独使用不能创建 M4 租约。

固定模拟确认时间 2026-10-17 19:00 +11:00、接收时间 19:01 +11:00 是可复现测试时钟，非实际运行时间。完整契约与待对齐字段见 `agent4/docs/m3-m4-receive.zh-CN.md`。
