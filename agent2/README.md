# 悉尼租房评估 Agent：课程原型

已实现：30 条模拟房源、3 份学生偏好、确定性资格筛选与评分、Top 5 Markdown/JSON 报告，以及可选的偏好调整比较。

这是四 Agent 系统中 **Agent 2 的可独立运行工具核心**，不是已接入真实房源的自主 Agent。所有地址、租金、通勤和设施均为虚构，不可用于实际租房决策。运行时无 LLM、API Key 或网络请求；使用 jsonschema 验证本地交接契约。

## 快速运行

需要 Python 3.10 或更新版本。先进入仓库的 `agent2/` 目录，再运行：

```sh
python3 -m pip install -r requirements.txt
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --output reports/my-first-run
```

输出 `reports/my-first-run.md` 和 `reports/my-first-run.json`。为保护文件，已有同名输出时会报错，请换一个前缀，不会覆盖原文件。

可选功能：用相同房源快照，把通勤优先改为预算优先，比较排名变化：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --compare-profile data/demo/profiles/budget.json --listings data/demo/listings.json --output reports/my-comparison
```

第三份偏好是 `data/demo/profiles/housing.json`（居住条件优先）。三个 profile 的硬条件相同，只有版本和权重不同，便于观察权重影响。

测试及帮助：

```sh
python3 -m unittest discover -s tests -v
python3 -m rental_agent --help
```

## 已生成的示例

- [通勤优先推荐](reports/commute.md)
- [预算优先推荐](reports/budget.md)
- [居住条件优先推荐](reports/housing.md)
- [偏好调整前后对比](reports/comparison.md)
- [SCRUM-22 验收与复现（19个场景及71项测试）](docs/scrum22-acceptance.md)
- [课程功能与两个 Use Case](docs/course-requirements.md)
- [三个交接契约与 Schema 说明](docs/data-contracts.md)
- [明确选房后的证据包（仅本地，未发送）](reports/selection.selection.json)
- [设计、数据来源和 GitHub 参考](docs/superpowers/specs/2026-09-17-listing-evaluation-agent-plan.md)

当前样本分流：30 条输入 → 15 条完整合格、9 条待确认、5 条排除、1 条重复记录；从15条合格房源中取Top 5。数据本来就包含坏案例，不应让全部30条都进入排名。

## 代码结构

```text
rental_agent/
  validation.py  输入格式、类型、范围与模拟标记校验
  contracts.py   本地 JSON Schema 验证
  engine.py      三态资格检查、四维评分、去重与证据追踪
  report.py      Markdown 报告和偏好比较
  handoff.py     用户明确选定合格房源后构建证据包
  __main__.py    命令行入口、JSON读取与文件导出
schemas/         RentalProfile / RecommendationReport / SelectedListingEvidence
data/demo/
  listings.json  30条静态模拟记录和固定as_of
  profiles/      commute.json / budget.json / housing.json
tests/
  test_engine.py 规则与数据边界测试
  test_cli.py    报告、CLI和课程用例集成测试
  test_contracts.py 契约、批次ID和选房证据包测试
```

供未来 Agent 编排层调用：

```python
from rental_agent.engine import evaluate
from rental_agent.report import render_markdown, compare_reports

# profile 与 dataset 是已经读取的 JSON 对象。
report = evaluate(profile, dataset)
markdown = render_markdown(report)
updated_report = evaluate(updated_profile, dataset)
comparison = compare_reports(report, updated_report)
```

## 输入与输出约定

偏好输入字段以 `data/demo/profiles/commute.json` 为可执行示例：预算必须注明 AUD/week 和 per_person、per_room 或 whole_property；通勤必须注明校区目的地、到达时段及交通模式；设施硬条件与软偏好不重复。

房源输入是对象而非裸数组，包含 `schema_version: "1.0"`、`data_mode: "synthetic_demo"`、带时区的 `as_of`、最多30条 `listings`。房源内部ID唯一；来源ID用于识别同源重复。事实可以是 `null`，但不能用字符串 `"unknown"` 代替布尔值或数值。错误格式拒绝整批输入并指出字段位置。

- 各房源必须有 `data_kind: "synthetic"`；路线和字段证据也须显式标记 synthetic。当前拒绝真实或混合数据。
- `evidence` 按字段记录 `source_ref`、`observed_at`、`data_kind`；字段有值但无有效证据时按未知处理。
- 每个数值型业务字段接受非负有限数（租期至少1），最高 `1e12`，防止极端输入算术溢出；布尔值不是数字。权重总和须大于0，程序统一归一化。
- 租金周期接受 week/fortnight/month；月租按12/52换算用于预算比较，不用于合同应付款计算。计价对象不同不自动折算。
- `commute` 是预先提供的模拟路线摘要，不是在线查询结果。需与偏好的目的地、时段、时区、交通模式匹配，地点精度须为楼栋/入口。
- 起租必须有供方可接受的起止范围与客户窗口相交；仅有 available_from 不能认定任意未来日期仍可租。
- 房源、路线和已使用的字段证据按 `as_of` 检查24小时新鲜度；未来观测也不接受。日期只是课程快照，不代表现在仍有效。
- `--as-of` 可显式覆盖评估时点。默认使用数据中的固定时点，不使用机器时钟，因此同输入可复现。

JSON 报告包含 Top5 `recommendations`、全部合格项 `eligible`、`pending_confirmation`、`excluded`、`duplicates`、分项得分、三态硬检查、证据和澄清问题。`score=null` 表示没有正式总分，不是0分；区间只是缺失范围，不是概率。排名按未舍入总分降序、内部ID升序；展示分数可能舍入为相同值。

报告Schema现为1.1，新增 `recommendation_run_id` 和 `profile_fingerprint`；原偏好/房源输入仍为1.0。同一输入、评估时点和规则版本重试会得到相同逻辑批次ID，不是每次调用生成随机ID。独立Schema与业务验证共同生效；上游用户确认和版本存储尚未实现。

相同来源ID且事实相同才去重，并保留两条记录中更新且在有效时点内的字段证据；事实冲突时两条均进入待确认。同地址不同单间不自动合并。比较功能要求数据指纹、评估时点和评分版本相同，覆盖全量候选，不只比较Top5。

比较还要求相同 `search_id`。每套房源新增 `change_reasons`（资格、硬条件、分项和名次的变化原因）及 `score_contributions`（四维加权贡献前后值与差值）。贡献根据已展示的分项分数计算，存在舍入误差；未知维度保持 `null`，零权重维度贡献为0，不能将已知贡献相加冒充待确认房源的正式总分。自身展示总分未变但名次变化时，会提示结合其他候选的资格与得分变化理解。旧版比较示例保存在 `reports/archive/`；旧报告仍可读取，未记录的变化原因需重新生成。

## 原型边界与后续接入

课程编号已统一为 **UC03：房源分析与资格评估、UC04：推荐与比较**。修改/确认客户偏好仍是Member1的UC02；本模块只使用已确认的新版偏好重算。

显式选房后，可生成给Agent3的本地证据包：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --select-listing DEMO-006 --selected-at 2026-09-17T10:00:00+10:00 --output reports/my-selection
```

这会额外生成 `.selection.json`；只有原报告和选择时点均合格的房源才允许交接。缺少明确选择、不存在/重复/待确认/排除项、报告与数据不一致、证据过期均拒绝。证据包状态始终为 `prepared_not_sent`，程序不会联系或启动合同Agent。

目前不实现房源网页抓取、真实地图查询、NSW 市场基准计算、聊天界面或合同审查。价格合理性不由个人预算分冒充。报告理由由模板依据已计算事实生成，不使用模型改写分数。

下一步应把获授权的房源和路线适配器接到同一输入合同，并扩展真实数据许可、时效及证据核验；当前不能简单把 synthetic 改成 real 就宣称真实推荐上线。

本实现独立编写，没有复制方案中许可未确认的第三方代码。已有文档中的 GitHub 项目用于设计参考，不是运行依赖。

## 小组代码协作

本目录包含 Member 2（Agent 2 / UC03、UC04）的可运行代码。其他 Agent 的实现由对应成员后续通过分支与 Pull Request 集成。

```sh
git clone https://github.com/seven77-ops/elec5620-group3-rental-agent.git
cd elec5620-group3-rental-agent/agent2
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

提交信息和 PR 标题注明 Jira 编号，例如 `SCRUM-7: explain listing ranking changes`。Member 1 的接口适配与版本绑定待办为 [SCRUM-19](https://breezebee64.atlassian.net/browse/SCRUM-19)；本次本地验证见 [2026-10-15 验证记录](docs/verification-2026-10-15.md)。运行示例使用固定模拟时点，不代表当前真实房源。

课程 PDF、PPT、Word 文档、Jira 截图及临时构建目录未包含在此源码提交中。
