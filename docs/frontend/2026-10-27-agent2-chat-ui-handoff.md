# 房产 Agent 跨窗口交接说明

更新日期：2026年10月27日，悉尼时间。

本窗口近期主要完成了 **Agent2 的 TfNSW MCP 正式接入、聊天交通查询、通勤参考展示，以及用户逐项确认的前端精简**。目前这些修改已在本地网站生效。接手时请以本说明中的最终界面要求为准，旧文档和旧截图中的说明栏、完整偏好页、行程分段等内容，有一部分已经被用户明确取消。

## 1. 工作目录和运行状态

实际开发目录是：

```text
/Users/seven/Documents/AI_coding/5620房产Agent/.workspaces/frontend-demo
```

不要只在外层 `/Users/seven/Documents/AI_coding/5620房产Agent` 查找或修改代码。当前 Git 分支为 `codex/local-ai-integration`。

| 服务 | 本地地址 | 交接时核对结果 |
| --- | --- | --- |
| 网页 | http://127.0.0.1:5191 | 正在运行 |
| FastAPI | http://127.0.0.1:8011 | `/api/v1/health` 返回 `ok`、`real_listings` |
| TfNSW MCP | http://127.0.0.1:6401/mcp | `/health` 正常，网站配置显示 `tfnsw_mcp` 已启用 |

工作区存在大量历史修改和未跟踪文件，包含其他窗口的工作。本窗口没有执行提交、推送、合并或重置。**不要用整文件回滚、`git reset --hard` 或清理未跟踪文件来处理这些改动。** 接手后先查看差异，只改自己负责的部分。

## 2. 当前业务背景

当前找房定位已经收窄到悉尼大学 **Camperdown / Darlington 主校区学生**，统一以 Fisher Library 为到校参考，避免再次匹配到 Camden 等远校区。

交接时重新读取房源目录得到：

- 700套房源，覆盖72个区域。
- 552套具有来源可核对的楼栋位置。
- 550套具有公共交通分钟数。
- 其余缺楼栋定位的房源继续使用明确的街道、区域或邮区估算，不能当成已核对的精确路线。

主要数据文件位于 `agent2/data/real/`：`listings.json`、`locations.json`、`usyd-commutes.json`、`photos.json`。这些是有来源的房源快照，不保证今天仍可租；用户要求隐藏部分状态说明，并没有把后端数据改成“已核实”。

已有链路是：Agent1整理并确认需求 → Agent2筛选、比较、保存真实候选 → 看房及中介询问 → Agent3租约草稿或已有合同复核 → Agent4租后服务。合同和租后已有代码应保留，本轮没有重写这两个Agent的业务。

## 3. 本窗口完成的 TfNSW MCP 接入

### 接入架构

采用 `maxim75/tfnsw_trip_planner_mcp`，固定提交：

```text
f020393ce6759b125f6198226c496a28c7822935
```

原始源码、MIT许可证和依赖锁保存在 `integrations/tfnsw_mcp/`。MCP使用独立Python环境 `.runtime/tfnsw-mcp/.venv`，没有把它的MCP/Starlette依赖升级混入网站环境。

网站后端使用已有httpx实现了有大小、超时和工具名限制的本机HTTP客户端。只开放三个只读工具：

| 工具 | 已接入的用途 |
| --- | --- |
| `plan_trip` | 按房源坐标、主校区坐标及到达时间查询公共交通 |
| `find_nearby` | 查询已展示房源附近的车站 |
| `get_alerts` | 查询某一附近站点当前公开运营提醒 |

后端从本地配置读取 `TFNSW_API_KEY`，只通过每次请求的 `X-API-Key` 头传给本机MCP；不把密钥放进模型提示词、网页、工具参数或交接文档。MCP地址限定为本机回环地址，客户端禁止跳转和代理继承。

### 修正和保留的规则

- 用完整出发/到达时间差计算总时长，包含等待时间，不能只把各段移动时间相加。
- 后端继续检查用户指定的日期、到达截止、所选交通方式、最大通勤时间和换乘限制。
- MCP超时、协议错误或无法可靠解析交通方式时，路线查询回退到原有真实TfNSW直连接口；两段查询共享原有约12秒单次预算。
- 上游部分Metro分类不完整，不能把未知方式强行标成火车或公交。
- 附近查询使用 `type_1=STOP` 和原始字段 `STOP_NAME_WITH_PLACE`、数字 `stopId`。上游精简摘要可能返回 `undefined, undefined` 和G前缀ID，不应直接拿来展示或查询提醒。
- 附近车站最多展示10个，距离为直线参考。提醒仅针对查询到的一个附近站点，不能宣称整条未来行程都正常。
- 只引用当前对话已展示或已保存候选的房源，不把租客、房东的合同送达地址用作交通查询地址。

### 关键文件

| 位置 | 用途 |
| --- | --- |
| `server/app/commute/mcp_client.py` | 有界HTTP MCP协议客户端 |
| `server/app/commute/mcp_journeys.py` | 路线DTO转换、时间及方式校验 |
| `server/app/commute/mcp_transit.py` | MCP优先、真实直连接口回退 |
| `server/app/commute/planner.py` | 预算、房型、到达时间与通勤条件筛选 |
| `server/app/commute/usyd.py` | 固定主校区目的地 |
| `server/app/assistant/transit_info.py` | 聊天附近车站与运营提醒回答 |
| `server/app/assistant/intents.py`、`service.py` | 交通意图校验与路由 |
| `server/app/ai/provider.py` | 模型意图提示及结构化输出约定 |
| `scripts/setup_tfnsw_mcp.py` | 安装独立MCP环境 |
| `scripts/transit_sidecar.py`、`scripts/dev.py` | 本机MCP及网站进程管理 |

## 4. 通勤展示的最终约定

用户已经明确要求：**房源卡片只显示“平均通勤约X分钟”，具体查询交给Google地图链接。**

实现集中在 `frontend/src/features/real-data/commuteSummary.ts`：

1. 收集有有效时长的交通方式，缺失、负值、非有限数字和不可用路线不计入。
2. 路线分钟数向上取整作为详情显示值；区间估算取中点作为参考值。
3. 对实际显示的各项分钟数求算术平均，再四舍五入成整数。
4. **步行超过30分钟就隐藏，也从平均值中排除；30分钟及以内保留。** 对区间估算，步行区间上限超过30分钟也不显示。
5. 公共交通与公交、火车等分别作为显示项目参与平均，没有做去重；这是按用户要求对可见项目直接取平均的口径。

例：公共交通13、公交12、开车4、骑行7、步行15分钟，外部显示平均约10分钟。

**这个平均值只是前端参考，不是后端判断20分钟或30分钟硬条件的依据。** 后端仍使用用户选定方式的真实时长；街道估算中点不能代替上限通过筛选。不要为了匹配显示平均值而改坏筛选规则。

相关界面在 `UsydCommute.tsx`、`assistant/CommuteResults.tsx` 和 `RealRecommendations.tsx`。没有数据的火车、地铁等项目自动隐藏。已删除行程分段、出发/到达时刻、步行接驳和换乘文字。Google地图采用现有跳转链接，没有新增付费Google API。

## 5. 用户已确认的最终界面

以下内容不要按旧截图或旧文档恢复。

### AI租房助手

- 顶部只保留标题和“我的租房需求”等必要按钮；标题及需求按钮文字是黑色。
- 删除“面向悉大学生，按预算、房型和到校通勤找房”介绍。
- 删除“不限区域／预算／尚未同步需求”等整条顶部需求摘要栏。
- 删除左下角“你的需求，你来决定”“修改偏好前会请你确认”。
- 删除“资料与设置／演示与证据”入口及其技术信息弹窗。
- 聊天里的需求确认、候选保存与版本校验继续保留，删除文案没有取消业务确认逻辑。

### 我的租房需求面板

- 需求统一在聊天页的抽屉管理。
- 删除AI整理条件说明、数量0的说明、生活偏好下方的解释文字。
- 不显示“上课前到达时间”和“出行日”；“最多换乘（可选）”在此面板仍保留。
- 删除底部“查看房源推荐”“其他偏好与完整设置”两个链接。
- 真实房源模式下，旧 `/cases/:id/preferences` 地址转到 `/cases/:id/assistant?needs=1`。App内旧 `go("preferences")` 入口也统一转换。
- `Preferences.tsx`仍保留历史模式兼容代码，但真实房源模式不会再进入独立完整填写页。不要重新把它接回真实用户流程。
- 抽屉宽度限制为 `min(500px, 100vw)`，已修正手机端左侧内容被截断的问题。

### 房源推荐页

- 页面主体保留原来的筛选条件和筛选结果表格。
- 删除顶部重复展示的聊天通勤推荐与区域介绍，以及读取这两份聊天报告的请求。AI推荐仍在聊天中。
- 筛选表单不显示“到校时间”“最多换乘”。确认需求、生成候选报告、候选保存及详情入口仍可使用。
- 区域推荐在聊天里改成区域名称按钮，点击只过滤当前结果，再点同一按钮恢复全部，不额外调用模型。
- 删除区域卡片中的“依据与取舍”、候选/路线数量、资料未整理说明、来源范围展开块。

### 房源详情

- 保留地址、租金、照片、卧室/浴室/车位、通勤参考及地图链接。
- 原始Domain房源链接保留在详情内，不放回外部房源卡片。
- 删除房屋资料、房屋类型、房屋配置和“待确认事项”整块内容。
- 删除“在租状态待确认”标记，以及底部“房源资料采集于……实际情况……”整句。
- 外部聊天推荐底部的“路线：TfNSW……”整行已删除；详情里的简洁地图来源署名仍保留。

### 字段隐藏不等于删除已确认信息

`RentalNeeds.tsx`中的 `arrival_time`、`travel_day`，以及筛选表单中的 `usyd_arrival_time`、`usyd_max_transfers` 使用隐藏表单项保留已有值，避免用户修改预算时意外清空先前通过聊天提供的条件。它们不作为可见填写项。新需求也不应凭空填入示例时间、日期、人数或预算。

主要前端文件是 `frontend/src/app/App.tsx`、`frontend/src/styles/app.css`、`frontend/src/features/assistant/Assistant.tsx`、`RentalNeeds.tsx`、`CommuteResults.tsx`、`TransitInfo.tsx`，以及 `frontend/src/features/real-data/` 下的通勤和详情组件。

## 6. 与其他窗口工作的衔接

`ListingDetails.tsx`目前还包含房源照片更新逻辑：打开详情时读取当前房源，校验ID和来源后补充照片，并通过 `refreshedCommute()`保留历史卡片里的个性化通勤。照片字段和更新逻辑包含其他窗口的工作，本窗口在删减详情内容时保留了它们。

因此，不要拿较早的整个 `ListingDetails.tsx`、`api/catalog.ts`或照片数据文件覆盖当前文件。合同、租后和媒体数据的修改也不应因为本窗口交接而回滚。

## 7. 已做的验证

以下是分阶段实际执行的结果，存在重复覆盖，**不要将测试数相加当作一次全量结果**。

| 阶段 | 已验证内容 |
| --- | --- |
| MCP接入 | 当时后端全套389项通过；最终MCP、车站、聊天17项集中测试通过 |
| 真实外部链路 | 真实AI连续三轮完成按条件推荐、查询所选房源附近车站、查询站点提醒；未修改案例保存状态 |
| 时间校验 | 08:43到08:57的14分钟方案通过09:00截止；08:49到09:01的12分钟方案被排除 |
| 故障回退 | 实际连接不可用MCP端口，成功切回真实TfNSW直连接口，取得3条路线 |
| 平均通勤显示 | 28项前端单元测试通过；有缺失方式、30分钟步行边界和区间参考测试 |
| 最近界面与路由 | `workspace-sync.spec.ts`、`assistant.spec.ts`、`agent2-real.spec.ts`共18项浏览器检查通过 |
| 最后一次手机修正 | 旧偏好地址跳转、删减文案、390px抽屉宽度、填写并确认保存的检查再次通过 |
| 构建 | 最后一次 `npm run build`成功；仅有既存vendor体积提示 |

最近的改动主要在前端。上面的389项后端结果属于MCP接入阶段，不代表最新前端修改后又重新跑过一次全部后端测试。

关键测试文件：

- `server/tests/test_transit_mcp.py`、`test_transit_info.py`、`test_transit_chat.py`。
- `frontend/tests/commuteSummary.test.ts`、`commuteRefresh.test.ts`、`directions.test.ts`。
- `frontend/e2e/workspace-sync.spec.ts`、`assistant.spec.ts`、`agent2-real.spec.ts`、`commute-summary.spec.ts`、`listing-details.spec.ts`、`usyd-housing.spec.ts`。
- `frontend/e2e/fillRentalNeeds.ts`是需求面板测试辅助函数，已用于替代部分旧完整偏好页测试步骤。

本机近期日志包括 `/tmp/rental-needs-panel-browser.log`、`/tmp/rental-needs-panel-mobile-final.log`、`/tmp/rental-needs-panel-build-final.log`。临时测试服务使用8017/5197，已在每轮结束后停止；日志和截图不是仓库交付依赖。

## 8. 接手后的操作方式

当前网站已运行，不必再启动第二份。需要重启时，先核对端口、启动进程和案例目录。本窗口此前使用并保留的用户案例目录为 `.runtime/real-data-local`；不要直接用默认的新 `.runtime` 启动后误认为案例丢失。

```sh
cd '/Users/seven/Documents/AI_coding/5620房产Agent/.workspaces/frontend-demo'
RENTAL_RUNTIME_DIR="$PWD/.runtime/real-data-local" .venv/bin/python scripts/dev.py --web-port 5191 --api-port 8011
```

密钥在该目录的本地 `.env`；只确认配置是否存在，不要打印密钥内容。`TFNSW_API_KEY`已经由用户配置。MCP首次安装命令为 `.venv/bin/python scripts/setup_tfnsw_mcp.py`，需要本机有 `uv`；正常启动由 `scripts/dev.py`管理。

后端重点回归：

```sh
.venv/bin/python -m unittest server.tests.test_transit_mcp server.tests.test_transit_info server.tests.test_transit_chat
```

前端构建与单元测试，在 `frontend/` 目录运行：

```sh
npm run build
node --experimental-strip-types --test tests/*.test.ts
```

浏览器测试应先启动独立案例存储的测试后端与对应Vite端口，再运行仓库Playwright；不要把自动化测试写入用户正在演示的案例。可用 `server.tests.assistant_demo_app:app` 作为模型替身，设置 `RENTAL_ASSISTANT_TEST_RUNTIME`，通过 `RENTAL_DEV_API_PORT`让测试前端指向它。

```sh
WEB_TEST_BASE_URL=http://127.0.0.1:5197 PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' ./node_modules/.bin/playwright test workspace-sync.spec.ts assistant.spec.ts agent2-real.spec.ts
```

当前没有用户授权的新待办需要继续实现。本次已完成最后一轮需求面板精简；后续按用户的新指令推进即可，不必恢复已删内容，也不需要再次询问是否执行这些已确认修改。

## 9. 可直接发给接手窗口的话

请先阅读 `docs/frontend/2026-10-27-agent2-chat-ui-handoff.md`，在 `.workspaces/frontend-demo`继续工作。Agent2本机TfNSW MCP已接入并启用，当前网站端口5191、后端8011、MCP6401。需求统一在聊天的“我的租房需求”抽屉管理，真实模式旧preferences地址已转到该抽屉。用户已明确取消大量说明文字、同步摘要栏、技术弹窗、独立完整偏好页和重复聊天推荐块，请保持精简。平均通勤是可见方式的算术平均；步行超过30分钟不显示、不计入平均，后端筛选仍按所选方式判断。工作区包含其他窗口未提交工作，尤其照片更新逻辑，请先看差异，勿覆盖或重置。当前没有新实现待办，等待用户后续要求。
