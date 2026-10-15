# Agent 3 数据交接契约

版本：1.0｜日期：2026-10-15｜状态：本地文件与 CLI 已实现，团队网络/API 投递待联调。

| 契约 | 方向 | Schema | 可执行示例 |
|---|---|---|---|
| `SelectedListingEvidence` | Agent 2 → Agent 3（可选） | [selected-listing-evidence.schema.json](../schemas/selected-listing-evidence.schema.json)（Agent 2 契约副本） | [selected-listing-evidence.json](../data/demo/selected-listing-evidence.json)（合成包副本） |
| `ContractReview` | Agent 3 → 租客/人工复核编排层 | [contract-review.schema.json](../schemas/contract-review.schema.json) | [risk.json](../reports/risk.json) |
| `ContractQuestionList` | Agent 3 → 租客 | [contract-question-list.schema.json](../schemas/contract-question-list.schema.json) | [risk-questions.questions.json](../reports/risk-questions.questions.json) |

输入 Schema 是 Agent 2 截至 2026-10-15 的字节一致副本，由 `handoff.validate_selection` 执行 JSON Schema Draft 2020-12 格式检查与身份/资格一致性检查。与 Agent 2 同仓库时测试会核对两份 Schema；独立交付时使用本目录副本。Agent 2 的用户确认标记是调用方声明，不是密码学证明；M3 也不能仅凭文件证明来源未被修改。正式跨进程投递还须由编排层提供鉴权、收件确认及共享存储。

`receive` 入口要求 `request_id`、显式合同处理同意、完整选房包、合同和固定 `as_of`。本地 SQLite 收据以请求 ID 为唯一键：相同输入重试返回首次 `ContractReview`，不同输入重用该 ID 返回 `duplicate_request_conflict`。`ContractReview.intake` 绑定选房批次/检查批次/偏好版本、房源 ID、选择时间、选房包 SHA-256、合同 SHA-256 与首次复核版本。跨机器的传输、身份鉴别与投递确认仍需团队编排层实现。

`SelectedListingEvidence` 的 `listing_snapshot` 是原始房源，不是 `state.selected` 的扁平对象。合同地址与 `listing_snapshot.address` 交叉核对；合同租金与 `listing_snapshot.rent_amount/rent_period/rent_scope/currency` 比较。`assessment.weekly_cost` 可能计入账单/费用，只用于推荐评分。`recommendation_run_id`、`selection_check_run_id`、`search_id`、`profile_version`、`listing_id`、`selected_at` 和字段 `evidence` 都保留在 `ContractReview.selection_evidence` 中，便于追溯。

`ContractReview` 有稳定 `review_id` 与递增 `version`。字段包含 `value/confidence/evidence`；发现包含 `id/code/severity/reason/evidence/rule_version/rule_url`。旧版本的字段与发现保存在 `revisions`；租客修正会使之前的问题清单失效。状态包括 `Awaiting Resubmission`、`Degraded Summary Only`、`Awaiting Human Review`、`Reviewed`、`Questions Ready`。高风险由人工决定后才能进入 Reviewed；缺少可用规则包时暂停结论。

`ContractQuestionList` 只从 Reviewed 版本生成，每个问题关联 `finding_id`、`review_version` 和原发现证据。无需要澄清的发现时返回空数组，不编造问题；可以本地编辑并导出，不自动联系房东或中介。输出的 `handoff_status=prepared_not_sent` 表示尚未投递给租客界面。

M4 只可将合同地址视作预填候选值；租客必须确认租约资料和退租日期后才能创建退租计划。当前代码没有自动 M3→M4 API。
