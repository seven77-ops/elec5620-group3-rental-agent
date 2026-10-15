# SCRUM-22 场景验收结果

全部使用合成数据；快照时点固定为2026-09-17，不代表当前真实房源。

|场景|预期|实际|
|---|---|---|
|[01-baseline](01-baseline/result.json)|30输入→15合格/9待确认/5排除/1重复；Top5且保留15条完整排名与解释|PASS|
|[02-duplicate](02-duplicate/result.json)|同源同ID同事实合并；使用最新有效证据；审计保留两份原始引用|PASS|
|[03-conflict](03-conflict/result.json)|同源同ID租金冲突→两条pending，不排名；原始两份报价可追溯|PASS|
|[04-unknown-period](04-unknown-period/result.json)|周期未知→pending；周费用为空，不猜测week|PASS|
|[05-price-range](05-price-range/result.json)|原始480–540报价区间和周期/计价对象保留在审计；不取中点，缺精确报价保持pending|PASS|
|[06-missing-evidence](06-missing-evidence/result.json)|有值但无字段证据→pending，不排名|PASS|
|[07-missing-positive-weight](07-missing-positive-weight/result.json)|正权重设施输入缺失→pending，总分和排名为空|PASS|
|[08-gate-undecided](08-gate-undecided/result.json)|权限门禁未明确→pending，不排名|PASS|
|[09-hard-fail-precedence](09-hard-fail-precedence/result.json)|硬预算失败且软信息缺失→excluded；硬失败优先|PASS|
|[10-zero-eligible](10-zero-eligible/result.json)|全部硬失败→零合格是有效报告；无推荐，不自动放宽条件|PASS|
|[11-empty-input](11-empty-input/result.json)|空房源集→有效零推荐及澄清建议|PASS|
|[12-repeat](12-repeat/result.json)|固定输入、评估时间、rules-1.0重跑：完整报告及批次ID完全相同|PASS|
|[13-stable-ties](13-stable-ties/result.json)|8条同分候选按ID稳定排序；输入倒序不改排名；只展示5条且保留8条|PASS|
|[14-period-normalization](14-period-normalization/result.json)|同计价对象下周/双周/月报价均归一为520 AUD/week|PASS|
|[15-scope-mismatch](15-scope-mismatch/result.json)|整租与每人计价不匹配→pending，不按人数平分|PASS|
|[16-zero-weight-missing](16-zero-weight-missing/result.json)|仅零权重设施未知且其他条件完整→可合格|PASS|
|[17-stale](17-stale/result.json)|过期快照→pending，不把执行日期当来源刷新时间|PASS|
|[18-invalid-period](18-invalid-period/result.json)|非法周期字符串拒绝整批并指明字段；不默认为week|PASS|
|[19-real-data-rejected](19-real-data-rejected/result.json)|当前原型拒绝真实/混合房源模式|PASS|

通过：19/19。

未执行 Member 1 真实联调；上游适配代码尚未在共享仓库提供。

每个场景包含input.json和actual.json；有效输入另含actual.md和source-audit.json。价格区间为原始附加元数据，只保留，不进行区间评分。
