# M4 初版演示讲解

在 `agent4/` 安装依赖后运行：

```sh
python -m aftercare_agent demo --output runs/live-demo-01
```

每次换一个新的输出目录。演示完全使用固定合成记录，无需输入真实个人资料或模型密钥。`reports/` 中有相同流程生成的可读静态快照。

| 阶段 / 文件 | 展示重点 | 可以怎样解释 |
|---|---|---|
| `01-plan.md` | 房间、地毯、家具任务，Bedroom 已完成并关联照片/收据 | 系统按确认的物业资料选择适用任务，日期由程序计算 |
| `02-date-proposed.md` | 新退租日期待确认、旧任务仍保留、旧提醒暂停 | 提案不会直接覆盖用户确认的安排 |
| `03-date-confirmed.md` | 新日期、已完成状态和原始证据保留 | 改期改变日程，不会抹掉已做的工作 |
| `04-clear-draft.md` | AwaitingOutcome、事实草稿、来源引用、未发送 | 用户主动请求草稿，系统不自动接受扣款或确认退款 |
| `05-dispute.md` | 报称 AUD 180.00 墙面扣款、UnderReview、review-1 | 这是 reported claim；租客争议会先触发审核，而不是继续输出受影响的建议 |
| `scenario-log.json` 中 `demo-11` | `review_required` 为预期拦截，版本不增加 | 审核不是只有一个提示文案，而是阻断生成的服务规则 |
| 操作员 refer，然后 release | refer 保留门禁；明确 release + gate_resolved 才解除 | 转介与放行有不同的业务含义；当前身份为本机模拟 |
| `06-released-draft.md` | 新草稿仍将扣款称为“reported claim” | 放行允许事实沟通，不等于认定扣款合理 |
| `07-reminders.md` | 模拟时间推进后处理到期提醒，记录 delivered_at | 提醒只提示检查状态，不会自动结案 |
| `08-closed.md` / `09-closed-reminders.md` | 租客明确确认结果、保留历史、再次查询无新增提醒 | 关闭是用户决定，历史仍可读取 |

演示末尾输出 `commands_committed:17`、`expected_blocked_commands:1`、`final_state:Resolved`。可以再运行测试展示并发重试、无效模型和存储故障等边界。

诚实说明：本演示是 M4 独立服务和命令行，不是完整租房应用；默认事实模板不调用 LLM。可选模型网关有结构约束测试，尚无真实服务实测。没有自动发送邮件、申诉、官方查询或完成 M3 接口联调；活跃图形界面提醒的 60 秒指标也尚未验证。
