# Agent 1 输入约定与 Agent 2 → Agent 3 本地联调

本目录准备上游输入和跨模块可运行样例。**截至 2026-10-20，PR #6 中的 Agent 1 已实现偏好澄清适配、显式确认、不可变版本存储、Agent 2 本地调用和推荐版本比较；独立脚本已跑通 Agent 1 → Agent 2 → Agent 3。** 所有 ID、偏好、房源及合同均为合成数据；脚本确认不能证明真人已批准。实际 LLM 对话质量、组员共同验收、统一前端接入与跨机器投递仍待验证。实现与审核入口：[PR #6](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/6)；[Agent 1 验证说明](../agent1/VALIDATION.md)。

## 1. 给 Yirui 的输入样例

|文件|用途|
|---|---|
|[confirmed-profile.json](agent1-to-agent2/confirmed-profile.json)|实际传给 `evaluate(profile, dataset)` 的 RentalProfile 1.0；必须符合 [上游 Schema](../agent2/schemas/rental-profile.schema.json)|
|[handoff.json](agent1-to-agent2/handoff.json)|拟定的协调层交接示例；保存案例、搜索、任务、确认及原始草稿引用，**不是已上线的 API 格式**|
|[expected.json](agent1-to-agent2/expected.json)|固定模拟数据下的预期分流、Top1、选房时点和合同参考日期|

Agent 1 提供偏好，房源快照由 Agent 2/协调层另行提供。不要把交接外层对象直接当作 RentalProfile 传入，也不要将 caseId、taskId 或 confirmation 追加到严格的偏好正文。

|外层字段|Agent 2 对应字段/处理|
|---|---|
|caseId|租房案例标识；协调层保存，**不映射成 search_id**|
|searchId|映射 `profile.search_id`，本例为 DEMO-SEARCH-INTEGRATION-001|
|profileVersion|映射 `profile.profile_version`，本例为1|
|profileFile|相对交接文件定位已保存的偏好正文；真实接口的文件路径必须由调用方限定到可信存储|
|profileFingerprint|必须与正文指纹一致；算法沿用 `rental_agent.engine.fingerprint`，不是签名或身份验证|
|taskId|稳定的交接任务ID；同一逻辑请求重试保留ID，内容改变使用新请求|
|confirmation.confirmed / confirmedBy / confirmedAt|显式确认声明、确认者和带时区时间；真实应用应从可信用户操作获得，不能让LLM代填批准|
|confirmation.sourceDraftId / reviewedDraftRevision|被用户确认的草稿及其修订号；草稿修订3与确认后profile版本1不是同一计数器|
|exampleOnly / dataMode|本例为true / synthetic_demo，提醒调用方这是演示样例|

Agent 1 的本地适配器现已检查保存的确认版本、必填信息及未决硬冲突，绑定搜索/版本/指纹后把**正文**交给 Agent 2；确认信息留在协调外层。`handoff.json` 仍保留为固定接口样例，Agent 1 的 `/export` 则生成实际本地运行对应的交接文件。JSON Schema 校验只能证明形状，不能替代用户确认；这里的本地适配器不代表生产网络投递服务。

版本和异常规则：

- 必填偏好未明确、硬条件冲突未解决或用户未确认：留在 Agent 1 草稿，不调用评估。非必要偏好明确为未指定，不能擅自补业务默认值；必需的评分权重及其含义须与用户确认。
- 修改已确认偏好：保留旧版本，建立新草稿，重新校验与确认，再保存新 profile_version。不得原地修改旧版正文。
- LLM解释失败：保留原草稿，不覆盖已收集的信息。保存失败：不启动交接。
- 接收端确认接收后才能记录交接成功；接收成功不等于评估完成。超时/未确认请求先核对状态或去重，再重试。
- 显示推荐时核对 search_id、profile_version、profile_fingerprint 和 recommendation_run_id，防止旧请求晚返回覆盖新结果。
- 零合格是有效结果；技术错误或过期反馈不能当作零匹配来要求用户放宽条件。改偏好始终需要再次确认。

## 2. Agent 2 → Agent 3

Agent 3 已统一到无尾随空格的 `agent3/`。原来的 `agent3 /` 文件按原内容移动，评分、合同抽取和规则逻辑均未修改。用户会与 Chenyang 口头确认这份接口约定；本地检查不冒充成员共同验收。

输入由三部分构成：

1. 用户明确选定、资格复核通过后生成的 `SelectedListingEvidence` `.selection.json`。
2. 单独提供的合同文件（示例使用 Agent 3 的合成 TXT）。
3. 合同处理同意、稳定的 request-id、固定的规则参考日期和本地收据存储位置。

不要传完整推荐报告充当选房包；不要把“同意选房”当作“同意读取合同”。Agent 3 对比原始租金的周期、计价对象和币种，不将含账单的 assessment.weekly_cost 当作合同租金。

`receive` 成功后返回 ContractReview，intake 绑定选房批次、复核批次、搜索/偏好版本、房源ID、选择时间及输入指纹。同内容同 request-id 重试返回原结果；同ID不同合同/选房包/参考日期拒绝。地址或可比租金冲突进入 Awaiting Human Review，人工决定前不生成问题。本地 receive/SQLite 回执不代表已实现跨机器消息投递或鉴权。

## 3. 可重复运行的合成演示

从仓库根目录建立虚拟环境并安装双方已声明的依赖：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r agent1/requirements.txt -r agent2/requirements.txt -r agent3/requirements.txt
python -m unittest discover -s integration/tests -v
```

Windows 激活命令为 `.venv\Scripts\activate`。需要 Python 3.11+（覆盖双方建议版本）；无需API密钥。

手动查看两个模块的文件交接（输出前缀须不存在）：

```sh
cd agent2
python -m rental_agent --profile ../integration/agent1-to-agent2/confirmed-profile.json --listings data/demo/listings.json --select-listing DEMO-006 --selected-at 2026-09-17T10:00:00+10:00 --output ../integration/reports/my-demo/selection
cd ../agent3
python -m contract_agent receive --agreement data/demo/agreements/selection-demo.txt --consent --selection ../integration/reports/my-demo/selection.selection.json --request-id demo-agent23-001 --as-of 2026-10-15 --store ../integration/reports/my-demo/receipts.sqlite3 --output ../integration/reports/my-demo/review
cd ..
```

本例明确指定的 DEMO-006 是预设的合成选择；真实界面必须由用户主动选择。房源观察/选择时点为2026-09-17，合同规则参考日期为2026-10-15，两者用途不同，不能宣称房源已联网刷新为当前可租。`.selection.json` 仍标为 prepared_not_sent；本地 CLI 接收验证单独保存在 ContractReview.intake 中。

预期：30输入→15合格/9待确认/5排除/1重复；Top1=DEMO-006、92.75分；合同无对应冲突时为 Reviewed。同一 receive 命令重试得到相同 review_id。Reviewed 表示原型复核流程状态，不是批准签约。

[2026-10-16 执行记录](reports/2026-10-16/README.md)保存原有测试日志、正常交接、重复请求及冲突场景证据。2026-10-20 又使用 PR #6 的 Agent 1 实现生成已确认偏好，跑通后续推荐、选房包和 Agent 3 接收，详见下节。组员共同验收、网络投递与 Chenyang 的共同确认仍待按实际执行记录。

## 4. PR #6：使用 Agent 1 实现的本地交接复跑（2026-10-20）

仓库根目录执行：

```sh
python3 -m unittest discover -s agent1/tests -v
python3 agent1/main.py --db /tmp/agent1-acceptance.sqlite3 --acceptance-demo
python3 integration/reports/2026-10-20/verify_agent123.py
```

Windows 可把 `python3` 替换为自己的 Python 解释器；数据库路径也应改为本机路径。验收演示会保存新的合成案例，并在 `agent1/reports/` 下生成输出。

独立复跑：Agent 1 单元/边界测试 52/52、脚本验收 14/14、Agent 2 回归 71/71、原有集成测试 6/6。新增独立交接脚本 9/9：Agent 1 未确认时拒绝搜索，确认后调用 Agent 2 并复用重复任务；核对导出正文；显式脚本选择 DEMO-006 后新生成证据包；Agent 3 接收为 `Reviewed`，绑定的搜索/偏好版本及批次一致；重复请求返回原复核，无合同处理同意时拒绝。

执行环境与原始日志见 [2026-10-20 结构化执行记录](reports/2026-10-20/review-summary.json)。Windows 14 项通过来自 Yirui 的反馈及 PR 描述，独立复跑环境为 macOS；两者分别记录。此次仅为合成数据下的本地自动检查，不替代真人选择/同意、真实 LLM 验证、组员共同验收或 Sprint Review。
