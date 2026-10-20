# M3 → M4 接收验证

本次为 M4 消费端的合成数据预联调。M3 实际租约确认入口未实现，确认记录由明确标注的测试替身提供。

| 场景 | 结果 | 结果码 | 案件数 |
|---|---|---|---|
| 01-normal-stub | created | ok | 1 |
| 02-repeat | duplicate | ok | 1 |
| 03-unconfirmed | paused | confirmation_required | 0 |
| 04-human-review | paused | review_blocked | 0 |
| 05-version-change | paused | review_version_mismatch | 1 |
| 06-old-version-replay | paused | stale_review | 1 |
| 07-v2-reconfirmed-fresh | created | ok | 1 |
| 08-v2-reconfirmed-existing | paused | existing_tenancy_requires_reconciliation | 1 |
| 09-separate-date-setup | created | ok | 1 |

## 回归

- m4-tests: 87 项通过。
- m3-tests: 25 项通过。
- upstream-integration-tests: 6 项通过。

## ID 与来源

- 正常 M4 案件：`aftercare-b298cdd88922407795ac28be644590e9`。
- 正常租约：`tenancy-46d99b8d597b445ea131a301ce7937b1`。
- `02-repeat` 与 `01-normal-stub` 的案件和租约 ID 相同；数据库仍为一个案件。
- `05-version-change` 保存已知 v2，旧确认被拒绝；随后 v1 原请求重放也被拒绝。
- 原租约来源仍为 v1，不自动覆盖、不创建第二案件；新版重新确认在新库可创建，在既有库要求明确核对。
- `10-before-date-confirmation` 的 plan/bond 均为 null；第 11 步未确认日期被拦截，第 13 步独立确认后创建 Active 计划。
- 完整业务上下文、合同、租期与确认快照见各场景 JSON 及 `14-saved-handoff-snapshot.json`。

## 复现

从仓库根目录，使用装有 agent3/agent4 requirements 的 Python：

```sh
python agent4/tools/verify_m3_handoff.py --output agent4/reports/m3-m4-<new-run-name>
```

输出目录必须使用新名字；完整命令、返回码、环境、依赖版本见 execution.json，stdout/stderr 逐条保存。

仍需 M3 提供真实持久化确认记录，并由统一服务端绑定会话、案例和最新复核后调用 receive。前端页面与真实生产鉴权不在本次验证范围。
