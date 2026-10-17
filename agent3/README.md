# Agent 3 · 合同辅助 Agent（UC05 / UC06）

这是四 Agent 租房系统中 Member 3 的独立可运行模块。目录、命令行、Schema、演示数据、报告和测试的组织方式参考 `agent2/`。它消费 Agent 2 的 `SelectedListingEvidence` 本地 JSON，审查租客明确同意处理的合同，生成带原文位置的字段与发现；高风险先等待人工决定，达到 `Reviewed` 后才允许生成问题。**这是课程原型，不提供法律意见，也不会发送问题给房东或中介。**

## 快速运行

从 `agent3/` 目录执行；建议 Python 3.11+：

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 -m contract_agent review \
  --agreement data/demo/agreements/selection-demo.txt --consent \
  --selection data/demo/selected-listing-evidence.json \
  --as-of 2026-10-15 --output reports/my-selection-review
```

会生成 `reports/my-selection-review.json` 和 `.md`，不会覆盖同名文件。没有选房包时省略 `--selection`；M3 仍可独立审查合同。`data/demo/selected-listing-evidence.json` 是 Agent 2 合成输出的本地测试副本。团队联调时把 `--selection` 换成 Agent 2 现场生成的 `.selection.json` 路径。

## SCRUM-25：Agent 2 → Agent 3 接收

`receive` 是带请求 ID 的本地接收入口，要求选房包、合同和合同处理同意；每次重试使用**相同** `--request-id`、`--as-of` 与输入。SQLite 收据保存首次复核结果，同内容重试返回同一 `review_id`；同一请求 ID 绑定不同输入会返回 `duplicate_request_conflict`。这处理本地重复请求，不代表网络已投递或用户身份已验证。

```sh
python3 -m contract_agent receive \
  --agreement data/demo/agreements/selection-demo.txt --consent \
  --selection data/demo/selected-listing-evidence.json \
  --request-id SCRUM-25-demo-001 --as-of 2026-10-15 \
  --store reports/intake-requests.sqlite3 --output reports/my-intake
```

输出 `ContractReview.intake` 绑定 `recommendation_run_id`、`selection_check_run_id`、`search_id`、`profile_version`、`listing_id`、`selected_at`、选房包指纹、合同 SHA-256 和首次复核版本。命令失败时以非零退出并向 stderr 写 JSON：`{"error":{"code":"...","message":"...","request_id":"..."}}`。房源地址或可比租金与合同冲突时停在 `Awaiting Human Review`，问题生成须等待人工决定。

演示高风险与 UC06：

```sh
python3 -m contract_agent review --agreement data/demo/agreements/risk-demo.txt \
  --consent --selection data/demo/selected-listing-evidence.json \
  --as-of 2026-10-15 --output reports/my-risk
python3 -m contract_agent decide --review reports/my-risk.json \
  --decision approve --reviewer 'Demo Operator' \
  --note 'Synthetic escalation path reviewed' --output reports/my-approved
python3 -m contract_agent questions --review reports/my-approved.json \
  --output reports/my-questions
```

最后生成完整复核 `.json/.md`，以及独立的 `.questions.json`。该问题包标为 `prepared_not_sent`；没有联网发送。`decide --decision return` 会进入 `Awaiting Resubmission`。人工操作员身份当前仅由 CLI 字符串表示，尚无生产鉴权。

租客修正字段时，把 `{"bond":2000,"address":"..."}` 存成 JSON，运行：

```sh
python3 -m contract_agent correct --review reports/my-risk.json \
  --corrections data/demo/corrections.json --output reports/my-corrected
```

修正产生新的 `version`，保存先前字段/发现快照，清空旧问题，重新计算规则和人工复核需求。编辑问题可给 `questions` 命令加 `--edits`，其 JSON 为完整的 `[{"finding_id":"F01","text":"..."}]` 列表，必须保留每个发现引用。

## 代码与数据布局

```text
contract_agent/
  document.py       同意、格式/大小验证、TXT/DOCX/PDF 文本与可选本地 OCR
  extract.py        带页/行/引文的保守字段提取及启发式置信度
  handoff.py        校验 Agent 2 的 SelectedListingEvidence Schema/关键一致性
  intake.py         请求 ID、版本/文件绑定与 SQLite 重复请求收据
  rules.py          版本化 NSW 参考检查及选房交叉核对
  model_gateway.py  可选模型说明、结构核验、一次重试与规则回退
  review.py         UC05/UC06 状态、人工决定、修正版本和问题生成
  contracts.py      本地 JSON Schema 验证
  report.py         JSON 对应的 Markdown 呈现
  __main__.py       CLI 入口
schemas/            Agent 2 选房契约快照、ContractReview / ContractQuestionList
data/demo/          合成合同、Agent 2 选房包副本与修正示例
reports/            合成输入生成的 JSON/Markdown 报告
docs/               课程追踪、交接契约与验证记录
tests/              本模块及 Agent 2 样例的联调测试
```

## 接口与判断边界

- 上游真实格式是 Agent 2 的 `selected-listing-evidence.schema.json`；本目录的 `schemas/` 有截至 2026-10-15 的字节一致副本，便于只交付 `agent3/` 时独立运行。必须由用户显式选房，Agent 2 的包状态为 `prepared_not_sent`，**文件生成不等于消息已送达 M3**。M3 只读此包，不改排名。Agent 2 升级 Schema 时须同步本副本并重跑联调。
- 合同租金只与 `listing_snapshot.rent_amount` 比较，并要求周期、计价对象、币种一致。`assessment.weekly_cost` 是推荐用的可比周费用，不是合同租金；不进行直接比较。
- 合同提取支持 TXT、DOCX、文字版 PDF，文件最多 2 MB、PDF 最多 10 页。扫描版 PDF 可在系统安装 `pdftoppm` 与 `tesseract` 时调用本地 OCR；否则要求较清晰版本。OCR 字段置信度是较低的启发式标记，**不是经标注样本校准的概率**。
- 当前 NSW 规则包只实现“押金超过四周合同周租”参考检查；不把整个合同宣称为合法或非法。规则包记录来源和核对日期，超过 30 天后进入 `Degraded Summary Only` 并暂停规则结论。
- 房源与合同地址不同，即使房源精度只有楼栋，也转人工复核以确认是否仅为精度差异；同周期、计价对象、币种的租金数值冲突亦转人工。字段或来源不明时保持待核对。
- 可选模型只解释已有规则发现，不控制字段、风险、状态或问题引用。当前接入点是显式配置的 **OpenAI-compatible chat completions** HTTPS endpoint；**不能假设学校 Campus Qwen Proxy 与其兼容**。需要按单独的 Proxy Connection Guide 做适配和实测。无配置或模型输出结构不合格时使用规则文本。代码校验字段引用和结构，不能自动证明每句自然语言都正确。
- 本地 CLI 有 SQLite 重复请求收据，但尚未提供跨 Agent HTTP API、业务数据库、人工操作员鉴权或 M4 自动投递。这些属于后续编排层工作。

可选模型配置仅放在服务器/终端环境：`AGENT3_MODEL_URL`（完整 HTTPS chat completions URL）、`AGENT3_MODEL_NAME`、`AGENT3_MODEL_API_KEY`。只有租客另行同意外部模型处理时才加 `--allow-external-ai`；不要用真实合同做课程演示。

详见 [课程需求追踪](docs/course-requirements.md)、[数据交接契约](docs/data-contracts.md)、[M3 → M4 交接包](docs/m3-m4-handoff.zh-CN.md)和[2026-10-15 验证记录](docs/verification-2026-10-15.md)。

## 小组联调入口

代码及文档现统一放在 `agent3/`（目录名末尾无空格）。从仓库根目录运行 `python -m unittest discover -s integration/tests -v` 可验证现场生成的 Agent 2 选房包、重复请求及合同冲突；先安装双方 requirements.txt。样例和逐项说明见 [跨 Agent 联调](../integration/README.md)。本地运行记录不代表 Agent 1 已实现或成员共同验收已完成。
