# M3 → M4 接收验证

本次为 M4 消费端的合成数据预联调。M3 实际租约确认入口未实现，确认记录由明确标注的测试替身提供。

快照序号同样由测试替身显式分配；同秒复核/人工放行调用真实 M3 状态函数。尚未验证 M3 事务计数器和确认持久化入口。

| 场景 | 版本/序号 | 结果 | 结果码 | 案件数 |
|---|---|---|---|---|
| 01-normal-stub | 1/1 | created | ok | 1 |
| 02-repeat | 1/1 | duplicate | ok | 1 |
| 03-unconfirmed | 1/1 | paused | confirmation_required | 0 |
| 04-human-review | 1/1 | paused | review_blocked | 0 |
| 05-version-change | 2/2 | paused | review_version_mismatch | 1 |
| 06-old-version-replay | 1/1 | paused | stale_snapshot | 1 |
| 07-v2-reconfirmed-fresh | 2/2 | created | ok | 1 |
| 08-v2-reconfirmed-existing | 2/2 | paused | existing_tenancy_requires_reconciliation | 1 |
| 09-separate-date-setup | 1/1 | created | ok | 1 |
| 15-same-second-pending | 1/1 | paused | review_blocked | 0 |
| 16-same-second-approved | 1/2 | created | ok | 1 |
| 17-old-pending-replay | 1/1 | paused | stale_snapshot | 1 |
| 18-same-revision-conflict | 1/2 | paused | review_snapshot_conflict | 1 |
| 19-confirmation-revision-mismatch | 1/2 | paused | review_snapshot_revision_mismatch | 0 |
| 20-newer-blocked-snapshot | 1/3 | paused | review_blocked | 1 |
| 21-old-success-replay | 1/2 | paused | stale_snapshot | 1 |

## 回归

- m4-tests: 99 项通过。
- m3-tests: 25 项通过。
- upstream-integration-tests: 6 项通过。

## ID 与来源

- 正常 M4 案件：`aftercare-6f0c08ae521b48f28bf30d716b9dc231`。
- 正常租约：`tenancy-430fc82f67e24b9b9e94563b06aa5e37`。
- `02-repeat` 与 `01-normal-stub` 的案件和租约 ID 相同；数据库仍为一个案件。
- `15/16` 在同一秒从序号 1 人工待审变为序号 2 放行，可创建；`17/21` 的旧包被拦截，`18` 同号异内容冲突，`19` 确认序号不匹配暂停。
- 已核对旧报告 67 个文件的指纹，全部保持原样。
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
