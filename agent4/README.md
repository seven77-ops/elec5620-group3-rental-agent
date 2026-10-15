# Agent 4 · Move-out & Aftercare（M4 初版）

Member 4 的独立 Python 原型，对应 Stage 1 的 **UC07 / FR07 退租计划、UC08 / FR08 押金善后、OF04 可选提醒**。不依赖 M1–M3；现有租客可直接提供已确认租约信息进入。当前版本 `0.1.0`，输入/导出 Schema `1.0`。

已实现：按房间/家具生成可编辑退租任务、证据引用、改期提案与确认、押金状态机、争议审核、跟进草稿、Sydney 时区提醒收件箱、SQLite 持久化、版本检查、请求重试去重，以及 JSON/Markdown 导出。默认离线，不需要模型密钥。

## 先跑起来

从仓库根目录进入 `agent4/`，需要 Python 3.10+：

```sh
cd agent4
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m aftercare_agent demo --output runs/demo-01
```

`runs/demo-01/` 必须是新目录。会生成本地数据库、9 组 JSON/Markdown 快照和运行日志。所有演示地址、押金编号、照片/收据引用均为合成数据；`synthetic://` 不指向真实文件。固定模拟时间为 2026-10-15 至 2026-11-03，不表示真实事件已经发生。

先读 `runs/demo-01/01-plan.md`，再依次看 `05-dispute.md`、`06-released-draft.md`、`09-closed-reminders.md`。演示包含 **17 次成功提交 + 1 次预期被审核门禁拦截的请求**；该拦截属于成功演示结果。

## 自己提交一次操作

下列命令在新的数据库中按顺序运行：

```sh
python -m aftercare_agent run --store runs/manual.sqlite3 \
  --request data/demo/requests/01-create.json --output runs/manual-created
python -m aftercare_agent run --store runs/manual.sqlite3 \
  --request data/demo/requests/02-create_plan.json --output runs/manual-plan
python -m aftercare_agent show --store runs/manual.sqlite3 \
  --case-id aftercare-demo-1 --actor-id demo-tenant --output runs/manual-current
```

`run` 应用一条操作；`show` 只读取。输出前缀已存在时拒绝覆盖。数据库提交后若文件导出失败，使用 `show` 和新前缀重新导出即可，不必重复业务操作。

自定义请求以 `schemas/command.schema.json` 和 `data/demo/requests/` 为准。每次新操作使用新的 `request_id`，`expected_version` 填当前案件版本，`as_of` 填带时区时间。重试时原样复用整份请求；同 ID 改内容会报 `request_conflict`。完全重复请求返回第一次保存的响应快照，当前状态请用 `show` 读取。

所有请求使用 `case_id + tenant_id` 隔离；跨租客引用证据、过期版本、未确认关闭及未知字段均会拒绝。操作者 ID 是本地演示身份，不代表真实登录认证。

## 审核与状态

```text
Draft --激活且无审核门禁--> AwaitingOutcome
Draft --激活且存在审核门禁--> UnderReview
AwaitingOutcome --争议/冲突--> UnderReview
UnderReview --授权操作员明确 release，全部门禁解决--> AwaitingOutcome
AwaitingOutcome / UnderReview --租客明确确认结果--> Resolved
Draft / AwaitingOutcome / UnderReview --租客明确撤回--> Withdrawn
```

`annotate / return / hold / refer` 都保留门禁。只有配置在 `AGENT4_OPERATOR_IDS` 中的本地演示操作员可写审核决定，例如：

```sh
# 仅在已经顺序执行演示前 10 个成功步骤、版本吻合的数据库上使用。
AGENT4_OPERATOR_IDS=demo-operator python -m aftercare_agent run \
  --store runs/manual.sqlite3 --request data/demo/requests/12-operator_decision.json
```

PowerShell 对应 `$env:AGENT4_OPERATOR_IDS='demo-operator'`，然后运行同一 Python 命令。`demo` 命令在进程内部配置此演示身份，不修改用户环境。

## 提醒与日期

默认不启用提醒。`reminder_preferences` 显式开启，`poll_reminders` 把到期项写入本地收件箱并返回本次新增项。再次查询不重复投递。完成/取消任务、待确认改期、关闭案件或取消订阅会抑制相应提醒；在实际投递事务中重新检查状态。改期确认前保留旧任务、完成状态和证据。

本版是 **CLI + 提醒后端**，没有常驻进程、桌面推送或图形界面。下次主动查询会处理到期项；尚未验证 Stage 1 所述“活跃界面 60 秒内显示”的 UI 指标。未来界面可以每 30 秒调用一次查询入口。日期按 `Australia/Sydney` 处理，包含夏令时变化；提前清洁等偏移是实用计划日期，不是法律期限。

## 可选模型入口

`request_draft` 默认 `use_model:false`，使用确定性事实模板。可选模型接收一个带引用的句子目录，只返回 `statement_ids` 与预定义结尾；程序验证必选事实、引用范围、重复项和结构，再渲染原始事实句。模型不能生成任意发布文本、裁定责任、改金额或改变案件状态。

配置兼容 Chat Completions JSON 协议的完整 HTTPS 地址、模型名和密钥：`AGENT4_MODEL_URL`、`AGENT4_MODEL_NAME`、`AGENT4_MODEL_API_KEY`。请求还必须同时明确 `use_model:true` 与 `allow_external_ai:true`。错误输出或超时返回错误且不保存草稿，不会自动伪装成模型成功。之后可由租客新建一次离线模板请求。

只用模拟数据试验外部模型。当前测试通过注入模拟网关覆盖合法返回、无效返回和超时；**没有实际调用模型服务，没有假设学校 Qwen Proxy 与该协议兼容**。因此不能把本版离线演示表述为“已完成真实 LLM 多 Agent 联调”。

## 代码导航

| 文件/目录 | 作用 |
|---|---|
| `aftercare_agent/store.py` | 本地协调入口、SQLite、身份/版本检查、请求收据、原子提交 |
| `aftercare_agent/services.py` | UC07/UC08 确定性业务操作、审核门禁、关闭规则 |
| `aftercare_agent/planner.py` | 房间/家具任务、缺失信息、日期提案与确认 |
| `aftercare_agent/reminders.py` | 可重复查询的提醒收件箱与失效抑制 |
| `aftercare_agent/model_gateway.py` | 可选模型适配、受限候选选择与确定性草稿 |
| `aftercare_agent/report.py` | 已提交记录的 JSON/Markdown 导出 |
| `aftercare_agent/__main__.py` | CLI；`demo.py` 驱动固定演示 |
| `schemas/` | 请求、租约、证据、案件导出四份契约 |
| `data/demo/` | 合成场景与 18 份逐步请求 |
| `reports/` | 可直接阅读的合成演示快照、验证结果 |
| `tests/` | 业务、模型边界、CLI 与并发测试 |

## 边界与交付

- 证据按 `source_ref + source_version` 引用并保留。可以登记照片、收据等元数据，但不上传文件、不做视觉识别或 OCR，也不把有引用当作事实已核实。
- 扣款始终标为 `reported_claim`；即使有附件或操作员放行，也不自动变成租客接受的扣款。金额用 AUD 整数分。
- 未验证通知触发事实和适用规则，不输出法定倒计时。官方路径见 [来源说明](docs/reference-sources.md)。
- 关闭需要租客明确确认或撤回。数据库保留历史、收据与证据；本版不提供自动清理或保留期任务。
- 没有 RBO/NCAT API、外发消息、申诉提交、支付或服务预订。草稿始终为 `prepared_not_sent`。
- 本地 CLI 与单 SQLite 库不是生产鉴权/部署方案；模型调用时会占用该库的写事务，当前适合单机课程原型。
- M3 尚无双方确认的 `TenancyRecord` 输出，不能把“合同已审查”自动当作“租约已签订且租客已确认”。M4 的独立输入契约和后续适配边界见 [数据契约](docs/data-contracts.md)。

上传时将 **整个 `agent4/` 目录**保留在仓库根目录，保留包目录层级。不要只上传 ZIP 文件并认为 GitHub 会自动解压。`runs/`、数据库、虚拟环境和密钥不属于源码提交。

进一步阅读：[仓库审阅与拆解](docs/repository-review.zh-CN.md)、[需求追踪](docs/requirements-traceability.md)、[演示讲解](docs/demo-guide.zh-CN.md)、[验证记录](docs/verification-2026-10-15.md)。
