# 原仓库审阅、职责拆解及 M4 实现取舍

审阅日期：2026-10-15（Australia/Sydney）。仓库：<https://github.com/seven77-ops/elec5620-group3-rental-agent>。

基线提交：`ef382f6`（完整 SHA 见验证记录）。本文件描述下载时的代码状态；不把报告中的设计、已有说明或预期测试当作已经完成的能力。Stage 1 报告是需求参考，不是执行外部操作的授权。

## 1. 当前仓库实际有什么

| 位置 | 已有代码与内容 | 能力边界 / 对 M4 的含义 |
|---|---|---|
| 根目录 `README.md` | 说明成员独立目录、数据契约及 Jira/PR 协作，模块表仅登记 M2 | 不是统一应用入口；M4 可以独立提交到 `agent4/` |
| `agent2/rental_agent/validation.py`、`contracts.py` | 数据类型/范围、模拟标记、JSON Schema 验证 | 说明团队重视可追踪结构化输入；M4 沿用此风格 |
| `agent2/rental_agent/engine.py` | 房源去重、三态硬筛选、确定性评分、完整合格列表与 Top 5 | 负责 UC03/UC04，不处理租约履行后的事实 |
| `agent2/rental_agent/report.py` | 推荐与偏好版本变化解释 | M4 只借鉴 JSON + Markdown 导出，不复用推荐分数 |
| `agent2/rental_agent/handoff.py` | 用户显式选房后生成本地选房证据包 | `prepared_not_sent` 不代表已自动发送或形成实际租约 |
| `agent2/data/`、`schemas/`、`reports/`、`tests/` | 模拟数据、契约、生成结果及测试 | 使用隔离依赖运行基线 71 项测试通过；无实时房源与地图接入 |
| `agent3/README.md`、`requirements.txt` | M3 的运行说明和依赖文件 | 说明文件与实现代码分布在不同目录，现有运行路径不能直接照抄 |
| **`agent3 /`（3 后有空格）** | 实际 `contract_agent/`、演示、Schema、报告、测试 | 在此实际目录运行 25 项基线测试通过；目录名在跨平台协作中易造成路径错误。此次不改 M3 文件 |
| `agent3 /contract_agent/document.py`、`extract.py` | 同意和文件检查、TXT/DOCX/PDF 提取、可用时本地 OCR、带位置字段 | 不应在 M4 重做合同提取；M4 当前要求租客确认结构化租约上下文 |
| `agent3 /contract_agent/rules.py`、`review.py` | 有限的版本化规则复核、人工决定、字段修订、Reviewed 后问题生成 | 合同复核结果不等于已签订租约，也不等于退租扣款责任判定 |
| `agent3 /contract_agent/intake.py`、`handoff.py` | M2 选房包接收、SQLite 请求收据、文档/版本绑定 | 有 M2→M3 本地契约；未发现已约定的 M3→M4 `TenancyRecord` 发布接口 |
| `agent3 /contract_agent/model_gateway.py` | 可选模型解释、校验、重试/回退 | 有接入点不等于真实模型服务已验证；M4 同样明确区分模拟网关测试与真实调用 |
| M1、M4、共享 Supervisor、统一 UI | 基线未发现对应完整模块 | 不应描述整个四 Agent 系统已经联调完毕 |

现有 `reports/` 是输出样例，不是另一套业务实现；`docs/superpowers/` 是已有设计和计划资料，不是运行依赖。本次没有访问 Jira 私有项目，也没有凭空为 M4 填 Jira 编号。

## 2. M4 的准确范围

Stage 1 报告第 10–13、18–19、33–37、62–68 页给出的职责是：

- **UC07 / FR07 / AD-M4-01**：以租客确认的退租日期、房间/家具和可用入住记录生成计划；任务可编辑，保留完成状态和证据；改期需租客审阅。
- **UC08 / FR08 / AD-M4-02**：组织押金记录、扣款主张、证据和带日期历史；争议转人工；无争议且租客请求时生成事实草稿；最终关闭由租客确认。
- **OF04 / AD-M4-03**：可选的本地提醒；Sydney 时间；改期、完成、关闭和取消订阅需抑制失效项。
- **SR01 / SR02**：案件与输入版本绑定、重复请求不重复产生结果、审核门禁及显式释放。

M4 不负责重新挑房、重排推荐、不以合同问题列表代替退租证据，也不替租客在 RBO/NCAT 提交行为。

## 3. 本次新增代码怎么拆

调用链：`CLI → AftercareAgent.submit → Schema / access / receipt / version → services.apply → planner / review / model / reminder → SQLite commit → JSON / Markdown`。

`AftercareAgent` 合并了本地路由和协调职责，是未来 Supervisor 可调用的入口；不是新增第五个业务 Agent。`services.py` 控制生命周期与审核，`model_gateway.py` 只提出受限候选，`store.py` 持有提交权限。生成成功不自动关闭案件。

以单案件聚合 JSON 存入 SQLite，是为了在初版中将更新、审核记录、提醒状态、版本、审计和请求收据一起提交。它比多个无事务 JSON 文件更容易验证失败回滚，但当前采用单机串行写入，不是分布式队列或生产数据库架构。

后续有真实统一层时，可拆分协调入口和持久化服务；不需要为了当前演示先复制 M1–M3 的未完成接口。

## 4. 初版为何能独立使用

租客直接提供 `TenancyRecord`，显式填写 `confirmed:true`、来源、版本、NSW 标准住宅租赁类型。缺失家具、房间等信息保留为 `null` 并提出问题。入住状况报告缺失会生成补证据任务，但不会假装有基线，也不会阻断所有退租操作。

押金案件可独立建立，无需先做 UC07；必须有押金编号或登记的押金凭证才能激活。照片/收据只是引用，不被自动识别或裁定。计划和押金使用同一案件中的证据登记表，从而避免跨案件借用 ID。

模型默认关闭。可选模型采用“选择已验证事实句”的受限结构；这是可运行的适配点和防止编造金额/引用的工程取舍，不是完整自然语言对话 Agent。

## 5. 与 Stage 2 的关系

Stage 2 评分材料分别考察设计实现、AI Agent 能力、Agile 过程和先进技术。本次有可执行服务、可复现演示、Schema、持久化与自动化测试，能支持其中的实现证据。没有真实模型服务测试、真实多 Agent 编排、用户研究、Jira 操作证据、生产部署或“活跃界面 60 秒提醒”验证；不能根据本次源码直接宣称这些指标完成或承诺分数。

建议下一轮按需推进：先补 M4 的真实模型服务演示或前端入口，再与 M3 确认 `TenancyRecord` 的确认语义、来源和版本映射，最后接入团队 Supervisor。任务号和贡献百分比应由小组实际确认。
