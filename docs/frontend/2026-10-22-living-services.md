# 租后生活服务与聊天同步

实现及核对日期：2026-10-22。真实模式页面：`/cases/{case_id}/aftercare`。

## 页面与流程

统一白蓝色租后服务页包含四个入口：

- **日常报修**：保存实际住处、中介/房东、邮箱、电话和紧急维修电话；手动或通过聊天整理问题，确认后保存报修记录和英文邮件草稿，记录“已准备 / 已联系 / 已解决”。支持复制邮件和打开用户邮箱；应用不发送邮件。
- **水电气网**：按类别选择并保存目前使用的供应商，提供官网、联系页面和已核实的客服电话。供水机构按地址确定，仅供记录；不做自由换水务商的推荐。
- **搬运与清洁**：展示真实公司官网及联系方式，按搬运/清洁查看；记录用户取得的报价、服务日期和“考虑中 / 已联系 / 已预约 / 已完成”状态。记录状态不等于向商家下单。
- **退租与押金**：保留 Agent4 的租约确认、退租计划、任务、押金和跟进能力。家具分别记录本人家具与房东家具；实际租约资料需要另行确认，不从房源广告或生成的未签署草稿推断。

页面同时支持保存照片和收据：JPEG、PNG、PDF，每个文件最大 10 MiB，每案例最多 50 个文件且总计不超过 100 MiB。文件留在本地运行目录，按案例隔离并可下载，标记“用户上传，未核实”；可关联报修记录。未接入图片识别、OCR、外部 AI 读取或自动证明材料核验。

## 聊天与页面使用同一份资料

示例：

1. “我的电力公司是 AGL，网络用 TPG，请帮我记下来。”——显示拟保存字段，用户确认后同步到水电气网页；刷新后仍保留。
2. “厨房水龙头一直漏水，帮我写一封报修邮件。”——整理问题并显示保存确认，保存后可在报修页查看邮件草稿。
3. “帮我找悉尼搬家公司 / 退租清洁公司。”——从真实公司目录返回卡片及官方链接，不生成虚构的电话、价格、评分或预约结果。
4. “我现在用哪家电力和网络公司？”——读取当前案例已保存的选择。

聊天页和各租后页面都可发起流程。页面的 AI 按钮只预填聊天输入，不自动发送；每轮调用沿用外部 AI 同意机制。模型接收相关租后摘要和供应商目录，详细住址、联系人邮箱及电话不因已保存在资料中而自动进入模型上下文。用户主动输入到消息中的信息按该轮同意发送。

模型只提出结构化动作。写入由后端校验、用户确认、版本检查和幂等回执完成。页面读取与聊天读取的是同一份案例记录；旧页面或旧聊天提案不能静默覆盖新数据。供应商字段只接受目录中适用类别的 ID，模型不能注入任意网址。

## 真实公司目录

后续更新（2026-10-28）：公司目录扩至33家，其中搬运12家、清洁12家，各新增9家。水电气网的9家供应商仍保留，并另接入[165条套餐与费率](2026-10-28-utility-plans.md)。下表保留最初15家记录，新增条目见文末；联系方式以每条核对日期为准。

来源为公司官方网站，核对日期 **2026-10-22**。目录含 15 家：3 家电力/燃气、5 家网络、1 家水务、3 家搬运、3 家清洁。电力和燃气共用的公司不重复计数。具体覆盖、地址可用方案、套餐费率、服务范围和档期仍由供应商确认，未接入实时比价或商家预订接口。电话未核实的项目保留为空并提供官方联系入口。

| 公司 | 类别 | 电话 / 联系方式 | 来源 |
|---|---|---|---|
| AGL | 电力、燃气 | 131 245 | [官方来源](https://www.agl.com.au/help-support/contact-us) |
| Origin Energy | 电力、燃气 | 13 24 61 | [官方来源](https://www.originenergy.com.au/contact-us/complaints/) |
| EnergyAustralia | 电力、燃气 | 133 466 | [官方来源](https://www.energyaustralia.com.au/home/help-and-support/contact-us) |
| Telstra | 网络 | 官网联系入口 | [官方来源](https://www.telstra.com.au/contact-us) |
| Optus | 网络 | 133 937 | [官方来源](https://www.optus.com.au/support/contact-us) |
| TPG | 网络 | 13 14 23 | [官方来源](https://www.tpg.com.au/contact) |
| Aussie Broadband | 网络 | 1300 880 905 | [官方来源](https://www.aussiebroadband.com.au/contact/) |
| Superloop | 网络 | 1800 57 87 37 | [官方来源](https://www.superloop.com/contact/) |
| Sydney Water | 供水 | 13 20 92 | [官方来源](https://www.sydneywater.com.au/contact-us.html) |
| TWO MEN AND A TRUCK | 搬运 | 1300 880 412 | [官方来源](https://www.twomen.com.au/contact-us/) |
| Grace Removals | 搬运 | 02 9838 5600 | [官方来源](https://www.grace.com.au/location/sydney-seven-hills/) |
| Kent Removals & Storage | 搬运 | 1300 490 557 | [官方来源](https://www.kentremovalsstorage.com.au/contact-us) |
| Simply Maid | 清洁 | 官网联系入口 | [官方来源](https://simplymaid.com.au/services/end-of-lease-cleaning/sydney) |
| Fantastic Cleaners | 清洁 | 02 8103 2006 | [官方来源](https://fantasticcleaners.com.au/contact-us/) |
| Calibre Cleaning | 清洁 | 1300 991 368 | [官方来源](https://www.calibrecleaning.com.au/contact/) |

目录源文件：`server/app/living/providers.json`。紧急维修提示链接到 [NSW 官方维修说明](https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/getting-repairs-done)。清洁页面提供服务选择，不把专业清洁服务作为所有租约的固定必选项。

## 后端接口和存储

- `GET /api/v1/living-providers`：带来源、核对日期和联系方式的目录。
- `GET /api/v1/cases/{id}/living-services`：当前案例资料、供应商选择、报修和服务记录。
- `POST .../profile`、`.../repairs`、`.../repairs/{repair_id}`、`.../bookings`：确认后的写入，使用 `request_id`、`expected_version` 和 `confirmed: true`。
- `POST .../proposals/{proposal_id}/apply`：确认应用聊天提案，检查案例归属及版本。
- `GET/POST .../attachments`、`GET .../attachments/{attachment_id}`：附件列表、原始文件上传和案例隔离下载。服务端验证内容、大小、类型和重复请求内容；附件独立存储，不改变住处资料版本。

后端实现位于 `server/app/living/`，聊天动作位于 `server/app/assistant/living.py`；前端为 `frontend/src/features/living/`。不将候选快照覆盖为实际住处。真实模式租约表单使用空白/未知值及悉尼实际日期；历史 Agent4 演示样例和演示时钟保留兼容。

## 验证记录

- 后端全套：175 项通过，包含租后资料、并发覆盖、幂等、跨案例隔离、聊天提案及附件验证。
- Agent4 原有测试：57 项通过。
- 前端 API 测试：9 项通过；TypeScript 与生产构建通过。构建仍有原有 vendor 包体积提示。
- 浏览器回归：22 项全部通过，覆盖租后服务、聊天同步、原有需求同步与合同草稿。最后一轮修正了旧同意文本定位，并为需求同步按钮补充稳定的无障碍名称，避免加载图标影响按钮定位。
- 实际 `qwen-plus` 模型：供应商保存提案、报修邮件提案、搬运推荐、清洁推荐、读取已保存供应商，共 5 个场景通过。浏览器自动化使用隔离测试后端；实际模型验证独立执行。
- 桌面 1440px 和手机 360px 检查通过，页面无水平溢出、无 JavaScript 错误或浏览器控制台警告。
- 在用户原案例进行只读浏览检查：未保存任何新资料，原案例及聊天历史摘要哈希与检查前一致。

测试使用隔离运行目录；原预览继续在 5191 / 8011 运行。未发送邮件、提交外部预约、支付或修改供应商账户；未提交 Git 或发布部署。

## 2026-10-28 搬运与清洁扩容

新增18条官网资料，未改动原有公司ID，历史报价与预约记录仍可读取。页面与AI按同一目录查询；新增公司可记录用户自行取得的报价，不会自动联系或预订。没有从商家宣传推断星级、保险承保范围或押金必退。

| 公司 | 类别 | 电话/入口 | 来源 |
| --- | --- | --- | --- |
| Men That Move | 搬运 | 1800 438 668 | [官方来源](https://menthatmove.com/contact-us/) |
| Holloway Removals & Storage | 搬运 | 02 8503 4444 | [官方来源](https://hollowayremovals.com.au/contact-us/) |
| Removal Brothers | 搬运 | 0405 919 600 | [官方来源](https://removalbrothers.com.au/) |
| Moveworx Removals & Storage | 搬运 | 1300 731 730 | [官方来源](https://moveworx.com.au/) |
| Optimove | 搬运 | 1300 400 874 | [官方来源](https://www.optimove.com.au/) |
| Man And His Van | 搬运 | 02 9907 3300 | [官方来源](https://manandhisvan.com.au/contact/) |
| NUSS Removals | 搬运 | 02 9425 4600 | [官方来源](https://www.nuss.com.au/) |
| Chess Moving Sydney | 搬运 | 02 9671 8400 | [官方来源](https://www.chessmoving.com.au/about/office-locations/sydney) |
| CityMove Removals | 搬运 | 1300 729 994 | [官方来源](https://www.citymove.com.au/) |
| Maid2Match | 清洁 | 1800 207 686 | [官方来源](https://www.maid2match.com.au/cleaners-sydney/) |
| Absolute Domestics | 清洁 | 1300 364 646 | [官方来源](https://www.absolutedomestics.com.au/services/end-of-lease-cleaning/sydney/) |
| This Is Neat Cleaning | 清洁 | 官网报价表单 | [官方来源](https://thisisneat.com.au/end-of-lease-cleaning/sydney) |
| MaidForYou | 清洁 | 1300 138 892 | [官方来源](https://www.maidforyou.com.au/contact-us/) |
| Maid2Go Cleaning | 清洁 | 02 7256 7367 | [官方来源](https://maid2gocleaning.com.au/) |
| 1800 CLEANER | 清洁 | 1800 253 263 | [官方来源](https://1800cleaner.com.au/contact-1800-cleaner/) |
| Jim’s Cleaning Group | 清洁 | 131 546 | [官方来源](https://jimscleaning.com.au/local/carpet-cleaning/nsw/sydney/) |
| Call The Cleaners | 清洁 | 0451 550 849 | [官方来源](https://callthecleaners.com.au/sydney/) |
| Clean Australia Service | 清洁 | 1300 034 788 | [官方来源](https://www.cleanaustraliaservice.com.au/) |

核对时排除了MiniMovers：其官网明确已退出悉尼业务。This Is Neat只记为退租/搬入搬出清洁，不误写为日常家政。Holloway的缓存代理出现不同营销号码，采用直接官网联系页与公开网页均可核对的02 8503 4444。部分号码/链接以公开索引核对，不代表已实际拨通或查询到实时空档。

本次验证：38项后端测试、10项浏览器测试通过，TypeScript与生产构建通过。5191实际预览只读核对搬运12家、清洁12家，桌面与390px手机布局正常；原有15条供应商对象保持一致，3个实际SQLite数据库的表行数与内容哈希均未变，1000套房源和165条公用事业套餐保留。浏览器新增报价测试仅在隔离测试目录运行。
