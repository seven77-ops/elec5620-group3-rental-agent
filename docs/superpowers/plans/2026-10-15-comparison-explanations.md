# SCRUM-7 Implementation Plan

**Goal:** 补齐逐房源变化原因，并给 Member 1 留下可验收的 Jira 联调任务。

**Architecture:** 沿用 evaluate → compare_reports → render_markdown；比较区块增加解释和可复算贡献，不修改评分公式。Schema 1.1 保持旧比较输入兼容。

**Tech Stack:** Python 3.10+、unittest、jsonschema、Jira 浏览器界面。

- [x] 在 tests/test_comparison.py 增加行为测试，运行 `python3 -m unittest discover -s tests -p test_comparison.py -v`，确认缺少解释导致失败。
- [x] 修改 rental_agent/report.py 和 schemas/recommendation-report.schema.json，实现 change_reasons / score_contributions、跨 search_id 拒绝和 Markdown 变化原因列，运行上述定向测试。
- [x] 归档 reports/comparison.json/.md，重建比较样例，更新 README 和 docs/data-contracts.md；实跑完整测试与比较 CLI，保存当日验证记录。
- [x] Jira 检查重复任务，创建 Member 1 确认/版本/联调待办，记录 SCRUM-7 实现及测试事实，保留团队验收未完成状态；读取保存结果并截图。

约束：不引入新依赖；不修改其他成员代码；不把本地 CLI 测试标成团队 Review；不提交用户已有未跟踪文件或原设计改动。

结果：71项测试通过；SCRUM-19已分配Yirui Chen、状态待办、父项SCRUM-2；SCRUM-7已保存当日代码与测试评论。截图保存在reports/jira-evidence/。
