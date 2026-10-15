# Agent 2：UC03／UC04 用例规约与课程功能

版本：v2.0｜日期：2026-09-17｜负责人：Member 2（房源分析与推荐）

本文件按用户确认的分工定稿，用作课程文档与后续行为图的基准。团队工作簿是参考，不照搬其“抓取即验证真实”“关键词即诈骗”等结论。原个人 UC-01／UC-02 编号停止使用，避免与 Member 1 冲突。

课程范围按“每人两个必须功能＋一个可选功能、两个用例”准备。参考材料另写每人至少1个完整用例、全组5–10个；四人各两个共8个，可覆盖两种数量表述，但具体评分仍以正式rubric为准。

## 1. 功能与职责边界

| 功能 | 分类 | 内容 | 对应用例 |
|---|---|---|---|
| F1：房源整理、数据检查与资格评估 | 必须 | JSON导入、租金口径标准化、去重、证据/时效检查、硬条件及未知项判断 | UC03 |
| F2：个性化评分、推荐与解释报告 | 必须 | 确定性评分、Top5、分项分数、取舍、待确认项及来源，形成可交接报告 | UC04 |
| F3：基于新版偏好的排名变化比较 | 可选，已实现 | 接收上游已确认的新偏好，比较同一批房源的状态、排名、分数变化 | UC04-A1 扩展 |

**Member 1** 负责收集、修改、确认偏好和保存历史版本（团队 UC01／UC02）。**Member 2** 消费已确认的 `RentalProfile`，不擅自改预算、校区或租期。**Member 3** 负责合同审查和法律风险判断。Member 2 不把推荐分数视作签约批准。

当前实现是本地模拟工具核心。输入中的“确认”是调用前置条件，尚未实现用户鉴权、签名或上游确认工作流。JSON Schema只能验证结构，不能证明用户真的确认过。

## 2. UC03：Analyse and Evaluate Property Listings

### 2.1 用例规约

| 字段 | 定稿内容 |
|---|---|
| Use Case ID & Name | UC03: Analyse and Evaluate Property Listings（分析与评估房源） |
| Primary Actor | International Student Tenant；通过 Agent 1 或演示者提交任务 |
| Secondary Actors | Tenant Advisor Agent（Agent 1）、Listing Data Provider；数据校验/通勤/评分是内部组件，不额外算团队成员 |
| Goal | 将候选房源整理为可比较的数据，明确资格、缺失、冲突和排除原因，为UC04提供依据 |
| Preconditions | 调用方提供已确认的 RentalProfile；存在合法候选快照（可为空）；明确评估时点；当前仅接受模拟数据 |
| Trigger | 租客请求评估候选房源，或 Agent 1 转交已确认需求和候选快照 |
| Success Postconditions | 每条输入归入合格、待确认、排除或重复之一，保留硬条件检查及证据；原始输入未修改 |
| Minimal Guarantee | 非法输入不产生成功推荐；未知不被写成满足；失败不自动放宽条件 |

### 2.2 Main Flow（固定步骤编号）

| 步骤 | 执行者 | 行为与输出 |
|---|---|---|
| UC03-M1 | Agent 1／演示者 | 提交已确认的 RentalProfile、候选房源JSON和固定as_of |
| UC03-M2 | Agent 2 | 验证Profile Schema及预算、日期等业务规则；验证房源结构与模拟标记 |
| UC03-M3 | Agent 2 | 统一周租比较口径；同来源ID、同事实去重，保留有效字段证据，不合并同地址不同单间 |
| UC03-M4 | Agent 2 | 检查来源许可声明、房源/证据时效、字段冲突；检查预先提供的通勤与目的地/时段/模式是否匹配 |
| UC03-M5 | Agent 2 | 对预算、通勤、租赁类型、入住范围、租期和必须设施生成 pass／fail／unknown 检查 |
| UC03-M6 | Agent 2 | 检查有权重评分维度的数据完整性；已知违反硬条件则排除，未知或冲突则待确认，完整候选交UC04 |
| UC03-M7 | Agent 2 | 保留每条房源的检查原因、证据和去重结果；必要时通过 clarification_requests 请求 Agent 1 补充信息 |

说明：上述是业务步骤，不表示代码已有七个独立服务。目前 UC03 与 UC04 共用一次 `evaluate(profile, dataset)`，内部完成整理、资格检查与评分，最终统一输出 `RecommendationReport`。没有单独持久化的“UC03数据库”。

### 2.3 Alternative / Exception Flow

| 编号 | 从哪一步分支 | 条件 | 行为及返回位置 |
|---|---|---|---|
| UC03-E1 | M2 | 缺必要偏好、格式错误、未知版本、错误类型、NaN或真实数据混入 | 返回字段级错误；停止本次运行。由Agent1确认修订后重新从M1开始 |
| UC03-E2 | M3 | 相同来源ID且事实一致 | 保留一条评估记录并合并有效证据；其他项列入duplicates，继续M4 |
| UC03-E3 | M3–M4 | 同源事实冲突、字段冲突、许可不明或过期 | 标记待确认，不宣称诈骗或真实；保留原因，进入M7等待补充/人工核对 |
| UC03-E4 | M5 | 已知超硬预算、超通勤、类型/入住/租期/必须设施不满足 | 标记excluded，保存具体原因；继续检查其他候选 |
| UC03-E5 | M4–M6 | 账单、起租日期、位置精度、关键证据或有权重软指标未知 | 标记pending，不补造默认事实；后续可显示分数范围，不正式排名 |
| UC03-E6 | M1 | 候选数组为空 | 接受合法空快照，产生0候选结果，由UC04说明不足，不伪造房源 |

同一房源同时存在已知硬条件失败和其他未知时，优先归为excluded，同时保留未知问题。人工补充数据后必须重新评估，不直接把pending改成eligible。

### 2.4 验收与代码映射

- 30条样本归为15条合格、9条待确认、5条排除、1条重复。
- DEMO-016超预算、DEMO-017超通勤排除；DEMO-021账单未知待确认；DEMO-028作为DEMO-001的重复记录处理。
- `validation.py` 对应M2；`engine.py:evaluate` 的去重逻辑对应M3；`evaluate_listing` 对应M4–M6；报告字段保留M7输出。
- 测试：`test_hard_failures`、`test_unknown_hard_facts_are_pending`、`test_conflicting_duplicates_quarantined`、`test_duplicate_uses_fresh_evidence`、`test_demo_fixtures_and_profile_ranking_change`。

## 3. UC04：Recommend and Compare Properties

### 3.1 用例规约

| 字段 | 定稿内容 |
|---|---|
| Use Case ID & Name | UC04: Recommend and Compare Properties（推荐与比较房源） |
| Primary Actor | International Student Tenant |
| Secondary Actors | Tenant Advisor Agent（Agent 1）、Contract Agent（Agent 3，仅用户选定后的交接目标） |
| Goal | 根据已确认偏好生成可解释推荐，帮助租客比较费用、通勤与居住取舍 |
| Preconditions | UC03的数据检查和资格分析已执行；使用明确的Profile版本、数据快照与评分版本；允许没有合格候选 |
| Trigger | 租客请求推荐，或UC03检查完成后继续执行 |
| Success Postconditions | 生成通过契约校验的RecommendationReport，含推荐批次ID、最多5条推荐、完整分项和证据 |
| Minimal Guarantee | 不将pending/excluded纳入正式排名，不自动选房、发送消息、预约或签约 |

### 3.2 Main Flow（固定步骤编号）

| 步骤 | 执行者 | 行为与输出 |
|---|---|---|
| UC04-M1 | Agent 2 | 读取UC03检查结果及已确认的Profile版本；锁定数据快照、as_of和规则版本 |
| UC04-M2 | Scoring Engine（内部函数） | 对完整合格候选计算通勤、费用、居住、便利四维分数；归一化用户权重 |
| UC04-M3 | Scoring Engine | 按未舍入总分降序、房源ID升序稳定排序；提取最多5条，保留全量合格排名 |
| UC04-M4 | Agent 2 | 依据事实模板生成满足项、妥协项、缺失信息及来源；说明通勤中的步行/换乘，不改写分数 |
| UC04-M5 | Agent 2 | 构建RecommendationReport，生成recommendation_run_id与指纹，校验Schema及输出结构 |
| UC04-M6 | Agent 2 → Agent 1／租客 | 返回JSON与Markdown推荐表、排除/待确认清单和澄清问题，等待用户决定 |

默认权重沿用现有方案：通勤35%、费用30%、居住20%、便利15%。硬条件先筛选，不作为可被抵消的奖励分。地图、滑块、LLM解释和真实TfNSW请求均不是当前主流程已实现能力。

### 3.3 Alternative / Exception Flow

| 编号 | 分支点 | 条件 | 行为及去向 |
|---|---|---|---|
| UC04-E1 | M2–M3 | 合格候选不足5条或为0 | 只返回实际数量，说明排除/缺失原因；经Agent1询问是否调整要求，不擅自放宽 |
| UC04-E2 | M2 | 有权重软维度缺失 | 保持pending，score=null，展示已知分项和缺失范围；不参与Top5 |
| UC04-E3 | M5 | 契约校验失败 | 返回错误，不输出成功报告；修正接口数据后重试 |
| UC04-E4 | M6 | 本地目标输出已存在或写入失败 | 拒绝覆盖或报告写入错误；不发送交接消息，换新文件前缀重试 |

### 3.4 UC04-A1：新版偏好重算与比较（F3，可选）

1. Agent 1 确认修改并提供新版RentalProfile；Agent 2不替用户编辑或确认。
2. 使用同一候选快照和时点，分别执行原/新偏好的UC03与UC04。
3. 记录变更字段、两次批次ID及所有候选的资格/排名/分数变化；不只比较Top5。
4. 输出新版Top5及对比表，原输入和原报告不变。

异常：不同数据/时点/规则的报告不得直接用于纯偏好比较；新目的地无匹配路线则待确认；收紧预算后失去资格显示“合格→排除”；未变更则保持结果，不制造差异。偏好版本存储及递增由Agent1负责，本地函数不实现版本数据库。

### 3.5 UC04-A2：用户选定后的证据包交接

这是F2报告使用后的交接分支，不新增顶层Agent或第四项个人功能。

1. 用户明确指定房源ID和选择时间；不自动采用Top1。
2. Agent 2 根据同一数据集复算原报告，确认批次引用与报告内容一致。
3. 在选择时点复查所选房源资格及证据时效。不存在、重复、pending、excluded或过期候选均不能直接交接。
4. 生成SelectedListingEvidence，保留原房源、相关来源记录、评估证据、价格口径、未解决事项和两个批次引用。
5. 本地状态为 `prepared_not_sent`。团队联调后才由编排层发送给Agent3；当前代码没有执行发送。

用户未确认或校验失败时停止本分支，不把未知项改成“已验证”。存在合同条款不确定性时由Agent3或人工处理，推荐模块不替代法律判断。

### 3.6 演示与验收

UC03＋UC04基础流程：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --output reports/uc03-uc04-demo
```

UC04-A1比较：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --compare-profile data/demo/profiles/budget.json --listings data/demo/listings.json --output reports/uc04-compare-demo
```

UC04-A2明确选房（固定模拟时点）：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --select-listing DEMO-006 --selected-at 2026-09-17T10:00:00+10:00 --output reports/uc04-selection-demo
```

验收：通勤优先Top1=DEMO-006（92.75）；预算优先Top1=DEMO-012（89.80），DEMO-002由第9升到第3。选择DEMO-006可生成证据包，选择DEMO-021（待确认）必须拒绝。相同输入及时点重试的逻辑批次ID保持一致。

测试：`test_uc03_uc04_export_and_no_overwrite`、`test_uc04_optional_compare`、`test_report_run_id_is_stable_and_input_sensitive`、`test_explicit_selection_contains_traceable_snapshot`及选房拒绝测试。

## 4. 数据交接与行为图基准

| 契约 | 方向 | 职责 |
|---|---|---|
| RentalProfile | Agent1 → Agent2 | 用户已确认的需求内容；确认与历史版本由上游负责 |
| RecommendationReport | Agent2 → Agent1／租客 | 推荐、原因、缺失、排除、批次与证据 |
| SelectedListingEvidence | Agent2 → Agent3（用户选定后） | 具体房源、原始记录、金额、证据和未解决事项；当前仅本地生成 |

详细字段、JSON Schema、版本及示例见[数据契约说明](data-contracts.md)。

后续活动图应引用UC03-M1–M7与UC04-M1–M6；顺序图中明确Agent、内部函数和外部参与者，不能把每个函数都画成新Agent。状态机至少区分房源评估的eligible/pending/excluded/duplicate，与交接包的prepared_not_sent；不要把后者误写成已发送或已签约。

“等待人工确认”目前通过pending、issues及clarification_requests表达，尚无人工工单、Supervisor调度、数据库状态机或消息确认机制。本次不绘图；以上编号为下一步建模的统一基准。
