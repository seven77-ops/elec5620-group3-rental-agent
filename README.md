# ELEC5620 Group 3 · Rental Agent

小组租房多 Agent 项目。各成员的实现放在独立目录中，再通过约定的数据契约联调。

| 模块 | 内容 | 运行说明 |
|---|---|---|
| [agent2/](agent2/) | Member 2：房源资格评估、评分推荐、偏好版本比较与本地选房证据包 | [Agent 2 README](agent2/README.md) |

## 运行 Agent 2

需要 Python 3.10+。从仓库根目录执行：

```sh
cd agent2
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --output reports/my-first-run
```

房源和路线全部为模拟数据。完整参数、比较功能和接口边界见 [Agent 2 说明](agent2/README.md)及[数据契约](agent2/docs/data-contracts.md)。

## 小组协作

在自己的模块目录中开发，通过分支与 Pull Request 集成；提交信息和 PR 标题注明 Jira 编号。

- [SCRUM-2：偏好确认与房源评估联调](https://breezebee64.atlassian.net/browse/SCRUM-2)
- [SCRUM-7：偏好比较与排名变化解释](https://breezebee64.atlassian.net/browse/SCRUM-7)
- [SCRUM-19：Member 1 接口适配与最新推荐版本绑定](https://breezebee64.atlassian.net/browse/SCRUM-19)
