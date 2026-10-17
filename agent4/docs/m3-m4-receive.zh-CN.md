# M4 接收 M3 合同复核与实际租约确认

日期：2026-10-17。本地消费端已实现；这是 M4 给 M3/前端组员的可运行提案，待双方对齐确认记录后联调。M3 PR #3 的确认入口尚未实现，当前演示确认是测试替身。实现基于 main `b06614d`，只修改 `agent4/`，不要求先合并 PR #3/#4。

## 字段核对与对 M3 四个问题的答复

| 项目 | M4 实现/约定 | M3/协调层还需提供或确认 |
|---|---|---|
| 用户身份 | `context.tenant_id` 与独立传入的 `actor_id` 一致；确认中的 tenant_id/confirmed_by 必须相同 | 从可信会话取得 ID，不能从合同姓名或浏览器传参推断；CLI 仅模拟身份 |
| 案例关联 | `context.case_id` 沿用全流程案例 ID；M4 生成独立 aftercare ID，并持久化双向业务关联 | 协调层保留已有 `caseId`，命名转换成 case_id；不能从 ContractReview 推造 |
| 租约 ID | 确认中的 `tenancy_id` 可为已有登记 ID 或 null；null 时 M4 在创建事务中分配随机 ID | 请确认 M4 担任新租约登记层。已有 ID 必须传原值；冲突时回查原映射，不重复创建 |
| 确认来源 | `tenancy.source_ref/source_version` 指向 confirmation_id/confirmation_version | M3 要先持久化确认，再交接；该二元组的内容不可重写 |
| 复核来源 | EvidenceReference 保存 review_id/version、合同 SHA-256、完整复核 SHA-256；kind=other | 原样交付最新完整 ContractReview，不给 revisions 中的旧快照 |
| 租期、金额、计价口径 | 完整 ContractReview 与 confirmed_fields 保存于不可变交接快照，可用 get_handoff 读取/导出 | 不扩展现有 TenancyRecord，不丢失起止日期；合同押金金额不充当付款证明 |
| 可接受状态 | 仅 Reviewed；人工复核存在时要求 approved 且绑定当前 review_version，覆盖 high findings | Questions Ready 暂停；其他状态暂停。人工放行仍不能替代实际租约确认 |
| 房间/家具/基线证据 | property_details/evidence 独立接收；未知明确使用 null/空引用 | 由 M4 向用户补齐。不能从 listing.rental_mode 推导实际 tenancy_type |
| 退租日期 | 成功接收时 plan/bond 均为 null、提醒关闭；独立确认日期后才能 create_plan | 不把 end_date、选房确认、处理同意或实际租约确认当成退租日期确认 |

M3 提案中还没有运行的确认 Schema。本次提供 `schemas/tenancy-confirmation.schema.json` 供统一。请重点确认以下缺口：

1. **新增 `review_sha256`**：完整当前 ContractReview 的规范 JSON SHA-256。M3 人工决定/问题操作可能只改状态和 updated_at、不提高 version，仅校验 review_id/version/document_sha256 不够。确认必须绑定用户实际看到的完整快照。
2. `confirmed_fields` 明确为 11 个合同字段的 **value 快照**，不包含 confidence/evidence：address、landlord、tenant、rent_amount、rent_period、rent_scope、currency、bond、start_date、end_date、signed_date；另加用户确认的 jurisdiction 与 tenancy_type。值必须与当前复核相同；要修改事实先 correct，再重新确认。end_date/bond 可为 null；其余必需事实未知会暂停。
3. `tenancy_id:null` 表示待 M4 登记；成功结果返回分配的 ID，M3/协调层应保存映射。若已有实际登记记录则传其 ID。该约定需要 M3 同意后落到其生产入口。
4. M3 要提供持久化的 confirmation_id/version、确认时间、确认人及显式 actual_tenancy_confirmed，字段修正后重新确认。**现有三份 ContractReview 都缺这份记录**，因此原样输入不能创建已确认租约。

## 接收接口

```python
result = AftercareAgent(database).receive(
    packet,
    actor_id=session_tenant_id,
    as_of=coordinator_clock,
)
```

`packet` 严格 Schema 为 `schemas/m3-handoff.schema.json`：

```text
schema_version: "1.0"
request_id: 上游可重试请求 ID，1..128 字符，允许冒号
context: {tenant_id, case_id}
review: 当前完整 ContractReview（复用 M3 Schema 和语义验证）
confirmation: TenancyConfirmation | null
property_details: {rooms, carpeted, outdoor, furnished,
                   inventory, inventory_confirmed, baseline_evidence_refs}
evidence: EvidenceReference[]
```

确认不包含 M4 的 actor_role、expected_version 或模拟时间。`actor_id/as_of` 由协调层独立传入；真实服务还必须验证案例归属、确认记录确实来自 M3 持久化存储，以及 review 是 M3 当前快照。**指纹是内容绑定，不是数字签名，也不证明来源可信。** M4 只能识别本库已经见过的较新版本，无法发现尚未交付的 M3 更新。

`review_sha256 = sha256(json.dumps(review, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()`。直接复用 `aftercare_agent.handoff.fingerprint` 可避免空白/编码差异。

新建、租约登记、M4 案件、复核/确认来源、原始交接快照与收据都在同一个 SQLite 写事务中提交。异常时不留下半成品。新租约和善后案件用随机 ID，不从 listing_id 或 review_id 推导事实 ID。

同一请求/内容重试，或者换请求 ID 重复投递同一业务输入，都返回原案件和租约。重复响应 `status=duplicate,newly_created=false`，内层 receipt 是首次提交的不可变快照；当前案件版本使用 `get`/`show` 读取。数据库用全流程案例、租约、复核唯一约束阻止并发重复创建；同请求 ID 改内容报 request_conflict。确认 ID/version 的内容同样不可变，旧确认版本不能回滚。

只要有效结构的较新复核到达，即使缺确认而暂停，也保存已知版本；之后旧成功请求重放不能绕过当前门禁。相同版本、不同内容只有 updated_at 更晚时才接收为当前快照，同时必须重新确认指纹。

## 结果码

| code | M4 结果/动作 |
|---|---|
| 无；status=created/duplicate | 创建成功/返回已有 ID |
| confirmation_required | 缺确认或 actual_tenancy_confirmed=false，暂停 |
| review_blocked | 状态不允许或人工复核未解决，显示原状态/原因，暂停 |
| review_version_mismatch / stale_review | 确认不是当前版本/收到已知旧版，暂停 |
| review_fingerprint_mismatch / review_snapshot_conflict | 合同或完整快照不匹配/同版本快照次序不明，暂停 |
| confirmation_ownership_mismatch / confirmation_time_invalid | 确认身份案例或时间不合法，暂停 |
| confirmed_fields_mismatch / tenancy_fields_missing | 修正 M3 事实后重新确认，暂停 |
| unsupported_tenancy | 未明确确认为 NSW standard_residential，暂停，不自动改租赁类型 |
| stale_confirmation | 已知更新确认版本，暂停 |
| existing_tenancy_requires_reconciliation | 已有案件收到有效新确认/新版本；保留现有案件，暂停隐式覆盖和再次创建 |
| access_denied / context_conflict / tenancy_conflict | 身份不符、复核跨案例或租约已有记录，拒绝且回滚 |
| request_conflict / confirmation_conflict | 请求 ID 或确认 ID/version 改内容，拒绝且回滚 |
| invalid_input / invalid_review / storage_error | Schema/语义或存储失败，拒绝且回滚 |
| move_out_confirmation_required | M3 来源案件尚未独立确认退租日期，拒绝 create_plan |
| handoff_review_stale | 已有案件的 M3 来源落后于已知复核；先核对租约再创建/确认计划或补资料 |

CLI 接收成功/重复 exit 0；业务暂停 exit 3；输入/权限/存储错误 exit 2。暂停不会创建租约/案件，但会保存版本观察和接收结果。修正输入必须用新 request_id，原暂停请求的收据不可变。

已有案件发现新版时，目前保留原始确认与旧来源，不自动改写在用租约或计划。重新确认的新版本在未建租约的新案例可正常接收；已有案件需要双方另行设计显式 reconciliation 操作，不偷偷用新版 create 再建一个案件。

## 退租资料补齐与单独确认日期

接收后，可以用原 `revise_tenancy` 补齐房间、地毯、户外、家具清单和基线引用。M3 来源案件须保持 tenancy_id、tenant_id、地址、辖区、租赁类型及 confirmation source_ref/source_version 不变；本地 case.version 和 audit 记录补充动作。该路径允许确认来源版本保持不变，避免把房间资料更新冒充 M3 新确认版本。

资料完整后，单独向用户确认 move_out_date，再调用 `create_plan`，设置 `schedule_confirmed:true`。M3 接收案件不允许 `schedule_confirmed:false` 创建草稿计划；独立旧租约入口继续支持其原有 Draft 流程。原 `propose_date`/`confirm_date` 改期流程保留。

## 命令与五种场景

从仓库根目录运行，receive 需要同仓库中的 M3 验证器；Windows：

```powershell
$env:PYTHONPATH='agent4'
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m aftercare_agent receive `
  --packet agent4/data/demo/m3-handoff/normal-confirmation-stub-packet.json `
  --store agent4/runs/m3-manual-01.sqlite3 `
  --actor-id DEMO-TENANT-001 --as-of 2026-10-17T19:01:00+11:00 `
  --output agent4/reports/m3-manual-01
```

此命令刻意使用模拟确认记录和固定模拟时间，不表示用户进行了真实签约确认。输出前缀必须是新文件名。需要原样重试时换新输出前缀，业务包保持原样。

自动复现正常、重复、未确认、人工复核、版本变化五种场景，并补测旧版重放、新版重新确认、已有案件、独立退租日期确认：

```sh
python agent4/tools/verify_m3_handoff.py --output agent4/reports/m3-m4-<new-run-name>
```

脚本运行 M4、M3 和上游 integration 回归；自动将 Windows 临时目录放在 ignored runs 下，使用 UTF-8。保存命令、返回码、依赖版本、输入、JSON/Markdown、stdout/stderr、文件 SHA-256。新输出目录不能覆盖已有报告。

## 与统一前端的边界

已阅读 PR #4 `docs/frontend/api-contract.md`、`implementation.md` 和 `server/app/adapters/aftercare.py`。现有 `POST /aftercare/commands` 是租客手工核对租约的独立入口，不能当作 M3 确认记录接收接口。本次没有修改草稿 PR #4 的页面/服务端，也没有宣称完成浏览器联调。

前端组员可在 M3 确认入口完成后增加服务端调用：读取会话租客与当前 CaseState → 从 M3 存储读取确认及最新 ContractReview → 校验归属/当前 selection → 构造 packet → 调用 M4 receive → 保存返回的 aftercare_case_id。不能让浏览器直接上传 actor_id、确认来源或 review 快照充当可信事实。HTTP 请求完成前若协调库保存映射失败，用同包重试 M4，并用返回的原 ID 补写映射。

原 API 使用的 TENANT/案例标识应直接进入 context，不能把示例 DEMO-TENANT-001 写死进统一服务。操作员 header 只能授权人工决定，不能代租客确认实际租约或退租日期。请在双方联调后再确定新增 HTTP 路由及前端类型；不要对现有接口做未经对齐的替换。

## 本次交付与下一次真正联调

1. M4 已给出 receive、两个 Schema、模拟包、五场景验证器和报告。
2. M3 实现并持久化真实 TenancyConfirmation，确认 review_sha256、tenancy_id 登记职责和 confirmed_fields 结构。
3. 协调层绑定真实保存的案例/会话/当前版本，再共同运行五场景；用新的 reports 目录保存真实入口的命令和结果。
4. 新版落到已存在租约时仍暂停，明确人工/用户核对及上下文更新方案后另行实现。

所有样例为合成数据；没有发送消息、付款、激活押金或调用外部模型。
