# 区域资料与个性化推荐

## 已接入的流程

- AI 路由新增 `area_advice`：比较或了解区域时，不必先填写通勤目的地。模型只能输出区域名称和明确需求，事实、来源链接和库存数量由服务端检索。
- 用户的生活主题保存在当前对话 `rental_brief.lifestyle_priorities`，可在聊天修改、清空，也能在“我的租房需求”面板编辑。房型与预算仍经过现有确认流程才写入正式偏好。
- 区域比较同时展示当前预算/房型摘要、符合这些房屋条件的库存数量、房源标价范围、相关设施、资料缺口、来源与日期。人数和未知计价对象不用于乘除租金。
- 通勤推荐给已有区域卡片增加相同的资料组件；硬条件、实际路线时长优先，生活主题只在既定租金/通勤排序相同时辅助比较。
- 聊天生成的区域比较共享到房源推荐页，可回到原会话调整。跨会话新需求、需求面板编辑、目录变更、资料变更及资料有效期到期都会使旧报告需要更新。

## 首批数据

文件：`agent2/data/areas/sydney-evidence.json`，版本 `2026-10-24.1`。

12 个区域、16 条简短资料摘要：Burwood、Rhodes、Redfern、Camperdown、Glebe、Marrickville、Petersham、Strathfield、Eastwood、Chatswood、Parramatta、Ashfield。当前房源库共有 71 个区域；其余区域仍可问答和显示库存，但显示“资料尚未整理”，不借用邻区资料。

来源包括 City of Sydney、Canada Bay、Inner West、Strathfield、Ryde、Willoughby、NSW Government、Greater Sydney Parklands、Burwood Chinatown、SBS 及 Homely。官方设施介绍、运营方介绍、媒体背景和住户观点分开展示。Homely 仅保留带出处的简短评论背景索引，不复制评论全文。AUO 未入库。

每条证据记录包括 `evidence_id/suburb/topics/kind/summary/geographic_scope/scope_label/limitation/review_after_days/source`。source 保存 publisher、title、url、published_at、updated_at、data_period、checked_at；原始发布日期不明时留空，核对日期不能当作原始发布日期。

## 检索与证据边界

- 生活主题：公园与户外、餐饮、购物、图书馆、社区设施、散步步道、安静、安全。社区设施不等于社区氛围；步道存在不等于整体步行便利指数。
- 仅当前核对有效期内的官方/运营方设施资料用于对应主题参考。媒体和住户评论只作背景；LGA 或邻近设施不算某个 suburb 已满足条件。
- Rhodes 的 Learning Space 保留为社区设施，不把名称推断成图书馆。Camperdown 的 Victoria Park 资料明确标注来源地址 Broadway，仅供周边设施参考。
- 安静、安全、隔音、具体房源到设施的距离和可租状态均未从区域资料推断；未核实项明确展示。存在公园不能证明房源安静。
- 设施资料默认 120 天重新核对；到期后不用于已核对的主题参考，旧共享报告提示过期。资料没有自动联网更新机制，需人工复核摘要与原文后更新核对日期。
- 房源价格是现有快照中的标价范围，不是整个区域的市场租金统计。真实通勤仅沿用现有 TfNSW 路线查询。

## 接口与文件

- 新增 `GET /api/v1/cases/{case_id}/assistant/area-advice`，读取案例所属的共享比较；返回 stale 和 stale_reasons。
- `server/app/areas/evidence.py`：资料加载、有效期、主题检索、库存关联。
- `server/app/assistant/areas.py`：模型可用主题、只读问答、通勤资料装配与共享比较。
- `frontend/src/features/assistant/AreaAdvice.tsx`：聊天与推荐页共用资料卡。

## 实例验证

实际调用本地已配置的 qwen-plus，使用独立临时案例完成五轮：

1. 整套每周900、两卧，比较 Burwood/Rhodes，喜欢公园和餐饮：正确识别全部条件；当前快照对应5条/1条。
2. 保持预算户型，仅改为看重图书馆：保留900和两卧，两个区域显示图书馆资料缺口。
3. 清空生活偏好：列表置空，预算户型保留。
4. 问 Carlton 是否安静安全：显示资料尚未整理，两项均待核实。
5. 新到悉尼、整套850、两卧一卫、Camperdown校区、工作日9点、公交40分钟、公园：正确进入通勤推荐追问；本次未授权位置查询，不编造路线。

实际 AI 的首次验证发现区域问题中预算/卧室被漏提取；已补全路由指令并重跑上述五轮通过。另用当前5191网站的实际 AI、变体表述验证整套周租900/两卧及来源卡片。

自动化覆盖资料时效、地域范围、不同计价对象、硬条件、非法模型字段、主题保留/清空、新旧会话共享结果、页面跳转、来源展开、通勤卡片复用及360px布局。浏览器插件未提供，使用项目已有 Playwright 和本机 Chrome；测试分类器夹具只用于自动化页面回归，实际模型验证单独运行。

测试证据：`/tmp/area-live-ai-results.json`、`/tmp/area-live-browser-results.json`、`/tmp/area-final-backend-tests.log`、`/tmp/area-advice-live-desktop.png`、`/tmp/area-advice-live-mobile.png`、`/tmp/area-advice-live-shared.png`。这些是本次本地验证文件，不作为产品资料源。

最终验证：318 项后端测试、15 项前端单元测试、11 项浏览器回归全部通过；TypeScript 与生产构建通过（现有 vendor 包体积提示仍存在）。独立审查发现的跨会话失效和自然过期问题已修复并增加回归。当前5191网站已重启加载；原用户案例相关32个对象哈希逐项一致，500条房源文件未作改动。
