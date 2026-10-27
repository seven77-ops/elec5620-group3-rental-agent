# ELEC5620 Group 3 · Rental Agent

小组租房多 Agent 项目。各成员的实现放在独立目录中，再通过约定的数据契约联调。

接手本地开发请先阅读[最新跨窗口交接说明](docs/frontend/2026-10-27-agent2-chat-ui-handoff.md)，其中记录了MCP接入、当前界面要求、实际工作目录、启动方式与验证结果。

**2026-10-28 小组试用更新：** 使用 `codex/group-trial-20261022` / PR #7，暂不合并 main。本次包含 1,000 套房源、悉大通勤、可选 TfNSW MCP、完整结果及换批；安装、最新验证和范围见 [本轮发布说明](docs/frontend/2026-10-28-trial-update.md)。先在群里向 Anda 反馈，由 Anda 统一修改本轮集成代码。

| 模块 | 内容 | 运行说明 |
|---|---|---|
| [agent2/](agent2/) | Member 2：房源资格评估、评分推荐、偏好版本比较与本地选房证据包 | [Agent 2 README](agent2/README.md) |
| [agent3/](agent3/) | Member 3：NSW 官方模板租约草稿、合同读取、选房交叉核对与人工复核 | [Agent 3 README](agent3/README.md) |

## 悉大学生到校通勤

Agent2现已接入本地 TfNSW MCP：按用户到达时间查询公共交通，核对总时长和换乘，再生成推荐。聊天可查询已展示房源附近的车站和某一附近站点当前的运营提醒；网页按用户要求展示平均通勤参考和地图链接，不再展示行程分段。运营提醒不代表整条行程必然正常，开车、骑行仍使用原有路网服务。

首次运行 `.venv/bin/python scripts/setup_tfnsw_mcp.py`（需要 `uv`），再按下方启动网站。上游源码、MIT许可证和锁文件位于 `integrations/tfnsw_mcp/`，使用独立Python环境；后端仍使用本地 `.env` 的 `TFNSW_API_KEY`，无需另配密钥。`scripts/dev.py` 自动启动仅监听本机的6401端口。未安装、端口占用或查询失败时，路线查询保留原有TfNSW直连回退；附近车站/提醒失败会明确提示。设置 `RENTAL_TFNSW_MCP_ENABLED=0` 可关闭MCP。详见[接入验证](docs/frontend/2026-10-27-tfnsw-mcp.md)。

找房现在面向悉尼大学 Camperdown/Darlington 主校区学生，以 Fisher Library 官方设施点为统一到校参考。每套房源提供公共交通（含火车、地铁、公交方案）及开车、骑行、步行标注；超过用户分钟上限或数据未知的房源不会进入符合条件的推荐。

现有1000套房源均有图片和通勤标注；852套取得来源可核对的楼栋位置，849套有公共交通计划方案；原有148套缺楼栋定位的房源提供明确标记的街道或区域通勤区间。新增300套中，215套位于悉大周边，85套覆盖Burwood、Strathfield、Rhodes等通勤区域；每套新增房源配一张匹配照片。到达时间、出行日及换乘限制会随需求同步；与基准不一致时必须使用近期核对的路线。详见[数据来源、覆盖与更新方法](agent2/data/real/README-usyd.md)。

## 运行统一前端演示

使用 React/TypeScript/Ant Design 页面与 FastAPI 本地接口。偏好表单通过 Agent 1 保存和确认版本，Agent2 默认读取1000条真实住宅房源，提供房源字段筛选、分页、待核实候选报告和候选快照保存。缺失或损坏的数据文件会使启动失败，不会回退到模拟房源。AI 对话可整理需求、查询与比较候选；保存候选后可记录看房及中介回复，并在独立同意后上传真实合同，由 Agent3 提取和比对。Agent4 需另行确认租约资料。不会向房东或中介发送消息。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-lock.txt
(cd frontend && npm ci)
.venv/bin/python scripts/dev.py
```

打开 <http://127.0.0.1:5173>。需要 Python 3.11+，前端本次使用 Node 22.23.1 验证。启动脚本生成的本地操作员密钥位于忽略目录 `.runtime/operator-key.txt`。完整启动、演示时钟和权限边界见 [前端运行说明](docs/frontend/implementation.md)，实际结果见 [验证记录](docs/frontend/verification.md)。

## Agent2 网页与真实数据接口

访问网页“房源推荐”；租房需求面板收进“AI租房助手”。接口与状态约定见 [真实 Agent2 接入说明](docs/frontend/2026-10-21-agent2-real-catalog.md)。真实广告未核实在租、计价对象和租期，不提供模拟通勤、综合分数或已认证合同交接。

## 运行历史 Agent2 合成场景回归

需要 Python 3.10+。从仓库根目录执行：

```sh
cd agent2
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 -m rental_agent --profile data/demo/profiles/commute.json --listings data/demo/listings.json --output reports/my-first-run
```

以上 CLI 命令仅运行历史模拟场景；它不是网站运行时的数据源。完整参数、比较功能和接口边界见 [Agent 2 说明](agent2/README.md)及[数据契约](agent2/docs/data-contracts.md)。

## 小组协作

在自己的模块目录中开发，通过分支与 Pull Request 集成；提交信息和 PR 标题注明 Jira 编号。

- [SCRUM-2：偏好确认与房源评估联调](https://breezebee64.atlassian.net/browse/SCRUM-2)
- [SCRUM-7：偏好比较与排名变化解释](https://breezebee64.atlassian.net/browse/SCRUM-7)
- [SCRUM-19：Member 1 接口适配与最新推荐版本绑定](https://breezebee64.atlassian.net/browse/SCRUM-19)

## 跨 Agent 对接

[输入约定与本地联调](integration/README.md)：包含 Agent 1 已确认偏好及外层确认/版本/任务样例，以及 Agent 2 → Agent 3 的可复现场景。Agent 1 已通过 PR #6 合入 main；统一前端的实际服务接入及验证见 [最新验证记录](docs/frontend/verification.md#2026-10-20agent1-实际服务接入)。

## AI 接入与模块核对

Agent 2 推荐解读、Agent 3 候选提取/风险解释与前端接线见 [本地运行与 API 配置](docs/frontend/2026-10-20-ai-local-run.md)；同学核对见 [Agent 3 核对单](docs/frontend/agent3-ai-handoff.md)。默认不开启外部模型，真实服务成功仍需填写自己的后端配置后实测。

## 真实数据与市场参考（本地）

市场租金、真实观察记录和地图工具收进“房源推荐”页面：查询悉大周边政府历史租金基准、保存并导出真实房源观察记录，以及在配置凭据后查询 Domain 广告和 TfNSW 通勤。当前不将这些记录自动视为已通过资格评估的推荐。覆盖范围、来源、启动与配置见[真实数据运行说明](docs/frontend/2026-10-21-real-data.md)。

## 候选之后的跟进与真实合同

候选卡片提供“准备看房与询问”“生成租约草稿”和“已有合同，开始复核”。用户记录与广告原始快照分开保存，合同上传后冻结各自版本用于事实比对。未核实广告不转换为历史 `SelectedListingEvidence`；详细接口、范围和验证见 [候选跟进说明](docs/frontend/2026-10-22-candidate-followup.md)。

“合同助手”支持 NSW 普通整租住宅的未签署草稿：填写或用 AI 整理双方及租约要点，经用户确认后保存版本并下载官方模板 PDF。广告租金不会自动成为约定租金；未知内容保留待补，签字栏保持空白。模板来源、版本保存和测试记录见 [租约草稿说明](docs/frontend/2026-10-22-lease-draft.md)。

## 入住后的服务与退租

“租后服务”现支持日常报修邮件草稿、实际中介联系人、水电气网供应商保存、真实搬运及清洁公司入口、报价与服务记录、照片收据，以及原 Agent4 的退租计划和押金流程。AI 聊天可读取同一份资料并在用户确认后同步更新；不自动发送邮件或提交预约。目录来源、接口及测试见 [租后服务说明](docs/frontend/2026-10-22-living-services.md)。

租后服务还支持[租约资料接续、报修连续对话与待办直达](docs/frontend/2026-10-22-living-continuity.md)：核对来源后选择性带入资料，聊天与页面可跟进同一条报修，顶部待办直接定位到具体事项。
