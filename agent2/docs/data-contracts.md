# Agent 2 数据交接契约

版本：1.0｜日期：2026-09-17｜状态：本地模拟契约已实现，团队消息/API联调待做。

本契约服务于[UC03／UC04](course-requirements.md)。不要求添加Location/Verification等顶层Agent，也不把结构校验等同于房源真实性、法律合规或用户鉴权。

## 1. 交接总览

| 契约 | 方向 | Schema版本 | 文件 | 实现入口 |
|---|---|---|---|---|
| RentalProfile | Agent1 → Agent2 | 1.0 | [rental-profile.schema.json](../schemas/rental-profile.schema.json) | `validate_profile`，由 `evaluate`调用 |
| RecommendationReport | Agent2 → Agent1／租客 | 1.1 | [recommendation-report.schema.json](../schemas/recommendation-report.schema.json) | `evaluate` |
| SelectedListingEvidence | Agent2 → Agent3 | 1.0 | [selected-listing-evidence.schema.json](../schemas/selected-listing-evidence.schema.json) | `build_selected_listing_evidence` |

三个文件均使用JSON Schema Draft2020-12，所有引用均为文件内的`$defs`，不依赖远程schema服务。开启format检查。实现使用`jsonschema==4.25.1`；金额关系、时间顺序、来源一致性、资格检查等跨字段业务规则仍由Python执行。

顶层契约拒绝未声明字段和未知版本，防止拼写错误被静默忽略。SelectedListingEvidence中的原始房源快照允许保留来源附加字段；构建前仍经过原型的房源校验。不能把外部网页中的指令当作执行命令。

## 2. RentalProfile：上游需求

直接沿用现有偏好JSON，不再包一层profile对象。可执行示例：[通勤优先](../data/demo/profiles/commute.json)、[预算优先](../data/demo/profiles/budget.json)、[居住优先](../data/demo/profiles/housing.json)。

| 字段 | 约束／含义 | 负责方 |
|---|---|---|
| schema_version | 固定1.0，指Profile格式，不是用户修改次数 | 团队接口维护者 |
| search_id | 非空租房任务标识 | Agent1／编排层 |
| profile_version | 正整数；同一任务修改需求应派生新版，不覆盖旧版本 | Agent1 |
| budget | AUD、week、每人/房间/整套；preferred≤maximum；是否含账单及硬上限 | Agent1与用户确认 |
| rental_mode / occupants | 租赁方式与人数；不据人数自动平分租金 | Agent1 |
| destination_id / arrival_time / timezone | 目的地、本地HH:MM、Australia/Sydney | Agent1确认，Agent2匹配路线 |
| commute | 交通模式、期望/最大分钟数、是否硬上限 | Agent1 |
| move_in_window / lease_months | 入住窗口起止有序，租期至少1个月 | Agent1 |
| hard_requirements | 必须满足的布尔设施字段 | Agent1 |
| soft_preferences | 软设施权重，不能与设施硬条件重复计分 | Agent1 |
| weights | commute/cost/housing/amenities非负权重；有效总和>0 | Agent1确认，Agent2归一化 |

**确认边界：** 当前对象没有独立用户签名或确认令牌。接口调用前“用户已确认”是Agent1必须保障的前置条件；结构合法不能证明真实确认。当前测试profile是模拟的已确认输入。缺硬指标的草稿留在Agent1，不交给本接口假装完整；本接口返回错误供上游补齐。

Agent2不会自动递增profile_version，也没有保存历史版本的数据库。相同版本内容被改写会产生不同profile_fingerprint，但历史版本冲突的治理仍由上游存储负责。

## 3. RecommendationReport：推荐与澄清

完整示例：[commute.json](../reports/commute.json)、[comparison.json](../reports/comparison.json)。

| 字段 | 含义 |
|---|---|
| schema_version / scoring_version | 报告格式1.1；现有规则仍为rules-1.0，评分没有改变 |
| recommendation_run_id | `rr-`＋64位SHA256十六进制；标识一次逻辑评估快照 |
| search_id / profile_version / profile | 输入任务和Profile版本、内容副本，便于Agent1核对 |
| profile_fingerprint / dataset_fingerprint | 原始Profile和整个数据快照的规范序列化内容哈希 |
| as_of / data_mode | 带时区的固定评估时点；当前只支持synthetic_demo |
| effective_weights | 实际归一化权重，不适用的住房维度可被统一移除 |
| report_status / counts | complete或partial，以及输入/合格/待确认/排除/重复数量 |
| recommendations / eligible | 最多5条推荐，以及全部合格排名；推荐数组为后者的前5条 |
| pending_confirmation / excluded / duplicates | 待补证据、已知不满足条件、同源重复记录分别保存 |
| clarification_requests | 交给Agent1确认的问题；不是自动修改偏好的指令 |
| data_limitations | 模拟数据、时点和使用边界等声明 |
| comparison（可选） | 原/新批次ID、权重、修改字段和全量候选状态/排名/分数差异 |

2026-10-15 增量：新生成的 `comparison.rows` 每行包含 `change_reasons`（非空字符串数组）和 `score_contributions`（commute/cost/housing/amenities 四维，每维包含 before/after/change）。Schema 1.1 允许这两个可选字段，以继续读取原始1.1比较；当前生成器始终输出。Markdown 新增“变化原因”列，旧记录缺此字段时明确提示重新生成，不推测历史原因。

贡献值使用报告已展示的四位小数分项乘 `effective_weights`，再保留四位小数；与未舍入排序分数可能略有差异，不保证逐项贡献恰好加总到展示总分。非零权重且分项未知时贡献为null；零权重时贡献为0；任一侧贡献未知则change为null。excluded/pending的已知贡献不是正式总分。

比较必须属于同一个 `search_id`，并使用相同数据指纹、评估时点、评分版本和数据模式。跨任务比较返回 ValidationError。名次由全量合格候选相对得分与ID决定，解释不会把自身某项贡献变化当作名次变化的唯一因果。

每个评估条目保存listing_id、status、rank、score、score_range、score_breakdown、hard_checks、evidence_coverage、可比周费用、通勤/步行/换乘、超市直线距离、reasons、tradeoffs、issues、evidence_refs和last_checked_at。

- eligible：允许正式分数和排名；score_range=null。
- pending：score/rank=null，给出分数区间和待确认原因；即使分数区间退化为同一数值，也不表示硬条件已确认。
- excluded：score/rank/score_range均为空，保留失败检查和已知分项。
- duplicates：只记录重复ID、保留ID及原因，不重复计入排名。

Schema验证上述形状及状态条件；数量加总、Top5与全量排名的关系、哈希及事实一致性是业务不变量。生成端由evaluate构建；选房交接时会依据原数据重新计算验证，不能只靠schema断言报告可信。

### 批次ID与可复现性

计算输入：profile_fingerprint、dataset_fingerprint、as_of字符串、scoring_version、报告schema_version；排序键固定、JSON使用一致序列化，不使用机器时间或随机数。

相同输入重试ID相同；Profile内容/版本、数据、评估时点或规则/报告版本变化则ID改变。ID是逻辑快照标识，**不是每次进程运行都不同的随机请求ID**；若团队需要每次调用审计，可在编排层另加request_id，不应破坏评分可复现性。

对象键顺序不影响指纹；数组顺序与时间字符串表示属于输入内容，可能影响ID，即使最终排序相同。哈希不是签名、不提供鉴权，也不能证明房源来源真实。

报告版本从1.0升级为1.1是因为新增必需追踪字段。旧1.0报告须从原始输入重新生成，不能凭空补一个ID；原Profile和房源快照仍保持各自的1.0版本。

## 4. SelectedListingEvidence：用户选定后的证据包

完整示例：[selection.selection.json](../reports/selection.selection.json)。不默认选择第一名；明确选择同批次任意合格候选即可，不限于Top5。

| 字段 | 含义 |
|---|---|
| schema_version / data_mode | 1.0 / synthetic_demo |
| recipient / handoff_status | ContractAgent / prepared_not_sent；仅声明目标，不代表已发送或已接收 |
| recommendation_run_id | 用户查看的原报告批次 |
| selection_check_run_id | 以selected_at复查资格生成的批次；时点不同可与原批次不同 |
| dataset_fingerprint / profile_fingerprint | 交接所依据的输入指纹 |
| search_id / profile_version / profile | 用户确认的需求上下文与副本 |
| listing_id / selected_at / user_confirmed | 明确选择的ID、带时区时间、true；时间不得早于原报告 |
| listing_snapshot | 被选择ID在原输入中的房源记录，含原始租金/周期/计价对象与地址等可用字段 |
| source_records | 同来源ID相关原始记录；若去重合并过证据，可追踪证据来自哪条记录 |
| assessment | 在选择时点仍为eligible的评估、周费用、分项、证据与检查结果 |
| unresolved_items | 仍需处理的非阻断未知项，以及合同尚未提供/审查的提醒 |
| data_limitations | 模拟、未发送、不能证明真实性及不能替代签约审查等边界 |

构建顺序：确认标记→报告schema→重新计算原报告并比对→检查明确选择属于原合格候选→按选择时点复查时效及资格→复制快照与证据→校验SelectedListingEvidence。

拒绝情形：用户未确认、不存在/重复/待确认/排除候选、数据或核心评估报告被改写、选择时点倒退、选择时已过期。原报告整体partial并不阻止选择其中信息完整的eligible房源；不能把其他候选的缺失强加到已选房源。

比较区块的边界：交接会检查comparison的目标批次、目标Profile版本及目标权重与当前报告一致，但不会重算其“调整前”的历史报告或验证所有差异数值，因为当前接口没有接收原Profile。comparison不作为SelectedListingEvidence的证据，也不会传给Agent3；所选房源的核心评估始终独立复算。若需要验证完整比较历史，调用方须保留两份原始Profile并重新执行compare_reports。

这个复查只使用同一份提供的数据，**不会联网刷新库存**。数据过期应由数据提供方更新快照，再重跑推荐，不能把selected_at当作新的来源观测时间。

## 5. 本地调用与演示

先安装依赖：

```sh
python3 -m pip install -r requirements.txt
```

接口调用：

```python
from rental_agent.__main__ import load_json
from rental_agent.contracts import validate_contract
from rental_agent.engine import evaluate
from rental_agent.handoff import build_selected_listing_evidence

profile = load_json('data/demo/profiles/commute.json')
dataset = load_json('data/demo/listings.json')
validate_contract('RentalProfile', profile)  # 结构；evaluate还会检查跨字段规则
report = evaluate(profile, dataset)
packet = build_selected_listing_evidence(
    report, dataset, 'DEMO-006',
    selected_at='2026-09-17T10:00:00+10:00', user_confirmed=True,
)
validate_contract('SelectedListingEvidence', packet)
```

CLI只在显式传入成对参数时生成额外证据包：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --select-listing DEMO-006 --selected-at 2026-09-17T10:00:00+10:00 --output reports/my-selection
```

输出`.json`、`.md`、`.selection.json`；默认不覆盖已有文件。没有发送网络请求、签约、支付或工单创建。重复执行请换输出前缀，逻辑批次ID仍保持一致。

## 6. 错误与责任交接

| 情况 | 当前行为 | 团队后续职责 |
|---|---|---|
| 契约结构不合法／未知版本 | ValidationError；CLI非零退出并提示字段，不输出成功报告 | Agent1补充偏好或适配调用；约定升级流程 |
| 房源事实不足／冲突／过期 | pending＋issues＋clarification_requests | Agent1询问用户，供数方补证据，必要时人工核对 |
| 无合格候选 | 空推荐＋原因，不擅自放宽约束 | 用户确认修改后由Agent1提供新版Profile |
| 选房被拒绝 | 不生成交接包，不自动改选其他房源 | 重新选房或刷新证据后重新推荐 |
| 证据包已生成 | prepared_not_sent | 编排层负责鉴权、消息投递、幂等接收和Agent3确认 |
| 合同／高风险人工处理 | 证据包列明尚未审查，不作合规保证 | Agent3与人工审核角色执行其职责 |

尚未实现：Agent1真实确认与不可变版本存储、跨Agent网络/API、收件确认、权限控制、人工工单、数据库状态机。这些不能在课程图中被标成已经运行的功能。本次先固定三种数据接口及本地验证行为，为下一步团队联调和行为建模提供基准。
