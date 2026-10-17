# M4 本地数据契约 v1.0

## 入口与持久化

```python
from aftercare_agent.store import AftercareAgent

agent = AftercareAgent('runs/aftercare.sqlite3', operator_ids={'local-operator'})
response = agent.submit(command_dict)
case = agent.get('case-id', 'tenant-id')
```

本地库保存 `cases(case_id, document)` 和 `receipts(actor_id, request_id, fingerprint, response)`。写操作先检查身份/归属，随后查收据，再核对版本；完整相同请求返回原始响应，故重放已成功旧请求无需改成最新版本。不同内容不能复用同一操作者下的请求 ID。请求 ID 指纹覆盖整个请求，包括时间、角色、版本和载荷。

`BEGIN IMMEDIATE` 串行处理写入；事务包含案件状态、审核记录、提醒、审计和收据。存储异常全部回滚并报错，不能把本地记录失败表述为审核已送达。这里的审核队列是聚合内的持久化列表，不是外部投递服务。数据库完全不可写时也无法保存一个新的“待路由”标志，调用方必须保留失败请求并重试；当前没有独立持久化重试队列。

`actor_id / actor_role` 与操作员允许列表仅模拟业务权限。未来统一入口应从已认证会话注入身份，不能信任浏览器自行提交的身份字符串。

## 请求外壳

四份机器可读契约位于 `schemas/`；逐步样例位于 `data/demo/requests/`。

```json
{
  "schema_version": "1.0",
  "request_id": "request-001",
  "case_id": "aftercare-001",
  "actor_id": "tenant-001",
  "actor_role": "tenant",
  "expected_version": 0,
  "as_of": "2026-10-15T10:00:00+11:00",
  "operation": "create",
  "payload": {"tenancy": {}, "evidence": []}
}
```

上面的空 `tenancy` 仅展示外壳，不能运行；完整可运行样例为 `01-create.json`。ID 仅允许字母、数字及 `._-`，最长 80 字符（房间/家具条目 ID 最长 60 字符，以保留生成任务前缀空间）；拒绝未知字段、重复 JSON 键、NaN/Infinity、无时区时间、负数/小数/布尔金额。

时间是调用方明确提供的业务操作时间，便于固定场景重放，不充当生产环境可信服务器时间。命令时间不能早于最近提交；历史事件和证据可以更早，但不能晚于当前命令。计划日期支持 2000–2100，按本地日历计算。真实接入时应由服务器生成操作时间。

## 主要对象

| 对象 | 必要信息 / 语义 |
|---|---|
| `TenancyRecord` | `tenancy_id, tenant_id, address, jurisdiction:NSW, tenancy_type:standard_residential, confirmed:true, source_ref, source_version`；房间、地毯、户外、家具属性允许 `null` |
| 家具清单 | 条目 `id/name/room_id`；房间必须存在；`inventory_confirmed` 表示租客是否已核对 |
| `EvidenceReference` | `evidence_id, kind, source_ref, source_version, recorded_at, summary`；只登记元数据，不读文件 |
| `MoveOutPlan` | Draft / Active / Cancelled、任务、缺失证据、待澄清问题、改期提案、历史计划；日期偏移不是法律期限 |
| `BondCase` | Draft / AwaitingOutcome / UnderReview / Resolved / Withdrawn、带日期历史、reported claims、草稿、结果、用户选择的跟进时间 |
| `ReviewTask` | reason_key、原因、引用、open / released / closed_by_tenant、操作员决策及时间；普通批注不释放 |
| `FollowUpDraft` | `mode, blocks, source_refs, text, based_on_version, saved_at_version, status`；始终需要租客审阅且未发送 |
| `Reminder` | 对应计划任务或押金案件，scheduled / delivered / suppressed；以 owner + due_at 生成稳定 ID |

金额固定为 **AUD 整数分**，范围 0–100,000,000 分；例如 `18000` 表示 AUD 180.00。该范围是原型输入限制，不是法律规定。扣款 ID 和证据 ID 不可就地覆盖；更正使用新的证据 ID/版本和带日期更新，原始主张持续保留。

## 操作列表

| 操作 | payload / 关键条件 |
|---|---|
| `create` | tenancy + evidence；新案件 expected_version=0；来源/租约确认由租客明确提供 |
| `revise_tenancy` | 完整 tenancy；ID 不变、source_version 增加；计划和押金尚未激活才允许替换上下文；保留旧任务修订与命令收据 |
| `add_evidence` | 一条 evidence；引用 ID 不可绑定不同内容 |
| `create_plan` | move_out_date + schedule_confirmed；有待澄清的属性不能直接确认为 Active |
| `confirm_plan` | tenant_confirmed:true；需要先处理阻塞澄清；缺基线可继续但保留 evidence_gaps |
| `edit_task` | task_id、status、evidence_refs；可选 title、due_date、review_reason；证据累计保留；冲突转 review |
| `propose_date` | move_out_date；仅产生提案，不改原日期/任务，暂时抑制计划提醒 |
| `confirm_date` | accepted:true/false；接受才调整任务日期，保留完成状态、附件引用和旧任务快照 |
| `cancel_plan` | tenant_confirmed:true + reason；保留任务和证据，抑制该计划提醒 |
| `open_bond` | bond_reference 或 deposit_evidence_ref，可先都为空形成 Draft；凭证须是 deposit_record |
| `activate_bond` | tenant_confirmed 的 entry；须已有押金编号或凭证；根据审核门禁进入活跃子状态 |
| `bond_update` | entry(text, occurred_at, evidence_refs, tenant_confirmed, claims, conflicting_evidence) |
| `request_draft` | use_model + allow_external_ai；存在未释放审核则先阻断，不调用模型 |
| `operator_decision` | review_id、decision、note、gate_resolved；仅允许列表中的 operator；release 需要 gate_resolved:true |
| `confirm_outcome` | outcome、evidence_refs、tenant_confirmed:true；Draft 不可确认结果 |
| `withdraw` | reason + tenant_confirmed:true；从 Draft 或任一活跃子状态撤回 |
| `reminder_preferences` | enabled + follow_up_at（可空）；选跟进时间须有已激活押金案件；时间转 Sydney 存储 |
| `poll_reminders` | 空对象；重查当前状态/订阅后处理到期项；不自动关闭案件 |

`edit_task` 对标题/状态/日期的更改是租客显式操作。自定义日期会更新该任务的相对退租偏移；后续改期沿用该偏移。已有日期提案时不能同时修改某个任务的日期。

## 响应和失败

成功响应：`schema_version, request_id, case_id, version, task, result, case`。`task` 标明任务 ID、AftercareAgent 责任角色、输入/输出版本、输出引用和完成状态。失败请求返回错误，当前没有独立持久化的失败任务队列。`case` 是提交后的完整快照，`result` 包含当前操作结果，查询提醒时带本次投递列表。每个成功写请求递增 version；即使提醒查询未找到新项，也有审计和收据。

CLI 失败退出码为 2，stderr 为 `{"error":{"code":"...","message":"..."}}`。常见代码：`invalid_input, needs_clarification, access_denied, case_mismatch, missing_evidence, evidence_conflict, version_conflict, request_conflict, review_required, case_closed, model_invalid, model_unavailable, storage_error, output_exists`。

模型/校验失败不提交该命令、不增加版本。新的事实、证据、计划或审核决定会让此前 current 草稿变为 superseded；保留历史但不作为当前发布草稿显示。修改提醒偏好和轮询不会改变事实草稿。

本机 JSON/Markdown 导出是独立步骤，不是跨 Agent 已送达。导出失败可从已提交数据库恢复；绝不能把非零 CLI 退出时的文件错误等同于业务事务必然未提交。

## M3 接收扩展（2026-10-17）

本版可通过 `receive` 验证完整 `ContractReview`、可信业务上下文和单独保存的实际租约确认后创建租约；不会从复核结果推断真实签约/入住。M4 新增消费端接收包及实际租约确认 Schema，保留本文件原有独立租约输入。完整字段核对、状态门禁、来源快照、ID 映射、单独退租日期确认和前端边界见 [M3 → M4 接收说明](m3-m4-receive.zh-CN.md)。M3 生产入口尚未实现，本次报告中的确认是测试替身。

这次的 `TenancyRecord` 是 **M4 自己可运行的 v1 提案**，不是小组已经统一的最终契约；不要求 M1–M3 立即按该格式修改代码。
