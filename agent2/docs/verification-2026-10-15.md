# SCRUM-7 本地验证记录

执行日期：2026-10-15（Australia/Sydney）；环境Python 3.13.9。本记录为 Codex 在当前项目目录实际执行的本地检查，不是团队 Sprint Review 或最终提交包验收。

## 改动

- 比较全部候选时输出 change_reasons 和四维 score_contributions，保留原评分、总分、排序和逻辑批次ID。
- 解释硬条件、资格、分项/有效权重、名次变化；未知贡献保持null，零权重贡献为0。加权贡献取自展示分项，明确舍入边界，不把非合格项已知贡献当作正式分数。
- 跨search_id比较拒绝；旧Schema 1.1比较仍可读取，未保存的原因不补造。
- Markdown增加变化原因列并转义源文本。更新比较示例前，将旧JSON/Markdown保存在 reports/archive/comparison-2026-09-17.*。

## 实际执行

1. 新增 tests/test_comparison.py 的12项测试；实现前运行时10项因缺功能失败，2项原有不变性/拒绝非法Schema行为通过。实现后12项全部通过。
2. `python3 -m unittest discover -s tests -v`：71 tests，OK。完整日志：`reports/verification-2026-10-15-tests.txt`。
3. `python3 -m compileall -q rental_agent tests`：exit 0。
4. 在临时新目录中执行以下比较CLI（成功后临时目录已清理），随后读取JSON执行RecommendationReport Schema校验，并确认30条比较行均有change_reasons、Markdown含“变化原因”列：

```sh
python3 -m rental_agent --profile data/demo/profiles/commute.json --compare-profile data/demo/profiles/budget.json --listings data/demo/listings.json --output <temporary-directory>/comparison
```

实测：input=30 / eligible=15 / pending=9 / excluded=5 / duplicates=1；通勤优先Top1=DEMO-006，预算优先Top1=DEMO-012。DEMO-002从9升到3，总分77.4→87.0；费用贡献28.8→57.6，四维贡献变化合计+9.6。JSON可执行示例为 reports/comparison.json，展示见 reports/comparison.md。

## Jira 交接

- 新建 SCRUM-19：Member 1：实现已确认偏好到 RentalProfile 的适配与最新推荐版本绑定。负责人Yirui Chen，待办，父项SCRUM-2，Sprint 0。
- SCRUM-4已有偏好验证定义；SCRUM-19补充实施职责和实际snake_case契约映射，避免将caseId/taskId/profileVersion直接作为不支持的字段传入。
- SCRUM-7记录本次实现/测试和待联调边界；不把本地测试宣称为Member1联调、模型调用或团队Review已完成。

仍待团队执行：确认与版本存储、实际接口调用、前端最新报告绑定；模型辅助和失败降级见SCRUM-11；最终压缩包重新解压验收见SCRUM-3；真实Review证据见SCRUM-12。

Jira链接：[Member 1实施待办 SCRUM-19](https://breezebee64.atlassian.net/browse/SCRUM-19)、[Agent 2实现及测试记录 SCRUM-7](https://breezebee64.atlassian.net/browse/SCRUM-7)。保存后已读取核对。截图：`reports/jira-evidence/SCRUM-19-2026-10-15.jpg`、`reports/jira-evidence/SCRUM-7-2026-10-15.jpg`。
