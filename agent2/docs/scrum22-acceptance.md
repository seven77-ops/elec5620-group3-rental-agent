# SCRUM-22：UC03–UC04 验收记录

执行日期：2026-10-15（Australia/Sydney），Python 3.13.9。范围为 FR03、FR04 的 Agent 2 确定性工具核心。全部输入是合成数据，固定评估快照为 `2026-09-17T09:00:00+10:00`；执行日期不会被当作房源观察时间。

本次新增可重复执行的验收脚本和证据导出，未改变评分规则。实际执行结果：**19/19 个验收场景 PASS；71/71 项原有测试通过；编译检查和 CLI 运行成功**。

## 逐项验收

|Jira 验收条件|预期与实测|证据|
|---|---|---|
|1. 来源、观察时间、价格范围、数据模式；重复合并、冲突可追踪，未知周期不猜测|同源同ID相同事实只评估一条，取最新有效字段证据；原始两条引用均留存于来源审计。报价冲突两条均 pending；未知周期不生成周费用。480–540 的原始区间、period、scope、currency 与证据保存在输入及来源审计，不取中点。|场景02–05、14、15、18、19|
|2. 硬约束优先；门禁未决或正权重缺失不排名|缺少证据、权限门禁未决、正权重设施缺失均 pending 且 score/rank=null；已知硬预算失败即 excluded，即使还有未知软信息。|场景06–09、16、17|
|3. 确定性评分，Top5及完整排名，解释依据、取舍和排除/澄清理由|30条输入→15合格、9待确认、5排除、1重复；展示5条且保留15条完整排名。Top1=DEMO-006。报告保留 evidence_refs、reasons、tradeoffs、hard_checks、issues 与澄清建议。|场景01、13；cli-demo.json / .md|
|4. 固定输入、评估时间、规则版本可复现，零合格有效|完整报告和 recommendation_run_id 重跑一致；8条同分按ID稳定排序，输入倒序不改排名。全部硬失败及空数据均返回有效零推荐，不自动放宽条件。|场景10–13|
|5. 合成样例与预期/实际结果及证据链接|19个场景分别保存明确预期、实际输入与输出；原有71项测试、编译和CLI的退出码与日志均保存。|[场景结果](../reports/scrum22-2026-10-15/README.md)、[执行记录](../reports/scrum22-2026-10-15/execution.json)、[71项测试日志](../reports/scrum22-2026-10-15/check-1.txt)|

全部场景和逐条结果见 [summary.json](../reports/scrum22-2026-10-15/summary.json)。有效输入场景的 `source-audit.json` 保存完整原始记录（包括重复引用和原始价格区间）、数据指纹、评估时点和报告批次ID；`actual.json` 保存完整引擎结果，`actual.md` 可直接阅读。非法输入场景保存实际 ValidationError。

来源审计由验收脚本导出。常规 `evaluate()` 返回的报告只包含所用的 evidence_refs，不内嵌完整原始房源；调用方应将输入快照与报告一并保存，并用 dataset_fingerprint 关联。`rent_range` 是保留的原始附加元数据，当前引擎不校验或评分区间；精确 rent_amount 缺失时按未知处理。不能把审计导出宣称为区间估价功能。

## 复现

先进入 GitHub 仓库的 `agent2/` 目录，安装 `requirements.txt`，然后执行：

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q rental_agent tests tools
python3 tools/verify_scrum22.py --output reports/my-scrum22
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --output reports/my-scrum22-cli
```

验收输出目录必须不存在，防止覆盖既有证据。脚本成功退出码为0；任一断言失败则返回非0。每次生成的输入、输出及 summary 均可查看；无需网络、模型或API密钥。

## 与 Member 1 联调的状态

2026-10-15 检查共享 GitHub 仓库 main（上游提交 `ef382f6`）：已存在 Agent 2 和新上传的 Agent 3 文件，尚未看到 Member 1 的适配实现；用户也确认目前尚未与 Agent 1 联调。此前读取 Jira 时，SCRUM-4 为“正在进行”，SCRUM-19 为“待办”。因此本记录证明 Agent 2 的本地验收，**尚未执行 SCRUM-4 / SCRUM-19 的真实成员间联调**。SCRUM-22 保持“正在进行”，待联调证据补齐后再关闭。

Member 1 接入时使用 `data/demo/profiles/commute.json` 与本次场景输入，调用 `evaluate(profile, dataset)`，校验 RecommendationReport，并核对 search_id、profile_version、recommendation_run_id、dataset_fingerprint。至少覆盖：已确认偏好正常交接、未知信息 pending、硬失败/零匹配、重复请求一致和新旧版本结果绑定；用户确认及版本存储应来自真实的上游实现。实际运行后补调用日志、输入/输出和预期/实际对照。

本次未把偏好版本差异任务 SCRUM-7、真实模型调用/降级、实时房源接入、团队Review或最终提交包验收标记为完成。
