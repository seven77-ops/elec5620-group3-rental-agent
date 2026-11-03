# M3 → M4 交接包（待双方联调确认）

日期：2026-10-17。范围：课程原型的本地 JSON/CLI 交接；当前没有自动投递给 M4 的 API。本文件是 M3 提供给 M4 队员的接口提案，不表示双方已经完成联调。**用户确认实际租约信息纳入 M3 的下一步开发职责；本节描述的确认入口、确认记录与租约登记尚未实现。**

2026-10-20 补充：以下 `snapshot_revision` 为 M3 侧明确提出的生成与传递约定；当前 M3/M4 分支尚未实现该字段，需同步双方 Schema、持久化入口及样例后联调。

## 先用这三份样例

| 场景 | M3 输出 | M4 预期 |
|---|---|---|
| 正常复核 | [`scrum25-agent2-receive-2026-10-17.json`](../reports/scrum25-agent2-receive-2026-10-17.json)（对应 [Markdown](../reports/scrum25-agent2-receive-2026-10-17.md)） | 读取候选合同字段；另收到 M3 保存的有效租客确认记录后才执行 `create` |
| 需要人工复核 | [`m3-m4-human-review-2026-10-17.json`](../reports/m3-m4-human-review-2026-10-17.json)（对应 [Markdown](../reports/m3-m4-human-review-2026-10-17.md)） | 暂停创建，显示复核原因；保留与正常样例相同的选房批次引用 |
| 版本变化 | [`m3-m4-corrected-v2.json`](../reports/m3-m4-corrected-v2.json)（对应 [Markdown](../reports/m3-m4-corrected-v2.md)） | 同一 `review_id`、`version=2`；发现旧版本后重新核对候选信息和租客确认 |

三份文件均为**合成数据**。正常样例来自已验证的 Agent 2 → Agent 3 `receive`；人工复核样例用同一份 Agent 2 选房包和风险合同调用 `receive` 生成；v2 样例由本目录的 `correct` 命令和 [`m3-m4-tenant-correction.json`](../data/demo/m3-m4-tenant-correction.json) 生成。人工复核样例是独立场景，不是正常样例的后续版本。

这些样例只覆盖 `ContractReview`，均未附实际租约确认记录，因此目前都不能单独作为 M4 创建已确认租约的完整输入。

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

## M3：用户确认实际租约信息（待实现）

该步骤由 **M3 收集并保存确认，M4 验证并消费确认结果**。确认应发生在合同复核完成后、向 M4 创建租约记录前。

1. M3 展示当前 `ContractReview` 的地址、租客、出租方、租金及周期/计价口径、押金、起止日期和签署日期，并显示缺失项与复核结果。默认仅从 `Reviewed` 进入确认；其他状态按下文门禁处理。
2. 用户核对原合同。需要修改字段时先走已有 `correct` 流程，使用重新复核后的最新版本；必需事实缺失或存在未处理风险时暂停确认。
3. 用户明确声明“这是我实际签订的租约，已核对所展示的信息”，并确认实际租赁类型和辖区。M3 保存的是该用户声明及来源，不能据此宣称系统独立验证了签名或付款。合同处理同意、选房确认和人工风险放行均不能代替此操作。
4. M3/协调层将确认记录持久化，成功后才交接。已有实际租约登记时复用 `tenancy_id`；新租约在确认并登记时由租约存储/协调层分配。租客和案例 ID 继续沿用可信上游上下文。
5. M3 向 M4 交付“业务上下文 + 当前 `ContractReview` + 租约确认记录”。M4 验证身份归属、版本及指纹后创建租约记录，再收集退租所需的其他资料。

拟新增独立的 `TenancyConfirmation` 记录，以下为**待实现的数据约定，尚无可运行 Schema 或 CLI**：

| 字段 | 含义 |
|---|---|
| `confirmation_id`, `confirmation_version` | 稳定确认记录 ID 与确认修订版本 |
| `tenant_id`, `case_id`, `tenancy_id` | 绑定租客、全流程案例及已登记租约；如 M4 使用独立案件 ID，另存案例映射 |
| `confirmed_by`, `confirmed_at` | 从可信用户会话取得的确认人及带时区的确认时间；演示阶段明确标为模拟身份 |
| `review_id`, `review_version`, `document_sha256` | 绑定用户实际核对的复核版本与合同文件 |
| `review_snapshot_revision`, `review_sha256` | 分别匹配当前 `ContractReview.snapshot_revision` 与完整复核快照指纹；具体生成规则见下节 |
| `actual_tenancy_confirmed` | 仅在用户显式确认后保存为 `true` |
| `confirmed_fields` | 用户核对后的租约字段快照，以及明确确认的辖区和实际租赁类型；保留未知值，不能自动补事实 |

确认与当前复核版本、合同指纹必须一致。字段修正或合同换版后，旧确认仅作历史记录，M3 要求用户重新确认；M4 拒绝过期、缺失或归属不一致的确认。相同请求重试应复用原确认和租约 ID，内容变化使用新请求并保留历史。这些属于下一步需要实现并测试的验收条件。

## snapshot_revision 的生成与传递（2026-10-20，待实现）

`ContractReview.version` 继续表示现有合同字段修订版本；新增顶层 `snapshot_revision` 表示完整复核快照的保存次序。人工决定和问题清单操作可能不改变 `version`，也必须有新的快照序号。二者独立计数。

**生成职责与事务规则：**

- 由 M3 的唯一持久化入口生成，类型为大于等于 1 的整数，计数范围是同一个 `review_id`。首次保存为 1，后续每次完整快照变化加 1；`version` 增长时序号继续递增。
- 初次复核、有效字段修正、人工批准/退回、生成或编辑问题清单，凡实际改变持久化的 ContractReview，均产生一个新序号。纯读取、JSON/Markdown 导出、没有字段变化的修正和相同请求重试复用原快照、序号和指纹。
- M3 在事务内先核对请求收据和预期快照序号，再分配新序号、保存完整快照及收据。并发修改遇到旧的预期序号时返回冲突，重新读取后处理；不能让多个调用方各自对旧值加 1，也不能用时间戳代替计数器。新 `review_id` 独立从 1 开始。
- 先把 `snapshot_revision` 写入将要保存的完整 ContractReview，再计算 `review_sha256`。用户确认必须绑定其实际核对的已保存快照；持久化确认审计使用独立记录，不向被确认的旧 ContractReview 追加事件而改变其指纹。

**传递字段约定：**

```text
packet.review.review_id                  = M3 复核 ID
packet.review.version                    = 合同字段修订版本
packet.review.snapshot_revision          = M3 完整快照序号
packet.confirmation.review_id            = 同一复核 ID
packet.confirmation.review_version       = 同一合同字段修订版本
packet.confirmation.review_snapshot_revision = 同一完整快照序号
packet.confirmation.review_sha256        = 包含 snapshot_revision 的完整快照指纹
```

确认记录使用 `review_snapshot_revision` 这个字段名，以区分自身的 `confirmation_version`。两份 Schema 均需显式定义为整数且最小值为 1。交接外层原样传递当前完整快照及其持久化确认；前端显示/提交确认时带回所见序号，M3 服务端与当前保存值比较，旧快照须重新展示并由用户确认。实际序号由 M3 服务端分配。

指纹算法沿用 M4 PR #5 的约定：

```python
sha256(json.dumps(review, sort_keys=True, ensure_ascii=False,
                  separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
```

同一 `review_id` 的时间先后以 `snapshot_revision` 判定，`updated_at` 用于显示和审计。M4 保存已观察的最大序号：更小序号暂停为旧快照；相同序号与相同指纹表示同一快照（创建还需满足当前确认/案件门禁）；相同序号与不同指纹返回冲突；更大序号作为新快照处理，并要求当前确认的序号和指纹均匹配。新的暂停快照仍须保留已知序号，旧成功收据不能绕过门禁。

示例：初次复核 `(version=1, snapshot_revision=1)` → 人工放行 `(1,2)` → 字段修正 `(2,3)` → 问题清单 `(2,4)`。重复导出/重试仍为 `(2,4)`，即使两次状态变化发生在同一秒也能排序。

旧报告没有该字段时保留原始历史。迁移由 M3 在存储内将唯一当前快照登记为初始序号，再重新生成确认；M4 对新接入不能为每份旧报告自行补 1。需要新增的验证包括：同秒人工放行、同版本不同序号、相同序号不同指纹、字段版本变化、重复请求及并发修改。

## M4 创建时补齐的退租资料

M4 当前 [`TenancyRecord`](../../agent4/schemas/tenancy-record.schema.json) 的 `create` 需要租客确认后的 `tenancy_id`、`tenant_id`、地址、`jurisdiction=NSW`、`tenancy_type=standard_residential`、`confirmed=true`、来源引用和版本、房间/地毯/户外/家具属性、家具清单及基线证据引用。部分属性允许 `null` 或空列表，但应真实表达“未知”，不能把 M3 提取结果冒充租客确认。`case_id`、`actor_id`、`request_id`、`expected_version`、`as_of` 属于 M4 命令外壳，也由 M4/编排层提供。

建议 `tenancy.source_ref/source_version` 指向 M3 保存的 `confirmation_id/confirmation_version`；如需在 M4 里保留复核来源，可登记一条 `kind=other` 的 `EvidenceReference`，其 `source_ref=review_id`、`source_version=version`，并在 `summary` 中说明复核来源的用途。具体存法请 M4 队员确认。M4 负责补齐房间/地毯/户外/家具、家具清单和基线证据等退租资料；基线状况报告、押金支付记录和退租日期需要各自的用户输入或证据。`create_plan` 仍另行要求 `move_out_date` 与 `schedule_confirmed`，不能用 M3 的租约确认代替退租日期确认。

## 状态与重试约定（提案）

- `Reviewed`：允许进入 M3 的实际租约确认步骤；M4 仍需验证有效确认记录后才执行 `create`。
- `Awaiting Human Review`、`Awaiting Resubmission`、`Degraded Summary Only`：暂停 M4 创建，并显示当前状态/原因。
- `Questions Ready`：问题清单可能仍待租客处理；双方需决定何时允许进入 M4 确认，当前先暂停自动创建。
- 同一 `review_id` 出现更高 `version` 时，M3 要求重新确认；M4 重新读取当前字段并拒绝旧确认用于新的创建或上下文更新。重复收到同一版本和同一确认应得到同一处理结果。
- M3 `intake.request_id` 可包含 `:` 且最长 128 字符；M4 `request_id` 仅允许字母、数字、点、下划线、连字符，最长 80 字符。M4/编排层应生成稳定且符合自身规则的请求 ID；重试时原样复用整份 M4 命令，同 ID 内容变化会报 `request_conflict`。

## 分工和联调完成条件

**M3 队员（我）**：维护本交接说明、`ContractReview` Schema 和三份样例；新增实际租约确认入口及持久化确认记录，绑定身份/案例、复核版本和合同指纹，处理修正后的重新确认；与协调层约定租约 ID 登记，向 M4 交付上下文、复核结果和确认记录。

**M4 队员**：核对 M3 确认记录的字段与可接受状态，实现上下文、复核 JSON 和确认记录到 M4 `create` 的适配与来源保存；为缺失确认、人工复核、版本变化和重复请求返回可识别结果；补齐退租资料，在单独确认退租日期后调用 `create_plan`。

**共同验证**：正常接收、同一版本重复接收、缺少租客确认、`Awaiting Human Review`、同一 `review_id` 的新版输入。记录每次输入文件、命令、M4 结果、案件 ID/版本和是否发生重复创建。联调完成后再把本文件中的提案改成双方确认的契约。

## 请 M4 队员确认的四点

1. 如何保留上游 `caseId` 与确认者关联？M4 `case_id` 是否复用全流程案例，`tenant_id` 如何从可信会话取得，以及租约确认后由哪一层登记 `tenancy_id`？
2. `TenancyRecord.source_ref/source_version` 指向租客确认记录是否合适？M3 `review_id/version` 保存在 `EvidenceReference` 是否足够？
3. M4 是否只接受 `Reviewed`，以及 `Questions Ready` 何时可进入租客确认？
4. M4 还需要哪些 M3 字段或异常码？合同租期是否要进入 M4 数据模型？
