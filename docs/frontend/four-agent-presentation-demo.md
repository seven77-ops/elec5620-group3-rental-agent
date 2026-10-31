# 四个 Agent 的交互测试用例：输入与按钮

- 打开 <http://127.0.0.1:5191>，点击 **New case**，保存主案例网址。
- 四个人共用这个主案例；问题合同 PDF 使用另一个新案例。
- 复制英文代码块输入，中文仅供理解。需要使用 AI 时，按页面完成对应授权。

## 可穿插测试：直接在聊天中提问租房知识

无需寻找单独的知识问答按钮。在 **AI rental assistant** 当前对话中发送：

```text
How do I request repairs in NSW?
```

中文：在新南威尔士州应该怎样申请维修？

检查回答和来源引用出现在聊天中，点击 **Read source excerpts** 查看原文。再继续回答之前尚未完成的租房需求问题，已经记录的预算和区域应保留。

也可以输入产品使用问题：

```text
How do I compare properties in this app?
```

中文：如何在这个应用中比较房源？

涉及本人上传合同的具体条款时，使用该合同的审核与问答入口，按页面完成对应文档的授权。

## Agent 1：收集并保存偏好

### 1. 只说想租房，不提前提供完整条件

点击 **AI rental assistant**，输入并发送：

```text
Hi, I am a University of Sydney student and I am looking for a place to rent.
```

中文：你好，我是悉尼大学学生，想租房。

**发送后等待 Agent 追问，不主动把预算、房型、人数和通勤全部发过去。**

### 2. 根据 Agent 的追问，逐轮提供信息

在同一个对话里，Agent 问到哪一项，就使用对应的短回答。下面的“追问内容”是用来辨认问题的提示，不是保证 Agent 会逐字返回的固定台词，也不要求固定顺序。

| Agent 追问内容 | 输入给 Agent 的英文回答 | 中文 |
| --- | --- | --- |
| 预算多少？ | `My maximum budget is AUD 900 per week.` | 最高预算每周 900 澳元。 |
| 是整套、每人还是每间的预算？ | `That budget is for the whole property.` | 这个预算针对整套房子。 |
| 偏好哪个区域？ | `I am open to any suburb.` | 不限区域。 |
| 几个人入住？ | `Just me. One person.` | 只有我，一个人。 |
| 整租还是租一个房间？ | `I want to rent the whole property.` | 我想整租。 |
| 至少需要几间卧室？ | `At least one bedroom.` | 至少一间卧室。 |
| 至少需要几间浴室？ | `At least one bathroom.` | 至少一间浴室。 |
| 需要车位吗？ | `I do not need parking.` | 不需要车位。 |
| 选择加入通勤筛选后：到哪个学校或校区？ | `The University of Sydney Camperdown/Darlington main campus.` | 悉尼大学 Camperdown／Darlington 主校区。 |
| 选择加入通勤筛选后：单程最多接受多久？ | `No more than 45 minutes one way.` | 单程不超过 45 分钟。 |
| 选择加入通勤筛选后：希望怎么通勤？ | `Public transport.` | 公共交通。 |

**每次发送一个回答后，等待 Agent 的下一次回复，再继续。** 已经回答并被记住的内容，不用重复输入。

如果 Agent 一次问了两个或几个相关问题，可以一起回答它实际问到的内容。例如：

- 同时问预算、计价对象和区域：

  ```text
  Up to AUD 900 per week for the whole property. I am open to any suburb.
  ```

  中文：整套每周最高 900 澳元，不限区域。

- 同时问卧室、浴室和车位：

  ```text
  At least one bedroom and one bathroom. I do not need parking.
  ```

  中文：至少一卧一卫，不需要车位。

住房基本条件齐全后，通勤是**可选条件**：

- **不限区域，想按通勤找房**：点击 **Add commute filter**，再发送填入聊天框的回答。Agent 问最长多久时回答 `No more than 45 minutes one way.`，问方式时回答 `Public transport.`；两项一起问时可以一起回答。
- **不限区域，不需要通勤筛选**：点击 **Skip commute filter**，再发送填入聊天框的回答。之后按住房条件继续，不需要补时间和交通方式。
- **已经确定住 Burwood**：区域问题直接回答 `I want to live in Burwood.`（我想住 Burwood）。条件收齐后不必补通勤。也可以明确说明：

  ```text
  I only want Burwood. I already know the commute and do not need a commute filter.
  ```

  中文：我只考虑 Burwood，已经了解通勤，不需要通勤筛选。

主案例建议四人事先选定同一条路径。下面 Agent 2 的第一个推荐问题适用于“加入通勤筛选”的路径；不使用通勤时，改用它下面的简短问题。

### 3. 修改预算

```text
Change only my maximum budget to AUD 1000 per week. Keep all my other requirements unchanged.
```

中文：只把最高预算改成每周 1000 澳元，其他需求不变。

### 4. 保存偏好，停在需求面板

依次点击：

1. **My rental needs**。
2. 核对：预算 1000、Weekly、Whole property、1 人、至少 1 卧 1 卫、0 车位，以及实际选择的区域。只有选择了通勤筛选，才核对 Public transport (any combination)、45 分钟；跳过通勤时相关字段应为空。
3. **Save rental needs**，按界面要求完成确认。
4. 再打开 **My rental needs**，停在这个面板，交给 Agent 2。

当前版本可能提前显示候选房源。Agent 1 不展开房源、不比较、不选定跟进。

## Agent 2：推荐、比较、筛选和选定跟进

### 1. 使用已保存需求推荐房源

关闭 Agent 1 留下的需求面板，在同一个案例的聊天中发送：

```text
Use my saved rental requirements to show matching properties. Keep the maximum budget at AUD 1000 per week, with at least one bedroom and one bathroom, no parking requirement, and a public transport commute of no more than 45 minutes to the University of Sydney main campus.
```

中文：按保存的需求推荐，预算每周 1000，至少一卧一卫，不要求车位，到悉大主校区公共交通不超过 45 分钟。

**如果 Agent 1 跳过了通勤筛选，使用这句：**

```text
Use my saved rental requirements to show matching properties. Keep my selected area and housing requirements unchanged, without a commute filter.
```

中文：按保存的需求推荐，保留已选区域和住房条件，不加入通勤筛选。


### 2. 打开房源详情

1. 在一张房源卡片上点击详情入口，例如 **View listing details / Listing details**。
2. 查看照片、租金、卧室、浴室和通勤。各交通方式以简洁卡片显示约略时长或估算区间；点击对应的 **Google Maps** 查看当前路线。列表中的 **Commute to USYD** 为加权比较参考，可在详情中的 **Commute weighting** 查看权重；筛选仍使用所选交通方式。
3. 可点击 **View Domain listing** 打开原广告。
4. 关闭详情。

如需让 AI 介绍该房源，通过该房源的聊天入口，或把下面的 `[address]` 替换成卡片上的完整地址，再发送：

```text
Please explain the main advantages and trade-offs of the property at [address], using the displayed listing facts. Which details should I confirm with the advertiser?
```

中文：请根据展示的信息，介绍这套房源的优点、取舍及仍需确认的事项。

### 3. 比较两套房源

1. 在两张房源卡片上勾选 **Compare**。
2. 点击 **Compare selected listings**。
3. 如果按钮只是填入问题，再点击发送；已经发出则不要重复发送。

如需调整比较问题，使用：

```text
Compare the two properties I selected. Focus on advertised weekly rent, bedrooms, bathrooms, parking and public transport commute. Explain the trade-offs and identify information that still needs confirmation.
```

中文：对比我选中的两套房源的周租、卧室、浴室、车位和通勤，说明取舍及待确认的信息。

### 4. 在房源推荐页筛房

点击左侧 **Housing recommendations**，按下面的顺序操作：

| 操作 | 填写或点击 |
| --- | --- |
| 调整价格 | **Maximum weekly rent (AUD)**：1000 改为 900 |
| 应用 | **Apply filters** |
| 调整卧室 | **Minimum bedrooms**：1 改为 2 |
| 应用 | **Apply filters** |
| 排序 | **Sort → Weekly rent: low to high**，再点 **Apply filters** |
| 恢复 | **Restore preference filters** |

也可以操作 **Area、Minimum bathrooms、Minimum car spaces、Commute mode to campus、Maximum commute to USYD (minutes)**，修改后点 **Apply filters**。

### 5. 选定一套房源并跟进

1. 完成筛选后，在一套房源上点击 **Select and follow up**。
2. 在确认弹窗中点击 **Confirm and start follow-up**。
3. 保留这个案例，交给 Agent 3。

可选收藏操作：两套房源分别点击 **Save listing** → **My favorites** → 勾选两套的 **Compare**。

## Agent 3：填写合同与审核 PDF

### 1. 打开合同填写

在主案例点击：

**Contract assistant → Generate lease draft**。

保留选定房源的地址和拟议租金，在 AI 辅助填写的描述框中输入：

```text
This is a synthetic demonstration. The tenant is Taylor Example and the landlord is Morgan Example. This is a whole-property fixed-term tenancy for one adult, starting on 2026-11-16 and ending on 2027-11-15. Rent is paid weekly. Keep the selected property's address and proposed rent unchanged. Leave any details I have not supplied unconfirmed.
```

中文：模拟租客 Taylor Example、房东 Morgan Example，一人整租，固定租期 2026-11-16 至 2027-11-15，按周付租。保留当前地址和拟议租金，未提供的内容保持未确认。

依次点击：

1. 勾选本次 AI 字段提取授权。
2. **Extract contract details with AI**。
3. 核对弹窗内容。
4. **Fill these fields into the form**。

### 2. 保存并预览合同 PDF

1. 核对表单；缺少的模拟资料按页面提示补充，不知道的保留未确认。
2. **Check and fill contract**。
3. 在确认弹窗完成要求的勾选。
4. **Confirm and save unsigned draft**。
5. **Preview saved v… contract**。
6. 可点击 **Download saved v… PDF** 下载。

保存主案例网址，下一步暂时切换到独立的合同检查案例。

### 3. 上传带问题的合同

新建一个案例，打开 **AI rental assistant**，输入：

```text
I have a rental contract in PDF format. Please let me upload it for review and check its key details, including the tenancy dates.
```

中文：我有一份 PDF 租房合同，请让我上传审核，并检查包括租期在内的关键信息。

依次操作：

1. 使用聊天中的上传入口，或打开 **Contract assistant → Upload contract for review**。
2. 完成该文档的处理授权。
3. 选择 [模拟问题合同 PDF](../../output/pdf/simulated-rental-contract-date-error.pdf)。
4. 勾选有权提交文档。
5. **Upload and review**。
6. 找到 **End date is not after start date**。
7. **View source 1 / View source 2**，查看两个日期原文。

### 4. 可选：追问合同问题

展开 **Ask more about this contract**，勾选本地私有检索授权，点击 **Enable contract search**。需要 AI 回答时，另行完成云端处理及本次问题的 AI 授权。

在 **Contract question** 输入：

```text
Are the tenancy start and end dates consistent? Cite both dates from the uploaded contract and explain the problem.
```

中文：合同起止日期是否一致？请引用两个日期并解释问题。

点击 **Find contract text**；启用本次 AI 时则点击 **Explain contract with AI**。

完成后回到主案例，交给 Agent 4。

## Agent 4：报修、退租任务和人工审核

### 1. 在聊天里生成报修邮件

回到主案例的 **AI rental assistant**，输入：

```text
The kitchen sink has been leaking since last night. Please prepare a polite repair email in English asking the property manager to arrange an inspection and repair. Show the full draft here, but do not send it.
```

中文：厨房水槽从昨晚开始漏水，写一封礼貌的英文报修邮件，在聊天里展示完整草稿，不要发送。

继续输入：

```text
Make it more concise, while keeping the fact that the sink has been leaking since last night.
```

中文：改简短一些，但保留从昨晚开始漏水的事实。

### 2. 保存报修并记录回复

依次点击：

1. 最新草稿的 **Copy email draft**。
2. **Save to Aftercare**。
3. 弹窗中的 **Confirm and save aftercare details**。
4. **Aftercare services → Repairs**，打开刚保存的报修记录。

返回同一聊天，输入：

```text
The property manager replied that a plumber will contact me tomorrow. Add this note to the existing kitchen sink repair. Do not create a second repair request.
```

中文：物业经理说水管工明天会联系我，把这条备注加到现有报修，不要重复创建。

按界面确认保存，再回 **Repairs** 查看。

### 3. 创建退租计划

1. 打开 **Aftercare services → Move-out plan**。
2. 根据页面需要，完成 **Complete lease details**：导入可用资料并核对，补充房间等必填信息，勾选确认。
3. 点击 **Confirm details and create aftercare case**；已有租后案例时使用相应保存按钮。
4. 输入模拟退租日期 **2027-11-15**。
5. 点击 **Generate and confirm plan**。

### 4. 提交人工审核，并在审核页找到记录

1. 对一个退租任务点击 **Edit task**。
2. 勾选 **Human review needed**。
3. 输入审核原因：

```text
The wall marks were already present when I moved in. Please compare the entry condition record and the move-out photos before I prepare a response to the proposed deduction.
```

中文：墙面痕迹在入住时就存在，请先比较入住检查记录与退租照片，再让我准备对扣款的回复。

4. **Save task**。
5. 打开左侧 **Human review**。
6. 输入本地操作员密钥，点击 **Load review records**，按主案例编号找到刚提交的事项。
7. 选择 **Defer · Retain restrictions**，在 **Human review notes** 填入：

```text
Please provide the entry condition record and dated photos. Review remains pending until the evidence is available.
```

中文：请补充入住检查记录及带日期的照片，证据齐全前保持待审核。

8. 点击该事项的 **Record selected review decision**，在弹窗点击 **Confirm record**。
9. 刷新后重新加载审核记录。

### 5. 可选：水电网与押金

**网络服务商输入：**

```text
I need an internet service for my rental in Sydney. Show me provider information and explain which prices and address-specific details I should confirm before choosing a plan.
```

中文：展示悉尼出租屋的网络服务商信息，以及选套餐前需要确认的价格和地址相关信息。

点击 **Aftercare services → Utilities**，打开一家服务商的详情。

**押金跟进输入：**

```text
My bond is held through Rental Bonds Online. I have returned the keys and am waiting for the refund. What facts and reference details should I record to track the follow-up?
```

中文：押金存在 Rental Bonds Online，已还钥匙并等待退款，需要记录哪些事实和编号来跟进？

点击 **Aftercare services → Bond follow-up**，按页面填写模拟编号和事实，再完成相应确认。
