# M3 → M4 交接包（待双方联调确认）

日期：2026-10-17。范围：课程原型的本地 JSON/CLI 交接；当前没有自动投递给 M4 的 API。本文件是 M3 提供给 M4 队员的接口提案，不表示双方已经完成联调。

## 先用这三份样例

| 场景 | M3 输出 | M4 预期 |
|---|---|---|
| 正常复核 | [`scrum25-agent2-receive-2026-10-17.json`](../reports/scrum25-agent2-receive-2026-10-17.json)（对应 [Markdown](../reports/scrum25-agent2-receive-2026-10-17.md)） | 读取候选合同字段；等待租客确认实际租约后才执行 `create` |
| 需要人工复核 | [`m3-m4-human-review-2026-10-17.json`](../reports/m3-m4-human-review-2026-10-17.json)（对应 [Markdown](../reports/m3-m4-human-review-2026-10-17.md)） | 暂停创建，显示复核原因；保留与正常样例相同的选房批次引用 |
| 版本变化 | [`m3-m4-corrected-v2.json`](../reports/m3-m4-corrected-v2.json)（对应 [Markdown](../reports/m3-m4-corrected-v2.md)） | 同一 `review_id`、`version=2`；发现旧版本后重新核对候选信息和租客确认 |

三份文件均为**合成数据**。正常样例来自已验证的 Agent 2 → Agent 3 `receive`；人工复核样例用同一份 Agent 2 选房包和风险合同调用 `receive` 生成；v2 样例由本目录的 `correct` 命令和 [`m3-m4-tenant-correction.json`](../data/demo/m3-m4-tenant-correction.json) 生成。人工复核样例是独立场景，不是正常样例的后续版本。

## 交接字段

M3 向 M4 交付完整的 `ContractReview` JSON，格式以 [`contract-review.schema.json`](../schemas/contract-review.schema.json) 为准。M4 读取当前顶层版本，不从 `revisions` 中挑旧值。

| M3 字段 | 给 M4 的用途 | 注意 |
|---|---|---|
| `review_id`, `version`, `status`, `updated_at` | 识别复核及其当前版本、决定是否进入确认流程 | `review_id` 稳定；租客修正会提高 `version` |
| `fields.address.value` | 预填地址 | 必须由租客核对；空值不能创建已确认租约 |
| `fields.tenant.value` | 显示合同里的租客姓名 | 不是 M4 的 `tenant_id` 或已认证用户身份 |
| `fields.start_date.value`, `fields.end_date.value` | 显示合同租期，供租客核对 | M4 `TenancyRecord` 当前没有对应字段；双方需决定是否扩展或另存 |
| `fields.rent_amount.value`, `fields.rent_period.value`, `fields.rent_scope.value`, `fields.currency.value`, `fields.bond.value` | 显示合同金额及计价口径 | 合同押金金额不是已付款凭证；不要由此激活押金流程 |
| `fields.signed_date.value` | 显示合同提取出的签署日期 | 不能仅凭提取结果证明双方已经签署 |
| `fields.*.evidence`, `document.sha256`, `findings`, `human_review` | 字段出处、合同版本和风险解释 | 发现待人工处理时暂停自动创建 |
| `intake.search_id`, `intake.listing_id`, `intake.profile_version`, `intake.recommendation_run_id`, `intake.selection_check_run_id`, `intake.selection_sha256`, `intake.document_sha256` | 追溯 Agent 2 选房包与合同 | `intake` 对普通 `review` 输出可缺省；`listing_id` 不是 `tenancy_id` |

`selection_evidence.user_confirmed` 只表示上游选房确认，`consented_at` 只表示合同处理同意；二者都不是 M4 所需的实际租约确认。正常样例的上游 `rental_mode=private_room`，不能自动填成 M4 目前唯一支持的 `tenancy_type=standard_residential`。

## 上游已有的身份与案例上下文

[`integration/agent1-to-agent2/handoff.json`](../../integration/agent1-to-agent2/handoff.json) 的外层协调样例已经有 `caseId=DEMO-CASE-INTEGRATION-001` 和 `confirmation.confirmedBy=DEMO-TENANT-001`。它们没有进入当前 M2 的严格 `SelectedListingEvidence` 正文，因此 M3 的正常复核报告也没有这两项。协调层应保留这份上下文并随 M3 结果交给 M4，不能仅凭下游正文缺字段就重新生成用户或全流程案例身份。

| M4 需要的 ID | 上游现状及建议 |
|---|---|
| `tenant_id` | 使用可信用户身份/会话中的稳定 ID。`confirmedBy` 是当前演示里的候选关联标识；真实接入前须验证它与会话租客相同。M1 消费用户身份，不能由 LLM 编造用户 ID。 |
| `case_id` | 上游已有租房案例 `caseId`。若 M4 的案件与全流程租房案例定义一致，显式映射并复用；若 M4 定义独立的善后案件，则保存两者关联，由 M4/协调层创建善后案件 ID。 |
| `tenancy_id` | 当前 M1 → M2 外层样例与 M2 → M3 正文都没有。实际租约确认并登记时由租约存储/协调层生成，已有租约记录则复用；不能从房源 ID 或合同复核 ID 推导成已确认租约。 |

拟议的交接应同时携带“可信业务上下文”和原样的 `ContractReview`，由协调层校验归属后交给 M4 适配器。上下文保存在外层，不直接追加到严格的 M2/M3 正文 Schema。当前外层传递及 M4 适配仍待实现，已有演示确认也不构成真实鉴权。

## M4 创建前必须另行取得的信息

M4 当前 [`TenancyRecord`](../../agent4/schemas/tenancy-record.schema.json) 的 `create` 需要租客确认后的 `tenancy_id`、`tenant_id`、地址、`jurisdiction=NSW`、`tenancy_type=standard_residential`、`confirmed=true`、来源引用和版本、房间/地毯/户外/家具属性、家具清单及基线证据引用。部分属性允许 `null` 或空列表，但应真实表达“未知”，不能把 M3 提取结果冒充租客确认。`case_id`、`actor_id`、`request_id`、`expected_version`、`as_of` 属于 M4 命令外壳，也由 M4/编排层提供。

建议 M4 在独立的租客确认步骤中收集这些数据。`tenancy.source_ref/source_version` 指向该确认记录；如需在 M4 里保留 M3 来源，可登记一条 `kind=other` 的 `EvidenceReference`，其 `source_ref=review_id`、`source_version=version`，并在 `summary` 中说明“合同复核候选信息，非签署证明”。具体存法请 M4 队员确认。基线状况报告、押金支付记录和退租日期需要各自的用户输入或证据；`create_plan` 还要求 `move_out_date` 与 `schedule_confirmed`。

## 状态与重试约定（提案）

- `Reviewed`：允许显示 M3 候选字段，随后进行独立的租客确认；不自动执行 M4 `create`。
- `Awaiting Human Review`、`Awaiting Resubmission`、`Degraded Summary Only`：暂停 M4 创建，并显示当前状态/原因。
- `Questions Ready`：问题清单可能仍待租客处理；双方需决定何时允许进入 M4 确认，当前先暂停自动创建。
- 同一 `review_id` 出现更高 `version` 时，M4 要重新读取当前字段，并使基于旧版本的未完成确认失效。重复收到同一版本应得到同一处理结果。
- M3 `intake.request_id` 可包含 `:` 且最长 128 字符；M4 `request_id` 仅允许字母、数字、点、下划线、连字符，最长 80 字符。M4/编排层应生成稳定且符合自身规则的请求 ID；重试时原样复用整份 M4 命令，同 ID 内容变化会报 `request_conflict`。

## 分工和联调完成条件

**M3 队员（我）**：维护本交接说明、`ContractReview` Schema 和三份样例；解释每个字段的来源与状态；在字段不匹配时调整 M3 的明确输出问题。

**M4 队员**：确认所需的用户确认字段和可接受状态；实现 M3 JSON 到 M4 `create` 的适配与来源保存；为缺失确认、人工复核、版本变化和重复请求返回可识别结果；在单独确认退租日期后调用 `create_plan`。

**共同验证**：正常接收、同一版本重复接收、缺少租客确认、`Awaiting Human Review`、同一 `review_id` 的新版输入。记录每次输入文件、命令、M4 结果、案件 ID/版本和是否发生重复创建。联调完成后再把本文件中的提案改成双方确认的契约。

## 请 M4 队员确认的四点

1. 如何保留上游 `caseId` 与确认者关联？M4 `case_id` 是否复用全流程案例，`tenant_id` 如何从可信会话取得，以及租约确认后由哪一层登记 `tenancy_id`？
2. `TenancyRecord.source_ref/source_version` 指向租客确认记录是否合适？M3 `review_id/version` 保存在 `EvidenceReference` 是否足够？
3. M4 是否只接受 `Reviewed`，以及 `Questions Ready` 何时可进入租客确认？
4. M4 还需要哪些 M3 字段或异常码？合同租期是否要进入 M4 数据模型？
