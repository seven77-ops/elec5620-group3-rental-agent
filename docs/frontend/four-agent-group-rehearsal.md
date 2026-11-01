# 四人演示与测试流程：Agent 1 → 2 → 3 → 4

按群内分工编写，按钮与功能核对至 **2026-10-31 本地版本**。中文用于排练说明；英文代码块可直接输入产品，英文讲解可按需要精简。

这是**待组员实跑的操作脚本**，不是四个人已经验收通过的记录。参考了[原演示文档](four-agent-presentation-demo.md)，并替换了旧的退租计划、押金激活、操作员密钥等页面步骤。

## 一、人员、边界与交接

| 人员 | 负责演示 | 交接时停在哪里 | 建议时间 |
| --- | --- | --- | --- |
| Agent 1 | 与 AI 逐轮对话，收集、修改、保存 Profile | 主案例的 My rental needs，条件已保存 | 约 3 分钟 |
| Agent 2 | 推荐、改条件后重查、比较、房源页与选房 | 主案例已明确选定一套房源 | 约 4 分钟 |
| Agent 3 | AI 填合同、生成未签署 PDF、检查问题合同 | 返回主案例，保留已保存草稿 | 约4 分钟 |
| Agent 4 | AI 报修邮件、水电网气、搬家清洁、My home、Issue report、人工建议回传 | 用户 History 中看到人工建议 | 约 4 分钟 |
| 最后：Anda | 介绍实现中使用的技术；可补一个 RAG 例子 | 回到完整业务流程总结 | 约 2 分钟 |

**Agent 1 不介绍房源推荐。** 即使条件收齐后系统提前显示房源，也只核对 Profile，把推荐、比较与选定交给 Agent 2。Agent 3 不负责讲退租报告；Agent 4 不重复讲合同生成。

主线可以概括为：

**聊天收集需求 → 保存 Profile → 推荐和修改条件 → 明确选房 → AI 辅助填写并保存合同 → 报修和选择生活服务 → My home 统一查看 → 上报问题和证据 → 人工建议返回 History。**

## 二、开演前的准备

### 2.1 共用一条主线，不要把 localhost 当成共享服务器

1. 推荐四个人轮流操作**同一台演示电脑、同一浏览器、同一个本地服务**。
2. 打开 <http://127.0.0.1:5191>，新建一个**专门演示用**的案例，记为 **A：主案例**，保存网址。
3. Agent 1、2、3 的合同生成、4 都接着用 A，途中不要重新点 New case。
4. 只在 Agent 3 检查问题合同时，另开一个标签页新建 **B：问题合同案例**。检查结束返回 A 的标签页。
5. 四台电脑各自打开 `127.0.0.1`，访问的是各自的本地数据库；单独复制案例网址不会共享数据。若各自在自己的电脑测试，必须各自准备上游步骤或使用同一台服务器，不能假定另一个人的 Profile 已经存在。

不要删除现有案例、清空数据库或把真实合同拿来做演示。

### 2.2 统一演示设定

| 项目 | 统一内容 |
| --- | --- |
| 用户 | 悉尼大学学生，1 人入住，整租 |
| Agent 1 收集 | 每周 900 澳元、整套计价、不限区域、至少 1 卧 1 卫、不需要车位 |
| Agent 1 修改后交接 | 预算改为每周 1000，其余不变 |
| 通勤主线 | 自愿加入公共交通筛选，到 USYD 主校区单程最多 45 分钟 |
| Agent 2 修改 | 预算改回 900，再把最少卧室改为 2；以实际可用结果选房 |
| 合同虚构人物 | Taylor Example、Morgan Example、Olivia Parker |
| 合同演示租金 | **拟议租金**每周 900，拟议押金 3600；这是独立输入的模拟数据，不说成广告价或已经达成的交易 |
| 合同日期 | 2026-11-16 至 2027-11-16，12 calendar months |
| 租后场景 | 切换到虚构的报修、生活服务和退租争议场景，不声称真实已经入住或退租 |

如果演示时间已晚于上表日期，排练时统一改整组日期；不要只改起租日却留下旧结束日。页面的自动提交日期始终使用实际系统时间，不需要手动修改。

### 2.3 准备文件和 AI

- 问题合同：主用[多问题模拟合同 PDF](../../output/pdf/simulated-rental-contract-multiple-issues.pdf)，含日期颠倒、押金金额异常、租客姓名缺失和待确认附加条款。演示者可单独看[错误对照表](../../output/pdf/simulated-rental-contract-multiple-issues-answer-key.md)。原[单一日期错误 PDF](../../output/pdf/simulated-rental-contract-date-error.pdf)保留作备用。
- 报告图片：[a4-entry-condition-demo.png](../../output/presentation-demo/a4-entry-condition-demo.png)、[a4-agent-message-demo.png](../../output/presentation-demo/a4-agent-message-demo.png)。两张都是明确标注的**虚构演示资料**，不是实际入住照片或真实中介聊天。
- 主模型要能用，才可演示自然语言提取、润色和 AI 总结。当前本机只读核对结果是主模型已配置、Jev 为 `active`；组员自己的安装配置不会自动相同。
- Jev 不是检索必需项；组员没有 Jev Key 时可关闭该可选路由，使用自己的主模型配置。不要共享或展示密钥。
- 先预演一次真实 AI 等待时间；正式展示时不要连续点发送、提取或提交。文本超时按后文恢复步骤处理，不承诺固定几秒完成。

## 三、Agent 1：只演示 AI 交互与 Profile

### 1. 开场与首次输入

先介绍：

> “Agent 1 turns a natural-language conversation into a structured rental profile. I will provide the requirements step by step, then review and save them.”

点击 **AI rental assistant**，发送：

```text
Hi, I am a University of Sydney student and I am looking for a place to rent.
```

**等 AI 追问后再回答。** 不要开场就贴完整条件，否则看不到逐轮收集功能。

### 2. 根据追问输入，不机械地照固定顺序连发

| AI 实际问到的内容 | 输入英文 |
| --- | --- |
| 预算 | `My maximum budget is AUD 900 per week.` |
| 计价对象 | `That budget is for the whole property.` |
| 区域 | `I am open to any suburb.` |
| 人数 | `Just me. One person.` |
| 整租还是单间 | `I want to rent the whole property.` |
| 卧室 | `At least one bedroom.` |
| 浴室 | `At least one bathroom.` |
| 车位 | `I do not need parking.` |

如果 AI 一次问了多个相关字段，一起回答它实际问到的内容，例如：

```text
Up to AUD 900 per week for the whole property. I am open to any suburb.
```

```text
At least one bedroom and one bathroom. I do not need parking.
```

介绍重点：AI 需要区分周租/月租、整套/每人等含义，并保留之前已经回答的条件。

### 3. 加入可选通勤条件

住房条件收齐、页面出现选择时：

1. 点击 **Add commute filter**。
2. 如果只是把文字填进输入框，继续点击发送；已经发送则不重复。
3. 根据后续问题回答：

```text
The University of Sydney Camperdown/Darlington main campus.
```

```text
No more than 45 minutes one way, using public transport.
```

介绍：

> “Commute filtering is optional. Here I choose public transport and a maximum one-way commute of 45 minutes.”

本次四人主线统一走加入通勤。**Skip commute filter** 只作为可选分支提一句，不在同一场演示反复切换两种路径。

### 4. 用自然语言只改一个字段

发送：

```text
Change only my maximum budget to AUD 1000 per week. Keep all my other requirements unchanged.
```

检查：只有预算改变；人数、卧室、浴室、整租与通勤条件保留。

### 5. 查看、保存，交接给 Agent 2

1. 点击 **My rental needs**。
2. 指着表单核对：`1000`、`Weekly`、`Whole property`、1 人、1 卧、1 卫、0 车位、45 分钟及实际公共交通选项。
3. 点击 **Save rental needs**，等待保存成功。如果已显示 Saved v… 且按钮因为没有更改而禁用，无需制造修改再保存。
4. 再打开或保留 **My rental needs** 面板，交接。

讲解与交接：

> “The profile is now structured and saved. We can review the extracted values instead of relying only on the chat history. I will hand this same profile to Agent 2 for housing recommendations.”

**本段通过标准：** 信息可核对，预算修改不丢其他条件，保存后重新打开可恢复。无需介绍下面的任何房源。




## 四、Agent 2：推荐 → 修改 → 房源页 → 选定

### 1. 从 Agent 1 的 Profile 开始

展示候选、结果数量和当前筛选条件。介绍：

> “Agent 2 uses the saved requirements to find matching advertisements. The displayed rent, layout and commute references help us compare the options.”

不报固定房源数量、固定第一名或固定地址，以实际页面为准；广告快照不等于房子仍然可以租。

### 2. 改条件后重新推荐

先发送：

```text
Change only my maximum weekly budget to AUD 900 and show the matching properties again. Keep the other requirements unchanged.
```

等结果出来，再发送：

```text
Now I need at least two bedrooms. Keep my maximum budget at AUD 900 per week and my other requirements unchanged. Refresh the recommendations.
```

指着页面讲：预算和卧室确实变了，其他条件保留；候选结果按新条件重算，而非只改变聊天中的一句话。

若实际为零结果，正好说明系统不会虚构匹配。选择页面给出的放宽方案，或明确发送下句后再选房：

```text
Increase only my maximum weekly budget to AUD 1000 and search again. Keep the other requirements unchanged.
```

不要把这个恢复步骤说成每次都必需；最终条件以屏幕和选房确认内容为准。

### 3. 详情与比较

1. 在一套房源上点 **Listing details**；若从列表页进入，按钮可能简写为 **Details**。
2. 展示照片、地址、周租、卧室、浴室、车位。
3. 展示详情中的 **Commute to USYD**，对比 Public transport、Driving、Cycling 等实际显示的方式与时长。
4. 解释列表通勤概览是加权比较参考；通勤筛选仍按所选交通方式，不把概览数字直接说成公共交通时长。
5. 可点 **Google Maps** 或 **View Domain listing** 看对应外部页面，然后返回本应用。
6. 关闭详情，勾选两套房源的 **Compare**，点 **Compare selected listings**。若按钮只填入问题，再发送一次。

需要手动输入比较问题时：

```text
Compare the two properties I selected. Focus on weekly rent, bedrooms, bathrooms, parking and the public transport commute. Explain the trade-offs and what I should confirm with the advertiser.
```

需要介绍指定房源时，把 `[address]` 换成**实际展示的完整地址**再发送：

```text
Explain the main advantages and trade-offs of the property at [address], using the displayed listing facts. What should I confirm with the advertiser?
```

### 4. 介绍独立房源页面

点左侧 **Housing recommendations**。演示一次完整的控件筛选即可：

| 操作 | 动作 | 介绍 |
| --- | --- | --- |
| 价格 | Maximum weekly rent (AUD) 填 900，点 Apply filters | 可以直接使用表单筛选，不必每次聊天 |
| 房型 | Minimum bedrooms 填 2，点 Apply filters | 条件组合会改变结果 |
| 排序 | Sort 选择 Weekly rent: low to high，再点 Apply filters | 按周租排序 |
| 需要返回偏好时 | Restore preference filters | 回到页面关联的已保存偏好，核对屏幕后再继续 |

可简短提及 **Save listing → My favorites**，不必把收藏和比较再完整演一遍。

### 5. 明确选定，交接给 Agent 3

1. 找一套符合最终条件的房源，点击 **Select and follow up**。
2. 在弹窗核对当前条件与地址，点 **Confirm and start follow-up**。
3. 记下选定地址，保留 A。此后不要为制造演示效果随意切换选定房源，否则合同上下文会改变。

交接：

> “The user has now explicitly selected one property. Agent 3 will use this selected-property context to prepare an unsigned lease draft.”

**本段通过标准：** 修改后的条件参与重查；比较能对应所选房源；确认后存在唯一的当前选定房源。

### 6 Rag查询

What should I know about rental bonds in NSW?
What should I check before signing a rental agreement in NSW?


## 五、Agent 3：AI 填写 → 合同 PDF → 问题合同检查

### 1. 打开主案例 A 的合同表单

点击 **Contract assistant → Generate lease draft**，展开 **AI-assisted entry (optional)**。

介绍：

> “Agent 3 can extract proposed contract fields from natural language. The user checks the extracted fields, then explicitly saves an unsigned draft.”

核对 Property address 来自选定房源；不要改成另一套房子。**广告租金不会自动成为双方同意租金**，本次明确输入模拟拟议租金 900/周。

### 2. 第一段 AI 输入：租期与主要条款

在 **Contract details description** 输入：

```text
This is a whole-property NSW tenancy for one occupant. The tenant is Taylor Example, phone 0491 570 006, email taylor.example@example.com, with notice address Unit 5, 25 Example Street, Sydney NSW 2000. The landlord is Morgan Example, phone 0491 570 008, email morgan.example@example.com, with notice address 18 Example Avenue, Parramatta NSW 2150. The fixed-term lease runs from 2026-11-16 to 2027-11-16. Rent is AUD 900 per week and the proposed bond is AUD 3600, not yet paid. Payment is by bank transfer, starting on 2026-11-16 and due every Monday. Use fictional payment details: Demo Rental Account, BSB 000-000, account number 000000000. No additional amenities or separate water usage charges apply. There are no embedded electricity or gas networks, the smoke alarms are battery-powered, and no strata by-laws apply. Both fictional parties agree to electronic notices at their listed email addresses. Leave any remaining details unconfirmed.
```

### 3. 核对、保存、展示 PDF

1. 按表单核对两段数据；完整草稿仍可能缺水电责任、烟雾报警器、电子通知同意等资料，未提供的保持未确认。
2. 如果需要展示手工补填，可把上面的模拟电话、通知地址或付款方式补到对应栏；不要随意勾选具有同意含义的选项。
3. 点 **Check and fill contract**。
4. 在 **Confirm lease draft save** 检查信息和未完成项，完成页面的确认勾选。
5. 点 **Confirm and save unsigned draft**。
6. 展示 **Contract preview · v…**。若已返回表单，可用 **Preview saved v… contract** 再打开。
7. 可点 **Download saved v… PDF** 下载。未提供的项目按草稿状态处理，不承诺这是完整或已经签署的合同。

讲解：

> “The AI output first becomes editable form data. The saved PDF is an unsigned draft based on the template, and unconfirmed details remain visible. Generating it does not sign an agreement.”

### 4. 独立案例 B：上传包含多处问题的合同

保留 A 标签页。另开本应用标签页，新建 B，在聊天发送：

```text
I have a fictional rental contract in PDF format. Please let me upload it for review. Check the tenancy dates, bond, party details and any additional clauses that need clarification.
```

如果聊天已经打开上传入口，直接继续；否则点 **Contract assistant → Upload contract for review**。

1. 点 **Select contract**，选择上文链接的 `simulated-rental-contract-multiple-issues.pdf`。
2. 勾选有权上传并允许 AI 处理的授权。
3. 点 **Upload and analyse**，等待上传和分析结束。
4. 查看 **Contract check results** 中实际的 Needs attention、Passed 和总数，不预报固定数量。
5. 在 Needs attention 找 **Agreement date order**。
6. 展开 **View source text**，读出两个原文日期：开始 `2026-11-16`，结束 `2026-11-01`。
7. 再看 **Bond and weekly rent reference**：周租 AUD 900，押金 AUD 5400。
8. 看 **Tenant** 的缺失资料提示，回 PDF 展示姓名空白。
9. 看 **Additional or special clause**，展示第 2 页的清洁扣款条款。它是待人工确认项，不说成系统已经判定违法。

讲解：

> “This fictional contract contains inconsistent dates, a bond amount that needs checking, a missing tenant name and an additional clause that needs clarification. The available source text lets the user verify the findings.”

补一句实现边界：这类明确的日期错误有本地提取、规则校验支撑；AI 可参与分析与解释。不要把整项检查说成完全依赖模型，也不要把无警告说成法律有效性保证。

本段不在 Human review 中批准这份问题合同，把人工页面主讲留给 Agent 4 的报告场景。

### 6. 返回 A，交接

回到 **A 的标签页**，确认仍是主选定房源和已保存草稿。

> “We have demonstrated both draft preparation and a source-backed contract check. We will now switch to a fictional aftercare scenario for this same housing context.”

**本段通过标准：** AI 提取可核对后应用；保存后可预览 PDF；B 的日期问题对应原文；A 没有被 B 替换。

## 六、Agent 4：报修、生活服务与人工审核闭环

### 1. 在 A 的聊天生成并润色报修邮件

点击 **AI rental assistant**，发送：

```text
The kitchen sink has been leaking since last night. Please prepare a polite repair email in English asking the property manager to arrange an inspection and repair.
```


介绍：

> “Agent 4 helps turn a repair description into an editable email. I can change the wording while preserving the reported facts.”

操作：

1. 最新草稿上点 **Copy email draft**。
2. 点 **Save to Aftercare**。
3. 在弹窗点 **Confirm and save aftercare details**。
4. 点 **Aftercare services → Repairs**，查看相同内容的报修记录。

说明：复制、润色、保存只准备草稿，没有自动发送邮件。不用为了展示而真的点击邮件客户端发送。

核对提案后按页面确认，检查原报修增加备注，而不是多出一条报修。

### 2. 水、电、燃气、网络：选择 → 保存 → My home

点击 **Aftercare services → Utilities**。

| 字段 | 演示选择 |
| --- | --- |
| Electricity provider | AGL |
| Gas provider | Origin Energy |
| Internet provider | Telstra |
| Water authority | Sydney Water |

如果组员目录不同，选实际提供的对应类别，不输入不存在的公司。

1. 可先点 AGL 公司卡片，介绍服务资料与套餐/资费来源，关闭详情。
2. 填好上表四个字段，点 **Save provider selection**。
3. 在弹窗核对并点 **Confirm selection**。
4. 点 **View in My home**，展示 Utilities 中已保存的四个名称。
5. 关闭 My home，继续下一段。

讲解：

> “The selected utility providers are saved with the home information. My home gives the user one place to review the saved choices.”

水务由地址对应的服务机构决定，不介绍成和电力、网络一样可随意切换；套餐价格和地址可用性需向供应商确认，保存选择不会开通账号。

### 3. 搬家、清洁：先保存公司，再统一查看

点击 **Moving and cleaning**。

1. 打开 **TWO MEN AND A TRUCK** 公司卡片。
2. 在详情点 **Save to My home**。
3. 在 **Save this service to My home?** 中点 **Confirm and save**。
4. 打开 **Simply Maid**，重复保存。
5. 点页面的 **View in My home**，展示 Moving and cleaning 中两个公司及 Considering 状态。
6. 若该公司已经保存，详情直接显示 **View in My home**，无需再重复保存。

介绍：

> “The user can save moving and cleaning companies before obtaining a quote. These choices are visible in My home, together with any recorded service details.”

### 4. 用户提交问题及证据

关闭 My home，点 **Issue report → Report issue**。

1. **Issue type** 选择 **Rent / bond**。
2. **Issue description** 输入下面内容。当前表单没有单独的标题、退款金额或人工请求字段，所以把这些信息写在描述中。

```text
Proposed bond deduction for pre-existing wall marks.

The property manager has proposed an AUD 300 deduction for wall marks. I dispute this because the example entry condition record notes the marks as pre-existing.

I have attached a entry condition record and a fictional agent message. Please compare the two records and advise what supporting information I should request before replying. I have not accepted the proposed deduction.
```

3. 点 **Upload files**，选择准备好的两张 `a4-…-demo.png`。
4. 等上传完成，确认文件出现在表单；点击缩略图可预览。
5. 点 **Submit report**。
6. 页面转到 **History**，检查描述、两份附件、自动生成的日期和待审核状态。

介绍：

> “The user reports the issue, explains why it needs review and attaches evidence. The submission date is recorded automatically.”

这是虚构的退租争议，不需要再创建退租计划、激活押金跟进或填写额外案件设置。上传支持 PNG、JPEG、PDF，每份最多 10 MB，一次报告最多 10 份。

### 5. 人工审核：看内容、看证据、写建议

1. 点左侧 **Human review**。页面直接加载，**没有操作员密钥输入**。
2. 在 **Pending (…)** 找到 `DEMO-A4` 对应的报告，核对 Rent / bond 和描述；不要因为是第一条就操作，也不要误选 Agent 3 的 Contract 记录。
3. 看 **Report details**，解释“问题是什么、为什么 report、用户希望人工做什么”。
4. 看 **Evidence**，打开两份图片，说明审核者能看见原上传资料。
5. 在 **Review advice** 输入：

```text
These  records indicate that the wall marks were noted at the start of the tenancy. Ask the property manager for the proposed deduction breakdown and supporting documents, and compare them with the entry record before replying. Keep the original records. This review does not confirm that a refund has occurred or that the deduction is accepted.
```

6. 点 **Save advice and complete review**。
7. 在人工页面的 **History (…)** 找到已审核记录和建议。
8. 点该记录的 **View report**，回到用户的 Issue report History，读出同一条建议。

讲解：

> “The report reaches the human-review queue with its evidence. The reviewer records advice, and that advice is returned to the user's history. This closes the communication loop.”

完成审核表示建议已记录，不表示实际退款、接受扣款或完成外部争议处理。

**本段通过标准：** 报修草稿能保存；供应商和服务选择能在 My home 找到；报告连同附件进入人工队列；人工建议回到用户 History。

## 七、排练记录与故障恢复

每人实跑后，在下表填自己的实际结果；不要把“脚本写了”当作“已经测试通过”。

| 检查点 | 应看到什么 | 实跑结果/截图 |
| --- | --- | --- |
| A1 收集 | 已答条件保留，预算可单独修改 | 待填写 |
| A1 保存 | My rental needs 可恢复正确字段 | 待填写 |
| A2 重查 | 条件变化与候选结果对应 | 待填写 |
| A2 选定 | 唯一当前选定地址，交接到 A3 | 待填写 |
| A3 提取 | 两段 AI 结果经核对后进入表单 | 待填写 |
| A3 PDF | 已保存版本可预览和下载，保持未签署 | 待填写 |
| A3 检查 | 问题 PDF 的两条日期原文可见 | 待填写 |
| A4 报修 | 简化邮件保留事实，保存后原文一致 | 待填写 |
| A4 生活服务 | 保存的供应商、搬家和清洁记录在 My home | 待填写 |
| A4 报告 | History 有自动日期、描述、附件 | 待填写 |
| A4 审核闭环 | 人工队列看到同一证据，用户 History 收到建议 | 待填写 |

常见情况：

- **Agent 1 追问顺序不同：** 回答它实际问的字段，不把表中所有答案连续发一遍。
- **推荐为零：** 演示明确放宽一个条件再查，不声称零结果是成功匹配。
- **AI 提取超时：** 原文和表单保留；等请求结束再按 Retry original action 重试，或将该段拆小。也可手动填入同一组虚构字段继续 PDF，但要如实说这是人工补填，不能说本次 AI 已成功。
- **AI 提取有遗漏：** 看字段核对窗和 Still needed，手动补对应信息；不要让模型编造未提供的联系方式或同意。
- **版本冲突：** 使用页面的 Load latest details / Load latest report 或刷新入口，比较保留的输入后再明确保存；不要清空数据绕过冲突。
- **Human review 没找到：** 先在用户 History 确认本次确实提交成功，再在人工页点 Refresh reports，按 `DEMO-A4` 描述和类别查找 Pending/History。
- **保存了公司却没报价：** Considering 是“已保存选择”，不是已预订。报价、日期只在实际录入后显示；点 My home 的 View record 可补记录。
- **切到了 B 或其他案例：** 用事先保存的 A 标签页/网址返回；不能把 B 的合同检查结果当成 A 的选房合同。

若限时较短，保留每个 Agent 的主任务，删去收藏、第二次比较、报价补录、私有合同问答和可选 RAG 展示；**保留报告 → 人工审核 → 用户收到建议的最后闭环**。
