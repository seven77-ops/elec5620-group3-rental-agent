# ELEC5620 Group 3 统一前端实施交接方案

日期：2026-10-17（Australia/Sydney）。接收对象：负责统一前端与本地 Python 接口层的另一个开发窗口。

请实现一个可本地运行、能真实调用现有 Python 模块的课程演示应用。以“确认租房偏好 → 查看并选择房源 → 合同复核 → 租后服务”为主流程。Agent 1 目前使用明确标注的模拟输入；Agent 2、3、4 复用已有业务代码。优先交付可以完整操作和验证的功能，再完善视觉表现。

## 1 先读这些资料

### GitHub

- 小组仓库：<https://github.com/seven77-ops/elec5620-group3-rental-agent>
- 最新主分支：<https://github.com/seven77-ops/elec5620-group3-rental-agent/tree/main>
- 本方案核对的 main 基线：`b06614de1c7825d7fbc4bcc773a75efa4eb1da97`。开发前重新 fetch，保留之后出现的成员提交。
- 已合并 PR #1，输入样例与目录整理：<https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/1>
- 已合并 PR #2，Chenyang 实际 receive 结果及重试证据：<https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/2>
- Agent 2：<https://github.com/seven77-ops/elec5620-group3-rental-agent/tree/main/agent2>
- Agent 3：<https://github.com/seven77-ops/elec5620-group3-rental-agent/tree/main/agent3>
- Agent 4：<https://github.com/seven77-ops/elec5620-group3-rental-agent/tree/main/agent4>
- 跨 Agent 约定：<https://github.com/seven77-ops/elec5620-group3-rental-agent/blob/main/integration/README.md>
- Agent 1 模拟输入和外层交接元数据：<https://github.com/seven77-ops/elec5620-group3-rental-agent/tree/main/integration/agent1-to-agent2>
- Agent 2 现生成选房包：<https://github.com/seven77-ops/elec5620-group3-rental-agent/blob/main/integration/reports/2026-10-16/selection.selection.json>
- Agent 3 接收结果：<https://github.com/seven77-ops/elec5620-group3-rental-agent/blob/main/agent3/reports/scrum25-agent2-receive-2026-10-17.json>

先阅读各模块 README、data-contracts.md 和 schemas，再确定映射。网页链接跟随 main 更新；需要复现本方案基线时使用上述完整提交号。

### Jira

- 项目看板：<https://breezebee64.atlassian.net/jira/software/projects/SCRUM/boards/1>
- SCRUM 项目工作项：<https://breezebee64.atlassian.net/issues/?jql=project%20%3D%20%22SCRUM%22>
- SCRUM-2，偏好确认与房源评估：<https://breezebee64.atlassian.net/browse/SCRUM-2>
- SCRUM-4，Agent 1 偏好侧验证：<https://breezebee64.atlassian.net/browse/SCRUM-4>
- SCRUM-19，Agent 1 契约适配与最新版本绑定：<https://breezebee64.atlassian.net/browse/SCRUM-19>
- SCRUM-22，Agent 2 资格筛选与排名验收：<https://breezebee64.atlassian.net/browse/SCRUM-22>
- SCRUM-7，偏好版本比较：<https://breezebee64.atlassian.net/browse/SCRUM-7>
- SCRUM-25，Agent 2 → Agent 3 交接：<https://breezebee64.atlassian.net/browse/SCRUM-25>
- SCRUM-8，人工复核：<https://breezebee64.atlassian.net/browse/SCRUM-8>
- SCRUM-17，Agent 3 测试及演示证据：<https://breezebee64.atlassian.net/browse/SCRUM-17>
- SCRUM-11，模型辅助与交接/降级：<https://breezebee64.atlassian.net/browse/SCRUM-11>
- SCRUM-20，验收矩阵：<https://breezebee64.atlassian.net/browse/SCRUM-20>
- SCRUM-3，最终交付包：<https://breezebee64.atlassian.net/browse/SCRUM-3>
- SCRUM-12，团队 Review 记录：<https://breezebee64.atlassian.net/browse/SCRUM-12>

以上是已有任务的关联入口，不表示其中每项已经完成。先查看实际内容和当前状态；不要编造前端任务编号、成员确认或测试结果，也不要因为前端展示正常就关闭所有关联任务。是否新增统一前端工作项，应按现有看板分工落实，避免重复建单。

### Stage 1 报告

本机绝对路径：

`/Users/seven/Documents/AI_coding/5620房产Agent/ELEC5620_Group3_Stage1_report_副本.pdf`

[打开 Stage 1 报告](</Users/seven/Documents/AI_coding/5620房产Agent/ELEC5620_Group3_Stage1_report_副本.pdf>)

这是本机文件地址，适合同一台电脑上的另一个窗口读取；不是 GitHub 下载地址。若实施窗口在远端，需由用户另行提供这份附件。不要假定 clone 仓库会获得该 PDF，也不要把课程报告自动放进前端 public 目录。

重点阅读下表，页码为 PDF 页码，与这份报告印刷页码一致：

|页码|实施时需要提取的约束|
|---|---|
|10–16|FR01–FR08、OF01–OF04 及质量要求；第14页 NFR05/NFR06 涉及交互响应、可编辑摘要、文本状态、键盘操作和证据访问|
|25–28|UC01 收集草稿、UC02 校验/明确确认/保存版本/接收确认；DraftReady 不代表用户已经批准搜索|
|28–30|UC03/UC04 房源评估、推荐、解释和确认后版本比较|
|39–40|caseId/searchId/profileVersion/taskId 的分工、跨 Agent 数据流、独立合同处理同意及失败恢复|
|44–45、50、52–54|Agent 1 的草稿、确认版本、交接记录、对话及状态模型|
|其余 UC05–UC08 及 M4 章节|合同审查、人工复核、租客确认、退租计划、押金善后和可选提醒|

报告描述的是设计与验收目标；现有代码、已执行验证和拟实现能力必须区分。界面容器不能代替真实 Agent 1 或真实模型集成。

## 2 当前能力和本次范围

已核对的仓库目前没有网页前端或统一 HTTP 接口，主要通过 Python 函数、CLI 和 JSON/Markdown 交互。

|模块|已有能力|前端接入方式|
|---|---|---|
|Agent 1|结构化模拟偏好和交接元数据样例；真实对话、确认/版本服务尚待接入|先做标注“模拟 Agent 1 输入”的可编辑表单，页面点击产生本地演示确认记录；留出适配层|
|Agent 2|输入校验、去重、资格三态、确定性评分、Top5/完整排名、比较及明确选房后的证据包|薄接口调用原 Python 函数，显示原计算结果|
|Agent 3|合同读取、SelectedListingEvidence 校验、receive/SQLite 重试收据、规则提示、修正、人工决定和问题清单|复用接收与复核函数，单独记录合同处理同意，保存复核版本|
|Agent 4|AftercareAgent、SQLite、退租计划、任务、押金状态、争议门禁、草稿、提醒及导出|先以已确认租约表单独立进入；按 command Schema 调用现有 submit/get|

本次要交付统一页面、薄 API、必要的本地状态保存和可复现演示。Agent 2/3/4 的评分、规则、业务状态机和 Schema 不重写。默认使用合成数据，关闭外部模型调用。

M3 → M4 尚无双方确认的最终 TenancyRecord 输出约定。界面可以从合同复核结果预填候选资料，但必须展示来源、允许租客补齐/改正并明确确认，才能按 M4 现有契约创建案件。它是“用户确认后的表单衔接”，不得称作已有自动跨 Agent 接口。

## 3 推荐技术路线

推荐 **React + TypeScript + Vite + Ant Design，配 FastAPI 薄 Python 服务和本地 SQLite**。

|方案|取舍|
|---|---|
|推荐：React/Ant Design + FastAPI|页面和业务分层清晰，便于后续接入 Agent 1，以及展示确认、版本和复核门禁|
|备选：Python 快速界面框架|起步较快，但复杂状态、表格/抽屉和前后端接口演示会受其组件及执行模型约束|
|静态 JSON 展示页|只适合早期视觉稿；不满足本次真实调用、合同上传、版本与重试要求|

统一使用 Python 3.11+，覆盖各模块建议版本。Node 版本应满足所选 Vite 的实际要求；本方案查阅的官方文档要求 Node 20.19+ 或22.12+。新窗口应核对模板兼容性并提交 lockfile，不猜版本、不写未经安装验证的依赖号。[Vite 官方入门](https://vite.dev/guide/)

Ant Design 负责表单、步骤、表格、提示、抽屉和时间线等常规组件；自定义配色、间距和页面层级，避免整页堆满默认卡片。[Ant Design 官方文档](https://ant.design/docs/react/introduce/)

FastAPI 只封装现有函数与状态保存。文件上传使用官方支持的上传方式并安装对应 multipart 依赖；同意验证和文件生命周期必须按下文实现。[FastAPI 教程](https://fastapi.tiangolo.com/tutorial/)、[文件上传说明](https://fastapi.tiangolo.com/tutorial/request-files/)

默认只监听本机回环地址；开发期 Vite 通过 /api 代理后端。浏览器不能直接读服务器任意路径、执行 CLI 或保存模型密钥。不要引入云数据库、支付、外发消息、真实房源抓取或复杂账号体系。

## 4 页面和主要交互

主导航使用租客看得懂的名称：“租房偏好”“房源推荐”“合同复核”“租后服务”。可以增加一个首页概览和单独的演示操作员视图。Agent编号、请求ID、Schema和日志集中在可展开的“演示与证据”区域，不占据租客主流程。

### 4.1 概览

展示当前案例、当前阶段、每阶段可用操作、最近有效结果和需要用户处理的事项。显著显示“合成数据演示”和固定输入快照日期。未完成阶段写“待确认/待接入”，不能统一显示绿色完成。

导航可查看历史结果，但下一阶段的写操作受后端条件控制。Agent 4 允许既有租客从“直接填写租约资料”独立进入，不强迫其假装走完选房/合同阶段。

### 4.2 租房偏好

加载 integration/agent1-to-agent2/confirmed-profile.json 为演示初始值，同时注明来源是模拟输入，不伪装成已经经过 LLM 对话提取。

可编辑：预算与计价对象、账单范围、人数、租赁方式、目的地/交通方式/到达时间、入住窗口、租期、硬要求、软偏好和四维权重。完整取值与约束以 RentalProfile Schema 和 validate_profile 为准。

“保存草稿”“确认当前偏好”“生成推荐”是可区分的操作。必填项缺失或硬冲突时展示字段错误并阻止确认/搜索。未指定的业务值不自动编造；预置示例值须明确来自示例。确认按钮展示将被批准的摘要及版本。

确认后保存不可变正文、profile_fingerprint、草稿ID/修订号、确认者演示ID和确认时间。再次编辑产生新草稿并使“当前草稿已确认”标记失效，不覆盖旧确认版本。Agent 1 将来接入时替换此输入适配器，保留界面使用的稳定数据边界。

caseId 是整个租房案例；searchId 对应一次搜索；profileVersion 是已确认偏好版本；taskId 是调用/交接任务。只把 searchId/profileVersion 映射为 RentalProfile 的 search_id/profile_version，其他元数据留在外层。

### 4.3 房源推荐和比较

主区域展示最多5条推荐，允许展开全部合格排名。每条显示可比周费用、计价对象、通勤、偏好匹配分项、事实依据、取舍和输入时点。pending/excluded/duplicates 分开查看，保留具体澄清、失败检查和来源引用。

pending/excluded 的正式 score/rank 必须为空，不能显示成0分或混入排名。少于5条按实际数量展示，零匹配是有效结果；提供返回偏好草稿的入口，不自动放宽硬条件。

用户主动选中本批次任一 eligible 房源，展示选择摘要并确认后，再调用选房证据构建函数。不能自动选择Top1；支持下载实际生成的 .selection.json。过期、pending、excluded、重复记录、报告/数据不一致等拒绝情形原样清楚展示。

偏好修改比较必须基于重新确认的版本，并符合 compare_reports 对相同搜索、数据指纹、as_of、规则版本和数据模式的约束。展示 changed preferences、change_reasons、四维 score_contributions、资格/排名/分数前后值。新版本不符合纯偏好比较条件时，提示重新评估，不能伪造对比。

迟到的旧版本响应可以保留为历史，但不能覆盖当前确认版本。仅凭请求完成先后或相同 profile_version 不足以判断最新结果，还需核对搜索、正文指纹和批次引用。

### 4.4 合同复核

页面先展示用户已选择的房源摘要；还没有选择时清楚说明。正常链路将实际生成的证据包交给 receive，而不是把完整 RecommendationReport 改名代替。独立合同审查作为现有能力可以单列，必须标明缺少选房交叉核对。

合同文件与选房包分开。先明确取得并记录合同处理同意，再允许读取/上传/写入/分析合同；不得由“选房确认”推断合同同意。为避免 multipart 处理器在同意校验前读取文件，采用“创建同意记录 → 凭该记录上传”的两步流程，并确认服务端中间件/依赖顺序确实在解析文件前验证同意。撤销/未同意时不落盘、不分析。

只用合成合同演示。支持格式/限制复用 Agent 3：TXT、DOCX、PDF，最多2,000,000字节、PDF最多10页；扫描PDF依赖本机OCR工具，缺少工具时应清楚要求文字版/更清晰副本，不显示解析成功。

调用 receive_review 后展示 review_id/version/status、提取字段与原文位置、findings、规则引用、人工复核需求和问题清单。点击来源可打开受控的文本/引文视图，不将合同原文当作 HTML 执行。

必须保留 Reviewed、Awaiting Human Review、Awaiting Resubmission、Degraded Summary Only、Questions Ready 等不同状态。Reviewed 不等于合法认证、签约批准或已签约。高风险等待操作员决定；没有发现项时不编造问题。

字段修正复用 correct_review，生成新版并使旧问题失效。人工决定复用 approve_review，在独立的“本地演示操作员”视图明确模拟身份；租客页面没有放行按钮。questions 只在后端允许的状态调用 generate_questions。问题包仍为 prepared_not_sent，下载不等于发送给房东。

同一逻辑请求重试保留 request_id、合同内容、选房包、参考日期及同意上下文。同ID不同输入展示冲突；不要每按一次重试就生成新ID。

### 4.5 租后服务

先做“确认租约资料”表单，可从 Agent 3 预填合同地址等候选事实，保留来源 review_id/version 与字段引用。只有用户补齐并确认 M4 契约必要资料后才创建 TenancyRecord；ID 映射保存在协调层，不把 search_id、review_id 或任意用户名直接混用为 M4 tenant_id/tenancy_id。

表单和服务端使用 agent4/schemas/tenancy-record.schema.json 等实际文件名，以读取到的仓库内容为准。字段包括租约/租客标识、地址、NSW标准住宅类型、来源引用/版本、房间和家具等，不能因合同 Reviewed 自动填写 confirmed:true。

提供退租日期、计划生成/确认、任务编辑与完成、证据引用、日期变更提案及确认。改期确认前保留旧计划、完成状态与证据；显示未决澄清和 evidence_gaps。

押金页展示原始状态、时间线、reported_claim、待审核事项、跟进草稿和用户确认结果入口。金额按 M4 的 AUD 整数分输入/存储，界面可格式化为元；不得把报告中的租金浮点数直接当作分。扣款记录不表示租客接受扣款。

operator_decision 只通过服务器配置的演示操作员允许列表执行；浏览器提供一个 actor_role 字符串不能获得权限。annotate/return/hold/refer 不应在UI表现为放行。关闭或撤回需要租客明确操作。

提醒默认关闭。用户开启后，活跃页面可以每30秒调用一次既有 poll_reminders 操作，并保持请求去重、版本检查与时间单调性。每次新的轮询是新操作；网络重试则复用原请求。展示本地提醒收件箱，完成/改期/关闭后的旧提醒应被抑制。没有常驻调度时，不宣称页面关闭后还能准时提醒。

## 5 必须复用的代码入口

|模块|入口与约束|
|---|---|
|Agent 2|rental_agent.engine.evaluate(profile, dataset, as_of=None)|
|Agent 2 比较|rental_agent.report.compare_reports(before, after)，复用服务端结果及 render_markdown|
|Agent 2 选房|rental_agent.handoff.build_selected_listing_evidence(report, dataset, listing_id, selected_at=..., user_confirmed=...)|
|Agent 2 契约|validate_profile / validate_dataset 及 contracts.validate_contract；不要在JS重写评分公式|
|Agent 3 读取|contract_agent.document.load_document(path, consent=...)；只有已验证同意的受控上传路径|
|Agent 3 接收|contract_agent.intake.receive_review(document, consent=..., selection=..., request_id=..., as_of=..., store=..., gateway=None, allow_external_ai=False)，返回 review 与 newly_created|
|Agent 3 后续|contracts.validate_review、review.correct_review / approve_review / generate_questions，保留版本及状态门禁|
|Agent 4|aftercare_agent.store.AftercareAgent(database, operator_ids=..., gateway=None)，调用 submit(command_dict) / get(case_id, actor_id, role='tenant')|

以上目录现不是统一可 pip 安装的应用包。薄服务可以在启动时集中配置包搜索路径，或增加轻量的安装配置；不要把路径修改散落到每个路由，也不要为方便启动移动/复制成员业务代码。优先直接调用 Python 入口，不拼接 shell 命令执行用户内容。

## 6 拟新增的 API 与持久化边界

以下 URL 是本方案拟定的接口，不是当前仓库已经存在的服务。实现窗口应在 server README 和 OpenAPI 中给出最终请求/响应示例。

|拟定路由|职责与关键条件|
|---|---|
|GET /api/v1/health、GET /api/v1/demo-config|健康、实际能力、数据模式、各模块演示时钟和未接入能力|
|POST /api/v1/cases、GET /api/v1/cases/{caseId}|创建/读取演示案例；保存阶段与映射，不编造后续业务完成状态|
|POST /api/v1/cases/{caseId}/profile-drafts|创建或修改草稿，带当前修订号；保留旧确认版本|
|POST /api/v1/cases/{caseId}/profile-confirmations|确认精确草稿修订与正文指纹，保存演示确认记录|
|POST /api/v1/cases/{caseId}/evaluations|仅用保存的已确认版本和受控数据快照评估；支持可核对的比较结果|
|GET /api/v1/evaluations/{runId}|取原始结果、完整排名、状态和来源；下载采用专门受控输出入口|
|POST /api/v1/cases/{caseId}/selections|用户明确选择后复核资格，保存并返回真正的SelectedListingEvidence|
|POST /api/v1/cases/{caseId}/contract-consents|记录独立合同处理同意；为随后受控上传提供服务器记录引用|
|POST /api/v1/cases/{caseId}/contract-reviews|验证同意引用后接收上传，调用receive；绑定原选房包与请求ID|
|GET /api/v1/contract-reviews/{reviewId}|读取复核JSON、版本、证据与状态|
|POST /api/v1/contract-reviews/{reviewId}/corrections、/decisions、/questions|包装现有修正/人工决定/问题函数；每次写检查预期版本和允许的演示角色|
|POST /api/v1/aftercare/commands、GET /api/v1/aftercare/cases/{aftercareCaseId}|严格校验/限制M4命令，服务器绑定案例和演示身份，再调用submit/get|

新增 HTTP 层的ID/引用必须引用服务端已保存对象；不能由浏览器提交任意文件路径读取服务器。HTTP错误统一包含 code/message/request_id，可含字段错误，保留底层语义。区分格式错误、缺失信息、版本冲突、重复输入冲突、需要人工复核和服务失败；不要全部转成“无匹配”。

保存案例、草稿、不可变确认版本、数据快照引用、推荐报告、选择包、合同同意及文件引用、复核结果/版本和调用收据。M3 接收收据和 M4 业务数据优先沿用原 SQLite 实现；协调层可用单独 SQLite 管理关联，不直接改成员数据库内部结构。

Browser 的 localStorage 仅保存非敏感UI偏好或当前案例引用，不作为已确认版本、复核状态和重试收据的唯一来源。刷新后应恢复上次已提交案例和有效结果。失败不清空旧结果；新版本结果不能被旧请求晚返回覆盖。

外层 request_id 与模块的 recommendation_run_id/selection_check_run_id/review_id 含义不同，不能互相替代。M4 expected_version 和 as_of 必须按原契约处理。幂等重试复用最初已保存请求内容，不能在重试时悄悄换成“当前时间/最新版本”。

本地演示身份由服务器配置，页面标明“本地演示身份”；不宣称实现生产登录和跨账户隔离。所有上传文件、数据库和生成报告放在忽略的运行目录，不能落进frontend/public、源码或常规请求日志。

## 7 演示时钟与历史数据

这是第一阶段必须解决的接入问题，不能等页面完成后再修。

- 房源数据 as_of 为 `2026-09-17T09:00:00+10:00`，字段观察时间更早。复现现有选房成功路径时，明确启用“固定合成场景回放”，使用 expected.json 中的 selectedAt：`2026-09-17T10:00:00+10:00`。
- Agent 3 合成合同复核的规则参考日期为 `2026-10-15`。Agent 4 的演示命令有自己的带时区时间线，以原始样例为准。
- 这几个时点不能混成一个“当前时间”。界面分别标明快照、选择、规则参考及实际生成/操作记录时间。
- 用真实当前时点复核旧房源时应按原规则返回过期，提示需要新快照；不得把旧evidence.observed_at改成今天，也不得移除24小时检查。
- 固定场景演示中的 selected_at 是明确披露的模拟业务时间，不是声称用户今天已在当时操作。真实模式需要真实更新的数据适配器，本次不实现。
- M4 操作时间必须不早于其上一条提交，提醒在活跃页面内使用统一的服务器演示时钟；不能由任意前端日期字符串绕过时序检查。

## 8 视觉与可用性

采用清晰的学生租房服务界面：浅色背景、深蓝主色、少量青绿色强调；文字层级清楚，内容区以表单、列表、证据抽屉和时间线为主。不要把课程演示做成充满装饰图表的后台模板。

桌面使用侧边阶段导航和主内容区；窄屏改为顶部步骤/折叠菜单。至少检查360、768、1440像素宽度。合同原文、长来源、中文地址、长错误信息和空列表都应可读，不挤破页面。

关键控件必须有标签，能通过键盘操作。loading、成功、错误、pending、人工复核和缺少数据使用文本说明，不能只靠颜色。提交时禁用会重复写入的按钮；重试恢复同一个逻辑请求。错误提示说明下一步该补什么，不泄漏服务器绝对路径或堆栈。

常用中文产品文案示例：“确认当前偏好”“查看推荐依据”“选择此房源”“同意处理此合同”“等待人工复核”“确认租约资料”。“导出”明确是本地下载，不暗示已经发送给房东/其他角色。

## 9 建议代码组织

新增 frontend/ 和 server/，成员模块保持原目录。

```text
frontend/
  package.json
  src/
    app/                  路由、布局、页面错误边界
    pages/                概览、偏好、推荐、合同、租后服务、演示操作员
    components/           证据抽屉、状态文本、确认摘要、空/错误状态
    api/                  HTTP客户端、DTO和统一错误处理
    state/                当前案例、草稿及请求版本控制
server/
  app/
    main.py               FastAPI入口
    routes/               只负责HTTP转换，不计算业务评分
    adapters/             Agent1模拟、Agent2、Agent3、Agent4包装
    repository/           案例/确认版本/关联/文件引用与幂等记录
    settings.py           根目录、数据路径、演示身份、时钟、模型关闭
  requirements.txt
  tests/
integration/
  tests/                  保留既有6项；必要时增加Web边界集成验证
docs/frontend/
  implementation.md      启动、接口和完成边界
  verification.md        实际命令、预期/实际、截图、PR/Jira引用
```

目录名称可以按仓库习惯小幅调整，但职责分离和现有模块路径必须保留。不要改回带尾随空格的目录。不要为了前端重排已有合成报告、Schema或测试文件。

## 10 开发顺序和阶段交付

### 阶段一 基础与偏好确认

建立 frontend/server 和启动说明；实现统一布局、演示模式提示、案例保存、模拟偏好编辑与明确确认。固定各时钟，完成输入/输出DTO及服务端引用约束。交付可编辑、可确认、刷新可恢复的实际页面。

### 阶段二 Agent 2 到 Agent 3 闭环

接入 evaluate、比较、资格列表、用户选房、证据包下载；接入合同单独同意、合成合同上传、receive、原文证据、重试和复核展示。正常路径和租金冲突路径必须可在浏览器实际操作。

### 阶段三 租后服务与人工门禁

完成M4确认资料表单、独立入口、计划/任务、改期、押金时间线、跟进草稿与可选提醒。接入演示操作员的现有决定函数，验证租客没有放行权限。M3→M4 使用明确标注且经用户确认的预填表单，不绕过未统一的契约。

### 阶段四 验收与演示资料

浏览器检查完整主流程及异常状态，修复发现的问题，提交实际验证记录、截图和复现命令。先确保闭环真实可用，再做视觉细化。界面部分使用合成输入不代表真实Agent1、真实LLM或生产投递已完成。

## 11 验收清单

|编号|场景|必须观察到的结果|
|---|---|---|
|F01|未确认偏好直接评估|前后端均拒绝；未创建伪造已确认版本|
|F02|修改预算/权重后重算|新草稿重新确认，新版本报告；旧版仍可查看，旧异步响应不覆盖新结果|
|F03|固定合成快照正常评估|30输入→15合格/9待确认/5排除/1重复；最多展示5条，通勤样例Top1 DEMO-006、92.75分|
|F04|未知/冲突/硬失败与零匹配|pending/excluded不排名；零匹配不等于系统失败，不自动放宽条件|
|F05|未选择、选pending/excluded或证据过期|服务端不能生成有效选房包；正常明确选择生成可Schema校验的真实包|
|F06|同源重复/冲突的证据查看|可从原结果定位来源/观察时间与输入快照，不编造引用或刷新时间|
|F07|未同意合同处理|不读取/落盘/分析合同；不能复用选房确认代替同意|
|F08|DEMO-006加对应合成合同|receive结果Reviewed，ID/版本/指纹和两份JSON关联一致；无发现不编造问题|
|F09|相同请求重试与同ID改内容|同内容返回同一复核ID及原报告；改内容返回明确冲突，不重复创建/覆盖|
|F10|合同租金500改650、或地址差异|Awaiting Human Review；人工决定前不能生成问题，不自动进入“可签约”|
|F11|合同提取失败/过大/规则过期|可读错误或对应暂停状态；先前有效结果保留；没有假成功|
|F12|合同字段修正|复核版本递增，旧问题失效，保留旧版本依据|
|F13|Reviewed但租约资料未确认|不能自动创建已确认M4案件；用户确认表单后才调用create|
|F14|退租改期和任务证据|提案确认前保留原计划，确认后按原逻辑更新且保留完成/证据记录|
|F15|押金争议与操作员门禁|进入UnderReview；普通租客不能放行；只有符合原服务条件的演示操作员决定生效|
|F16|关闭与提醒|关闭需要明确确认；提醒显式开启、不重复、完成/改期/关闭后抑制；页面关闭不保证后台投递|
|F17|版本冲突/超时/刷新|请求身份与输入保持；旧结果可见；明确区分接收、运行完成、部分报告及失败|
|F18|布局和可访问性|360/768/1440可用；键盘可操作，状态有文本，长证据不溢出|
|F19|数据与密钥边界|无真实数据/外发，前端构建和日志没有密钥；上传路径受控，导出按保存结果生成|
|F20|现有功能回归|Agent2 71项、Agent3 25项、仓库交接6项保持通过；Agent4按当时实际发现数量执行，不凭空填写数量|

不要求为低风险样式细节编写镜像式测试。重点测试确认门禁、版本绑定、重试、上传边界、人工审核和真实模块调用。API/UI端到端测试应验证可观察结果，不以硬编码假响应冒充接入。

最低实际检查命令由实施窗口补成可运行脚本：frontend类型检查/构建、关键交互或浏览器端到端检查、server边界测试，以及以下原有测试。示例工作目录与Python虚拟环境须在README写清：

```sh
# 仓库根目录，装好各模块依赖后
(cd agent2 && python -m unittest discover -s tests -v)
(cd agent3 && python -m unittest discover -s tests -v)
(cd agent4 && python -m unittest discover -s tests -v)
python -m unittest discover -s integration/tests -v
```

Stage 1 NFR05/NFR06 的量化响应/用户测试仍需按报告实际测量。几张截图、开发者自己跑通或一个loading提示，不等于达到五用户/并发/时延等验收目标。

## 12 仓库协作与最终交付

实施窗口使用干净 checkout 或隔离工作区，先检查 remote/status/AGENTS.md 和适用技能。不要假定存放PDF的本机目录就是GitHub最新代码，也不要在存在大量课程附件的目录里执行 git add .。

从最新main建立 codex/ 前缀的前端分支，例如 codex/frontend-demo。仅提交相关前端、薄服务、依赖锁、测试和文档；保留成员业务代码。通过PR集成，附实际验证命令和结果，创建后关联到当前聊天。不要改写历史或强推覆盖组员提交。

最终至少交付：

- 能在本机打开的统一页面和实际可用的Python接口；README给出前后端准确启动命令与地址。
- Agent 1模拟模式、真实模块接入、M3→M4人工确认衔接与未实现范围的准确说明。
- 正常流程、零匹配、无合同同意、版本变化、重复请求、合同冲突和M4审核/提醒的可复现场景。
- 关键截图、实际测试/构建日志、预期与实际结果，以及GitHub PR/提交和对应Jira记录链接。
- 现有业务测试不回退，保存的输入输出不被随意覆盖，下载内容与页面展示一致。

本次方案用于交接实施，不包含对真实用户/教师验收已经通过的声明。不要把UI做出来后直接关闭SCRUM-19、22、25、11或最终验收任务；按其实际条件逐项确认。

## 13 可复制给另一个窗口的任务说明

请根据本方案实现 ELEC5620 Group3 的统一前端和薄 Python 接口。先读取本文列出的 Stage 1 PDF、GitHub main、各 Agent README/契约及 integration 样例，再检查工作区状态和适用技能。复用 Agent2/3/4 的真实 Python 入口；Agent1先明确使用模拟已确认偏好，M3到M4经租客确认表单衔接。优先完成“确认偏好→推荐→明确选房→独立同意合同处理→Agent3复核”的可点击闭环，再接入M4已有功能。严格保留确认、版本、资格、证据时效、重试及人工审核门禁。处理固定演示时钟，不能篡改原证据日期。用隔离的codex/分支开发，验证后提交PR、启动说明、截图和实际验收记录。遇到范围不明时先核对报告和代码；不要重新设计评分算法、伪造真实Agent1/模型调用，或擅自扩展到真实房源、付款和外发消息。
