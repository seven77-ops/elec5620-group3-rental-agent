# Agent 1 输入约定与 Agent 2 → Agent 3 本地联调

本目录准备上游输入和跨模块可运行样例。**Agent 1 的真实对话、用户确认、版本存储和投递服务尚未实现/联调。** 所有 ID、偏好、房源及合同均为合成数据；模拟确认不能证明真人已批准。

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

拟接入的适配器应先确认保存版本存在、用户确实确认、必填信息有效且无未决硬冲突，再验证外层搜索/版本/指纹与正文一致，最后把**正文**交给 Agent 2。JSON Schema 校验只能证明形状，不能替代用户确认。`handoff.json` 是供双方确认的样例；本次没有新建生产适配器。

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
python -m pip install -r agent2/requirements.txt -r agent3/requirements.txt
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

[本次实际执行记录](reports/2026-10-16/README.md)保存测试日志、正常交接、重复请求及冲突场景的证据。真实 Agent 1 联调、网络投递与 Chenyang 的共同确认仍待执行。
