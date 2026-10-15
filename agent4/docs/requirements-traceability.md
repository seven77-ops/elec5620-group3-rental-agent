# Stage 1 → M4 v0.1.0 追踪表

“已实现”指本地原型代码和测试，不代表生产接入或全组验收。此表以用户提供的 Stage 1 报告为依据。

| 要求 | 初版实现 | 对应证据 / 限制 |
|---|---|---|
| FR07 / AD-M4-01 / UC07 | 房间、地毯、户外、家具清单生成任务；状态、日期、证据引用可编辑 | `planner.py`；`test_tailored_plan_inventory_and_practical_dates` |
| 未知信息不可编造 | `null` 保留未知并提出澄清；不能直接将有阻塞问题的计划确认 Active | `test_unknown_property_stays_draft_until_corrected` |
| 基线缺失处理 | 标明缺失、加入补记录任务，不假造条件比较 | `test_missing_baseline_is_visible_but_does_not_block` |
| 改期不丢完成/证据 | 提案和确认分离；保留旧日期、任务修订、状态与引用 | `test_proposed_and_confirmed_reschedule_preserves_done_and_evidence` |
| UC07 争议证据 | `edit_task.review_reason` 创建持久化审核；后来启动 UC08 仍受门禁约束 | `test_plan_conflict_creates_review_before_bond_entry` |
| FR08 / AD-M4-02 / UC08 | 押金编号或凭证、带日期历史、报称扣款、直接进入 aftercare | `test_direct_bond_entry_without_plan`、`test_deposit_record_is_valid_alternative` |
| 扣款不擅自接受 | `reported_claim`、整数 AUD 分、引用和租客争议字段；不自动更改为接受 | `test_dispute_blocks_draft_and_keeps_claim_classification` |
| SR02 争议/冲突审核 | UnderReview + durable ReviewTask；门禁先于模型/草稿 | `test_review_gate_precedes_any_model_call` |
| 操作员显式释放 | 允许列表、注释/hold/refer/return 不清门禁、全部门禁解决后才恢复 | `test_explicit_release_requires_all_review_gates_cleared` |
| 事实草稿 | 离线模板或模型受限选择；引用/结构校验，始终 prepared_not_sent | `test_valid_model_only_selects_evidence_bound_statements`；真实模型未实测 |
| 租客确认结案 | Resolved 需显式结果确认；Withdrawn 需显式撤回；保留审计 | `test_outcome_closes_reviews_retains_audit_and_suppresses_all_reminders` |
| SR01 案件/任务/版本 | case/tenant 归属、expected_version、request_id、task 元数据、原子收据 | 重放、并发、版本冲突及身份测试；无跨 Agent HTTP 接口 |
| 失败一致性 | 无效模型/超时不提交；存储异常回滚且不报告已路由；重新请求/导出可恢复 | 模型异常、存储触发器故障注入测试；无独立失败任务或外部队列 |
| OF04 / AD-M4-03 | 显式 opt-in、Sydney 时间、幂等查询到期项、完成/改期/取消/关闭抑制 | `reminders.py`，含 DST、重查、关闭竞争测试；CLI 主动查询，没有 UI/常驻推送 |
| 活跃界面 60 秒提醒 | 尚未验证 / 未实现显示层 | 需要未来界面周期查询、展示与实际计时测试 |
| 当前法定期限 | 暂不计算，只显示待核验 | 没有已验证规则包与触发事实时不产生倒计时 |
| NFR 性能/可用性/用户体验 | 仅有本地功能测试和操作演示 | 不把执行时间当用户研究或 95%/99% 等量化目标的验证 |
| 跨 Agent 协作 | M4 本地 TenancyRecord v1 提案 | 未与 M3 联调；不冒充全组最终契约 |

Stage 1 的模型状态以 `Draft / AwaitingOutcome / UnderReview / Resolved / Withdrawn` 实现。运行失败属于操作错误，不增加一个虚构的 BondCase 状态。数据库保留关闭对象；关闭不是删除。
