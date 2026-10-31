# 水电气网套餐与计价数据

2026-10-28：165 条官方套餐/费率快照，覆盖 9 家供应商。AGL 32、Origin 50、EnergyAustralia 51 条电气方案（含配网和电表费率变体）；Telstra 5、Optus 5、TPG 8（含两档5G家庭宽带）、Aussie Broadband 6、Superloop 7 条网络方案；Sydney Water 一套2026–27住宅收费表。它们不是165个完全不同的品牌套餐，也不是全市场目录。

## 来源与保存

- 电气：[AER公开产品数据接口](https://www.aer.gov.au/energy-product-reference-data)，按官方零售商端点与版本读取：目录 `x-v:1`，明细 `x-v:3`。保留方案编号、来源更新时间、生效/到期、邮编和配网、电表类型、所有阶梯/时段及受控负荷、折扣和费用。选择覆盖悉大周边和通勤区域的一般住宅套餐系列，排除商业和专属合作渠道系列。
- [CDR标准](https://consumerdatastandardsaustralia.github.io/standards/)规定用量单价和每日固定费不含GST。原始结构原样保存，展示另加10% GST；其他费用不自动重复加税或抵扣折扣。
- 网络来源：[Telstra](https://www.telstra.com.au/internet/plans)、[Optus](https://www.optus.com.au/broadband-nbn/home-broadband/plans/shop)、[TPG](https://www.tpg.com.au/nbn)、[Aussie Broadband](https://www.aussiebroadband.com.au/internet/nbn-plans/)、[Superloop](https://www.superloop.com/internet/nbn/)。分别记录促销价格、期限、截止日、恢复价、典型晚高峰上下行、技术、路由器及退出条件。Aussie可见卡片优先于不包含促销的JSON-LD；Telstra不同接入技术的同名卡片按实际速度区分。
- [Sydney Water住宅水价](https://www.sydneywater.com.au/accounts-billing/paying-your-bill/our-prices/residential-pricing.html)：普通水3.41 AUD/kL、条件性旱情水3.84 AUD/kL，再生水3.07 AUD/kL；最长92天季度供水26.65、污水189.88 AUD。固定费按日计算，不能直接当作租客应付款。供水方由地址确定。
- 费用责任：[NSW私人租赁用水规则](https://www.nsw.gov.au/housing-and-construction/rules/connection-and-supply-of-water-to-rental-properties)及[Sydney Water租客说明](https://www.sydneywater.com.au/your-home/moving-renovating-building/renting.html)。独立水表、节水、账单证据等条件必须核对，公屋等特殊情形另核。

版本化种子位于 `server/app/living/data/utility-plans.json`。服务启动后导入运行目录的 `utility_catalog.sqlite3`，使用 `utility_snapshots` 和 `utility_plans` 表，按内容指纹幂等导入，旧快照保留。默认预览数据库为 `.runtime/real-data-local/utility_catalog.sqlite3`。用户案例、供应商选择和房源目录独立保存。

## 查询与推荐

`GET /api/v1/living-providers` 返回原供应商信息及套餐卡片；内部查询读SQLite。AI仅负责识别租后服务问题，金额由本地记录组装。按供应商、类别和已给邮编筛选；网络预算按恢复价筛选，并比较首12个月基础月租。显示地址未核实、设备及特殊安装未计等实际比较边界，不声称全市场最低。电气保留完整时段/阶梯，不用最低时段价格冒充所有用量价格，也不在缺用量/电表信息时编造月账单。

每条记录按自身采集日30天时效和官方生效/失效日期检查。过期记录可在目录中带状态展示，但不参与推荐。促销截止后恢复标价，不继续套用优惠；新文件时间或单独刷新能源不得更新其他记录采集日。

显式更新能源：

```sh
.venv/bin/python tools/refresh_utility_energy.py
```

该命令仅下载AER公开产品数据，全部成功后原子更新能源种子，随后重启API导入。网络促销和水价须重新核对各自官方页面。未配置自动任务，不联系供应商、不创建订单、不读取客户账户。

## 验证结果

- 相关后端81项通过；随后新增的“网络预算简写”用例及完整套餐模块10项通过，覆盖SQLite幂等/历史快照、官方截止时刻、过期优惠恢复原价、过期价格不推荐、NBN不替换成5G、GST及来源字段。
- 浏览器11项通过（8项已有租后流程＋3项新套餐测试），涵盖优惠与恢复价、官方链接、聊天预算、供应商选择不自动保存和手机布局。TypeScript/Vite构建通过。
- 真实模型的网络套餐、电费和水费三类问题均返回本地价格卡片；水费首次供应商服务503，重试成功，未编造价格作为错误回退。
- 实际5191页面只读复核成功，数据库165条、9家供应商；原有两份用户数据库内容及1000套房源目录的哈希在重启前后保持一致。测试案例与人工智能调用均在隔离目录，未向供应商发送个人地址。
