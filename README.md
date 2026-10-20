# ELEC5620 Group 3 · Rental Agent

小组租房多 Agent 项目。各成员的实现放在独立目录中，再通过约定的数据契约联调。

| 模块 | 内容 | 运行说明 |
|---|---|---|
| [agent2/](agent2/) | Member 2：房源资格评估、评分推荐、偏好版本比较与本地选房证据包 | [Agent 2 README](agent2/README.md) |
| [agent3/](agent3/) | Member 3：合同读取、选房交叉核对、人工复核与问题清单 | [Agent 3 README](agent3/README.md) |

## 运行统一前端演示

使用 React/TypeScript/Ant Design 页面与 FastAPI 本地接口，直接调用 Agent 1、2、3、4 的本地服务。偏好表单复用 Agent 1 的草稿校验、确认版本、任务交接和版本比较；默认只用合成数据，当前不启用 LLM 对话提取或外发消息。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-lock.txt
(cd frontend && npm ci)
.venv/bin/python scripts/dev.py
```

打开 <http://127.0.0.1:5173>。需要 Python 3.11+，前端本次使用 Node 22.23.1 验证。启动脚本生成的本地操作员密钥位于忽略目录 `.runtime/operator-key.txt`。完整启动、演示时钟和权限边界见 [前端运行说明](docs/frontend/implementation.md)，实际结果见 [验证记录](docs/frontend/verification.md)。

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

## 跨 Agent 对接

[输入约定与本地联调](integration/README.md)：包含 Agent 1 已确认偏好及外层确认/版本/任务样例，以及 Agent 2 → Agent 3 的可复现场景。Agent 1 已通过 PR #6 合入 main；统一前端的实际服务接入及验证见 [最新验证记录](docs/frontend/verification.md#2026-10-20agent1-实际服务接入)。

## 本地 AI 接入核对版（尚未发布）

Agent 2 推荐解读、Agent 3 候选提取/风险解释与前端接线见 [本地运行与 API 配置](docs/frontend/2026-10-20-ai-local-run.md)；同学核对见 [Agent 3 核对单](docs/frontend/agent3-ai-handoff.md)。默认不开启外部模型，真实服务成功仍需填写自己的后端配置后实测。
