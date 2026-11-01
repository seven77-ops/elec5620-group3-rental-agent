# TfNSW Trip Planner MCP 接入可行性

核查时间：2026-10-27。结论：可以接入现有 Agent2 后端，建议采用本机独立 HTTP 服务和受控工具适配层。本轮仅在临时目录运行第三方项目，没有把 MCP 接到现有网站，也没有更改现有 Python 依赖、用户案例或房源数据。

## 核查对象及实测

- [MCP 仓库](https://github.com/maxim75/tfnsw_trip_planner_mcp)，提交 `f020393ce6759b125f6198226c496a28c7822935`，MIT。
- 仓库要求 Python >=3.12；按其锁文件在 `/tmp/tfnsw-mcp-audit-f020393` 创建独立 Python3.12.13 环境。我们的网站为 Python3.13.2，满足语言要求。
- 上游锁文件安装了 MCP2.1.1、Starlette1.6.0、Uvicorn0.52.4；现有网站锁定 Starlette0.46.2、Uvicorn0.34.2。用独立服务避免变更现有 FastAPI 栈。
- 上游离线测试：162 通过，20 个真实 API 测试被明确排除。本轮不是声称其全部真实 API 功能都已测试。
- 使用本地现有 TfNSW key，通过 `X-API-Key` 请求头，实际完成 Streamable HTTP 握手与10个工具的发现。
- 实际经 MCP 调用 `plan_trip`，使用公开房源 `25/124 Parramatta Road` 的已校验楼栋坐标，终点固定 Fisher Library 坐标，`origin_type=coord`、`destination_type=coord`、`arrive_by=true`、2026-10-28 09:00、`detail=summary`、最多3方案。没有发送租客或出租方私人送达地址。

| 出发 | 到达 | 总耗时 | 换乘 | 是否满足9点前到达 |
| --- | --- | ---: | ---: | --- |
| 08:49 | 09:01 | 12分钟 | 0 | 否 |
| 08:43 | 08:57 | 14分钟 | 0 | 是 |
| 08:42 | 08:56 | 14分钟 | 0 | 是 |

工具可正常返回路线，但请求 `arrive_by=true` 不能替代我们自己的到达时间校验，不能直接采用第一条方案。

## 可用能力和边界

项目的10个工具包括地点/车站搜索、路线、坐标起点路线、骑行、实时发车、运营提醒、附近车站、车辆位置。详见 [README](https://github.com/maxim75/tfnsw_trip_planner_mcp#tools) 和 [server.py](https://github.com/maxim75/tfnsw_trip_planner_mcp/blob/main/tfnsw_trip_planner_mcp/server.py)。

我们已直接使用同一 TfNSW 数据源。接入价值主要是标准化 AI 工具调用，并补充发车、运营提醒、完整行程等查询；房源库、偏好确认、预算房型筛选、通勤硬条件、开车/步行路网和前端展示仍由现有系统负责。

重要边界：

1. 认证是每次 HTTP 请求的 `X-API-Key`，不是从 MCP 进程 `.env` 自动取密钥。其 stdio 模式可以握手和列工具，但没有 HTTP 请求头，实际查询会报缺少密钥。见 [auth.py](https://github.com/maxim75/tfnsw_trip_planner_mcp/blob/main/tfnsw_trip_planner_mcp/auth.py) 和 [__main__.py](https://github.com/maxim75/tfnsw_trip_planner_mcp/blob/main/tfnsw_trip_planner_mcp/__main__.py)。
2. 当前 MCP 的路线签名没有直接暴露 `max_transfers` 或我们七种方式的完整过滤参数，需要后端按返回行程筛选；它没有通用开车工具。
3. [Journey.total_duration](https://github.com/maxim75/tfnsw_trip_planner/blob/main/tfnsw_trip_planner/models/journey.py) 为各段 duration 之和，MCP还将分钟四舍五入。适配层应重新按出发/到达时间算完整 elapsed，严格比较分钟上限，检查等待时间、日期、时区、到达时刻与换乘。本次三个实测方案中，各段求和与 elapsed 相同，尚未用本轮试验验证含换乘等待案例。
4. `plan_trip` 对名字匹配有质量下限，但不能代替本项目的完整街道/门牌/区域/邮编校验。我们的已知房源和 Fisher 应优先用已校验坐标，保留主校区范围。
5. `detail=answer/summary` 适合聊天；仅在请求路线绘图时用 `full` 并限制1–3条，防止结果过大。路线坐标和公交信息不等于地图底图，MapLibre需另接底图。
6. 车辆实时位置是单独的 GTFS-Realtime 产品，取决于现有密钥订阅；本轮未验证该权限。

## 建议接入方式

聊天 → Agent1收集/确认预算、房型、到校方式和时刻 → Agent2先筛真实房源 → 后端工具适配层调用本机 MCP → 本地严格校验结果 → 现有卡片、详情与路线展示。

- MCP绑定 `127.0.0.1`，固定提交和依赖；不把作者的远程服务当成密钥接收方。
- 网站后端添加 MCP HTTP 客户端，由后端从本地环境读取 key 并加请求头，密钥不进入提示词、网页或工具参数。
- 首轮开放路线、附近车站、运营提醒等只读工具；限制调用数、超时和返回量。
- 转成现有通勤 DTO，继续使用同一偏好确认、通勤校验、报告证据与候选保存规则。保留现有直连实现作为可回退路径。
- 后续已完成正式接入的后端客户端、工具路由与网页回归，见[接入验证](../frontend/2026-10-27-tfnsw-mcp.md)。上文实测描述保留为研究当时记录。

临时环境的服务在探测结束后自动退出，现有网站5191/API8011保持运行。MIT代码若复制或分发，应保留其许可证和版权声明。
