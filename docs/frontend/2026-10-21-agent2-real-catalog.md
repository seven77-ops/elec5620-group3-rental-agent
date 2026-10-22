# Agent2 真实房源网页接入

默认网页和后端使用 `agent2/data/real/listings.json` 的500条住宅广告，覆盖71个 suburb。卧室、浴室、车位、广告周租均有值，其他缺失事实保持 null。补采池中的一条单独出租车位广告已剔除并用住宅补位。

正常启动不读取 `agent2/data/demo/listings.json`。该文件和原确定性评分器仅用于显式注入的历史回归夹具。真实快照缺失或非法时启动失败，没有模拟数据回退；无需配置 Domain API 密钥即可读取本地已采集快照。

## 接口

- `GET /api/v1/listings`：`suburb`、`min_bedrooms`、`min_bathrooms`、`min_car_spaces`、`max_weekly_rent`、`sort`、`page`、`page_size`。排序支持 rent_asc/rent_desc/bedrooms_desc，默认每页20、最多100。返回 items/total/page/page_size/filters/catalog；catalog 包含全部区域和快照指纹。
- `GET /api/v1/listings/{listing_id}`：原始来源、核心字段和未知事实。ID 使用 `domain:<广告编号>`。
- `POST /api/v1/cases/{case_id}/evaluations`：保留 request_id/confirmation_version，新增可选 filters（字段同列表筛选，不含分页）。必须使用当前 Agent1 已确认偏好。返回真实候选报告，data_mode=real_listings，schema_version=real-1.0；score/weekly_cost/commute 等不明事实为 null，eligible 为空，候选为 pending。不传 filters 时从已确认偏好映射预算和 housing_preferences；传入 filters 时为明确标注的手动筛选。返回 filter_source/profile_filters/unverified_preferences/mapping_policy，不能当作已完成费用、租期或通勤资格检查。
- 现有报告读取和 JSON/Markdown 导出接口保留。历史模拟报告只读，不可用于新选房。相同报告可再次激活成为案例最新报告，原报告快照不可变。
- `POST /api/v1/cases/{case_id}/selections`：保留原请求格式，校验当前偏好、报告归属、真实数据模式、数据指纹及本次结果内的房源。保存 `candidate_selected` 快照，requires_verification=true，contract_ready=false。
- 现有候选导出接口可下载真实来源和完整快照。偏好未改变时同一 request_id 可重试；偏好或数据上下文改变后原写请求返回409，历史报告与快照仍可读取。新 request_id 不会改写旧报告内容。
- `/health` 和 `/demo-config` 默认 mode=real_listings；后者保留旧路径以兼容前端引导，不代表房源使用模拟数据。

## 网页行为

独立“真实数据”导航和页面已取消，旧链接重定向到“房源推荐”。500条来源广告在推荐页统一展示，租金参考、补充记录与通勤查询位于下方“房源补充工具”。支持区域、至少卧室/浴室/车位、最高广告周租和排序。筛选改变会回到第1页，旧请求不能覆盖新结果。详情显示原链接、索引时间和未知字段。

确认偏好后可以生成当前筛选的候选报告，再保存其中的房源。重新进入页面恢复最近真实报告的筛选条件。刷新后候选仍保存在原案例 SQLite 数据库内。未核实的真实候选不传入只支持既有证据契约的 Agent3；旧模拟 AI 推荐解读器同样不处理真实报告，避免伪造有效评分或发出误导性证据。

## 限制

这是公开索引中的广告快照，不是实时在租 API。采集/快照时间不代表页面更新时间或房东确认时间；列表会保留是否读到详情和来源索引时间标签。租金计价对象和额外费用尚待核实，不能把广告价直接称为人均预算或含账单总费用。通勤、精确位置、租期与市场估值没有补造。

Agent1 的真实偏好状态仍为版本绑定依据；Agent2 真实流程不调用原只接受模拟证据的评分/交接接收器，因而不声称生成完整四维评分或已核实推荐。当前能力是事实筛选、原始来源核对和持久化候选。

## 验证

后端回归使用 `python -m unittest discover -s server/tests -v`；真实模式专用覆盖见 `server/tests/test_real_agent2.py`。历史合成测试从 `server/tests/legacy_app.py` 显式注入夹具，独立于默认应用启动。网页覆盖见 `frontend/e2e/agent2-real.spec.ts` 与 `real-data.spec.ts`，包括四字段、分页、筛选、未知项、空结果、偏好生成报告、保存/刷新、手机布局和来源链接。

验证（含本次偏好联动）：后端90项、Agent1原有回归52项、前端接口9项、浏览器11项均通过；TypeScript/Vite构建通过。Browser插件未提供，使用已安装Chrome与Playwright验证1440×1000及360×800；控制台无应用错误/警告，无框架错误覆盖层，手机文档无横向溢出。表格内部允许横向滚动以保留核心列。保留已有Ant Design vendor包体积提示。独立审查发现的重复筛选激活、候选状态文案和延迟报告覆盖输入均已修复并验证。

原预览已在5191/8011重启，原案例可读，health.mode=real_listings，默认房源接口total=500、suburb_count=71。检查只读访问原案例；自动化写操作全部使用独立测试runtime。

## 用户确认的开放式房源计数口径

原广告卧室数为0的5条Studio，运行时按1个开放式起居睡眠空间计入展示、卧室筛选、排序、新候选报告及选房快照。API保留advertised_bedrooms=0，并提供bedroom_count_basis=open_plan_as_one、bedroom_label=1（开放式）。原始广告JSON不改写，不将其称为独立卧室。其他房源卧室数保持不变，房源总数仍为500。规范化后的数据参与指纹计算，旧报告不会与新口径混用；历史快照保持不可变。

## 已确认偏好与推荐条件联动

`housing_preferences` 为兼容旧偏好的可选对象，支持 suburb/min_bedrooms/min_bathrooms/min_car_spaces/budget_match_mode，经 Agent1 草稿和确认流程保留。所有房屋条件可留空（null 表示不限制）。`GET /api/v1/cases/{case_id}/recommendation-context` 只返回当前已确认版本的条件；未确认时返回默认浏览全部房源。

最高预算为硬条件时，默认 advertised_amount 将原金额作为最高广告周租粗筛，明确不保证每人、每间或含账单总费用。matching_scope 选项因当前广告计价对象未知，不应用预算上限，保留为待核实。软预算不作排除；不按居住人数擅自分摊租金。通勤、容量、独立卧卫、设施与租期仍待核实。

推荐页自动恢复已确认偏好或当前版本报告的筛选。手动调整需应用筛选，并显示与偏好可能不同；“恢复偏好筛选”恢复当前确认版本。生成期间禁用筛选编辑，避免返回响应覆盖新输入。修改偏好后必须重新确认和生成报告，旧规则报告保留但不能作为本轮选房依据。
