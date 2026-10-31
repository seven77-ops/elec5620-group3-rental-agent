# 2026-10-24 M4 反馈修复与最新试用更新

继续更新 `codex/group-trial-20261022` / PR #7，暂不合并 main。Anda 负责本轮网页、适配和 AI 对话修复；成员原 Agent1/3/4 业务代码继续按原贡献归属。

## 反馈与修复

根据 Anda 提供的群聊截图，Member 4 反馈两处网页流程卡住，并发送 `M4_integration_review.md`。其 Jira 显示名为 **Zz W**（见 SCRUM-37）。本轮未取得该原始附件全文；具体修复范围以仓库修复说明和实际代码为准。本记录不能替代反馈人的复测确认。

1. **租约建案后无法补齐资料，退租计划不能继续**：新增同案“补充租约资料”入口，预填已有信息，明确列出缺失项。用户确认后调用原 `revise_tenancy`，保留案件、租约 ID 和证据，递增来源版本；计划或押金激活后限制编辑。
2. **押金草稿缺编号或凭证时没有补录入口**：新增草稿阶段“补录押金资料”，可补编号或选择已保存的押金证据。更新同一 Draft，不自动激活；确认事实仍是独立操作。保留表单输入、原请求重试和版本冲突处理。
3. **可读性**：补齐入口、缺项提示与租约资料用中文呈现；已知“否”与未知信息分开，原始诊断保留在折叠内容中。

详细设计及实现阶段证据：[恢复流程](2026-10-24-m4-recovery.md)、[可读页面](2026-10-24-m4-readable-ui.md)。

## 同步发布的最新 AI 对话改动

修复区域比较后选区、补充学校/预算/房型时的流程推进；区域回答结合当前条件，含糊的 Rose 名称需要澄清。次级模型失败时保留主路由结果，有限恢复追问且保留用户明确修改；结构不合法的回复仅允许一次重试。

见 [对话推进修复](2026-10-24-assistant-progress-repair.md)及 [既有真实模型场景记录](../user-scenarios/2026-10-24-flexibility/验证记录.md)。这些真实模型记录来自实现阶段，不算本轮重新调用。

## 本轮实际验证

在独立冻结发布快照运行，Python 3.13.2 / Node 22.23.1：

| 检查 | 结果 |
|---|---|
| 根目录 `python -m unittest discover -s server/tests -v` | 338/338，52.021 秒 |
| 各 agent 目录 `python -m unittest discover -s tests -v` | Agent1 52/52、Agent2 89/89、Agent3 40/40、Agent4 57/57 |
| integration 目录同一命令 | 6/6 |
| frontend `node --experimental-strip-types --test tests/*.test.ts` | 18/18 |
| frontend `npm run build` | TypeScript/Vite 通过；既有 vendor 体积提示仍在 |
| `git diff --check` 和发布文件扫描 | 通过；未发布环境密钥、运行数据库、上传文件和依赖目录 |

共 **582 项 Python 检查、18 项前端单元检查**通过。另对隔离运行目录中的虚构案例通过实际网页操作验证：空押金编号 Draft → 补录编号后仍为 Draft；未知房间/地毯/室外/家具资料 → 同案补齐、来源版本 1→2 → 退租计划 Active；单独确认事实后押金进入 AwaitingOutcome。刷新及服务端读取确认相同案件/租约 ID、原证据保留，只有一条事实记录。

本轮未重跑自动浏览器全套、付费模型、真实交通请求或批量定位；实现阶段浏览器检查见各自功能文档。本轮未在 Windows 设备实测。独立代码复查未发现发布阻塞。

## 后续

请 Zz W 拉取试用分支，用原始复现步骤重试这两个流程，并在群内向 Anda 反馈结果、截图及建议；由 Anda 统一修改本轮集成代码。**修复及本地验证完成，反馈人复测尚待进行**；不据此关闭整个 Agent4 验收/交接任务。

- [PR #7](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/7)
- [SCRUM-35：Anda 前端与集成](https://breezebee64.atlassian.net/browse/SCRUM-35)
- [SCRUM-37：Zz W / Agent4 验收](https://breezebee64.atlassian.net/browse/SCRUM-37)
