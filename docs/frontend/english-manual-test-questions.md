# Rental Assistant — Manual Test Questions / 租房助手手动测试问题

Use these English prompts to test the English product through its normal interface.
These are test inputs and expected behaviours, not a record of completed tests.

**中文说明：** 请通过正常界面使用下方英文问题测试英文版产品。本文列出的是测试输入和预期表现，并不表示这些测试已经执行完成。英文代码块用于复制测试，中文翻译用于理解；E02 专门测试混合语言输入。

## Before you start / 测试前准备

- Open the local website: <http://127.0.0.1:5191>.
  中文：打开本地网站：<http://127.0.0.1:5191>。
- Use a new case for each section. Keep the same conversation for follow-up questions within that section.
  中文：每一节使用一个新案例；同一节中的追问应在同一个对话中继续。
- Use synthetic information and the sample contract below.
  中文：使用虚构测试信息和下方模拟合同。
- Enable external AI only when you want to test AI generation. Contract upload, private search and cloud processing have separate consent controls.
  中文：需要测试 AI 生成时再开启外部 AI。合同上传、私有检索和云端处理分别需要相应授权。
- Where available, inspect routing/call details. A helpful answer alone does not prove Jev handled the request; check the recorded routing source and route.
  中文：如界面提供路由或调用详情，请检查记录的路由来源和目标。仅凭回答看起来合理，不能确认请求确实经过 Jev。
- For each test, record **Pass / Fail**, the case ID, actual behaviour and a screenshot if it fails.
  中文：每项记录“通过／失败”、案例 ID 和实际表现；失败时附上截图。

If you only have ten minutes, start with **H01, R01–R03, C01–C04 and M01**.

**中文说明：** 如果只有十分钟，优先测试 **H01、R01–R03、C01–C04 和 M01**。

## 1. Housing requirements and recommendations / 租房需求与房源推荐

### H01 — A complete housing request / 完整的找房需求

```text
I am a University of Sydney student studying at the Camperdown/Darlington main campus. I need a whole property for one person, with at least one bedroom and one bathroom. My maximum budget is AUD 700 per week for the whole property. I do not need parking. I am open to different suburbs, but I want a public transport commute of no more than 40 minutes. Please help me find matching properties.
```

**中文翻译：**

> 我是悉尼大学 Camperdown／Darlington 主校区的学生。我想一个人整租，至少需要一间卧室和一间浴室。整套房子的最高预算是每周 700 澳元，不需要车位。我可以考虑不同区域，但希望公共交通单程通勤不超过 40 分钟。请帮我找符合条件的房源。

**Check:** The assistant understands the budget period, pricing scope, occupants, room minimums and commute ceiling. Review and confirm any proposed requirements. Results distinguish advertised facts from unverified availability and missing commute evidence.

**检查要点（中文）：** 助手正确理解预算周期、计价范围、入住人数、最低房间数和通勤上限。检查并确认提出的需求。结果应区分广告信息、尚未核实的可租状态和缺失的通勤证据。

### H02 — Change one requirement without losing the rest / 只修改一个条件，保留其他条件

After H01:

**中文说明：** 完成 H01 后，在同一个对话中继续：

```text
Change only my maximum budget to AUD 650 per week. Keep all my other confirmed requirements unchanged.
```

**中文翻译：**

> 只把我的最高预算改为每周 650 澳元，其他已经确认的需求都保持不变。

**Check:** The proposed budget changes to 650. Occupants, room minimums, rental type and commute criteria remain unchanged. Any save still follows the displayed confirmation flow.

**检查要点（中文）：** 拟修改的预算变为 650 澳元；入住人数、最低房间数、租赁方式和通勤条件保持不变。保存仍需按界面的确认流程完成。

### H03 — Ask for another set of results / 更换一批推荐结果

After confirming the housing requirements:

**中文说明：** 确认找房需求后继续：

```text
Keep all my confirmed requirements and show another set of recommendations, prioritising properties I have not seen before.
```

**中文翻译：**

> 保持我所有已经确认的需求，换一批推荐，优先展示我之前没有看过的房源。

**Check:** The assistant preserves the filters. It does not increase the budget or commute limit to produce more results. If there are no additional matches, it says so.

**检查要点（中文）：** 筛选条件保持不变，不能为了增加结果而提高预算或通勤上限。没有更多符合条件的房源时，应明确说明。

### H04 — Compare selected properties / 对比已选中的房源

**Setup:** Display results and select two property cards for comparison. Use the chat's comparison control so the selected property IDs accompany the request.

**中文说明：** 先展示房源结果并选中两张房源卡片。通过聊天中的对比控件发起请求，使所选房源 ID 随请求一起提交。

```text
Compare the two properties I selected. Focus on advertised weekly rent, bedrooms, bathrooms and public transport commute. Tell me which facts still need confirmation.
```

**中文翻译：**

> 请对比我选中的这两套房源，重点比较广告周租、卧室、浴室和公共交通通勤。告诉我还有哪些信息需要确认。

**Check:** The comparison refers to those two properties and their actual displayed facts. It does not invent availability, exact commute times or a claim that either property is safe or approved.

**检查要点（中文）：** 对比对象是实际选中的这两套房源，所用信息与展示内容一致。不编造可租状态、精确通勤时间，也不宣称房源安全或已经获得批准。

### H05 — No matching properties / 没有符合条件的房源

Use a separate test case:

**中文说明：** 使用一个单独的新测试案例：

```text
I need a whole property with at least five bedrooms and five bathrooms, for no more than AUD 1 per week. I do not want you to relax any of these requirements automatically.
```

**中文翻译：**

> 我需要整租一套至少有五间卧室和五间浴室的房子，每周租金不能超过 1 澳元。不要自动放宽任何条件。

**Check:** The assistant reports no matches in the available catalogue, or asks for necessary clarification. It may suggest changes, but does not silently apply them or claim that no suitable property exists anywhere in the market.

**检查要点（中文）：** 说明当前房源库中没有匹配项，或进行必要的澄清。可以建议修改条件，但不能偷偷应用，也不能据此断言整个市场都没有合适房源。

## 2. Repair email in chat / 聊天内报修邮件

### R01 — Generate a natural English draft directly in chat / 直接在聊天中生成自然的英文邮件草稿

```text
The kitchen sink has been leaking since last night. Please prepare a polite repair email in English asking the property manager to arrange an inspection and repair. Only prepare the draft; do not send it.
```

**中文翻译：**

> 厨房水槽从昨晚开始漏水。请帮我写一封礼貌的英文报修邮件，请物业经理安排检查和维修。只准备草稿，不要发送。

**Check:** The subject and full email body appear in chat. The email reads like correspondence, rather than a list of form fields. It retains the issue and timing. Missing contact details do not block drafting; the assistant does not invent a recipient or claim the email was sent.

**检查要点（中文）：** 聊天中直接展示主题和完整邮件正文。内容应像自然的邮件，而不是表单字段清单；保留问题和发生时间。缺少联系方式不应阻止生成草稿，不能编造收件人或声称邮件已发送。

### R02 — Rewrite the same draft / 修改同一封草稿

After R01:

**中文说明：** 完成 R01 后，在同一个对话中继续：

```text
Make this email shorter while keeping a polite tone. Keep the fact that the kitchen sink has been leaking since last night.
```

**中文翻译：**

> 请把这封邮件写得更简短一些，同时保持礼貌。保留“厨房水槽从昨晚开始漏水”这一事实。

**Check:** The revised email appears in chat, retains the facts and can be copied. It remains associated with the same repair issue.

**检查要点（中文）：** 修改后的邮件直接显示在聊天中，保留事实并可以复制，仍对应同一个报修事项。

### R03 — Save the exact preview / 保存与预览完全一致的草稿

**Action test:** Copy the latest preview for comparison. Click **Save to Aftercare**, review the confirmation and confirm saving. Open **Aftercare services → Repairs**.

**中文说明：** 先复制最新预览以便核对。点击 **Save to Aftercare（保存到租后服务）**，检查确认内容并确认保存，再打开 **Aftercare services → Repairs（租后服务 → 报修）**。

**Check:** One repair record contains the exact latest preview. Its status indicates preparation rather than delivery. Refresh the page and check that the record persists.

**检查要点（中文）：** 只产生一条报修记录，正文与最新预览完全一致；状态表示草稿已准备，而不是已经送达。刷新后记录仍存在。

### R04 — Record a reply without contacting anyone / 记录回复，不联系任何人

After R03:

**中文说明：** 完成 R03 后，在同一个对话中继续：

```text
The property manager replied that a plumber will contact me tomorrow. Please record this as a follow-up on the existing kitchen sink repair. Do not create another repair request.
```

**中文翻译：**

> 物业经理回复说，水管工明天会联系我。请把这条回复记录到现有的厨房水槽报修事项中，不要新建另一条报修。

**Check:** Review and confirm the proposed update where required. The note belongs to the existing repair. The application does not claim that it contacted the plumber or independently confirmed a booking.

**检查要点（中文）：** 按需要检查并确认更新。这条回复应归入原有报修记录；应用不能声称已经联系水管工，或独立确认了预约。

## 3. Contract upload and private retrieval / 合同上传与私有检索

### Synthetic contract for this section / 本节使用的模拟合同

Copy the following into a local file named `sample-test-contract.txt`. It is a test fixture, not a complete tenancy agreement.

**中文说明：** 将下方英文样本复制到本地文件 `sample-test-contract.txt` 中。该文件仅用于测试，不是完整租赁合同。中文译文仅供阅读，上传时使用英文样本。

```text
SYNTHETIC TEST DOCUMENT — NOT FOR SIGNING
Property address: 1 Example Street, Sydney NSW 2000
Landlord: Example Landlord
Tenant: Example Tenant
Rent: AUD 650 per week for the whole property
Bond: AUD 2600
Start date: 2026-11-01
End date: 2027-11-01

6. Cleaning
The tenant must leave the premises reasonably clean, except for fair wear and tear.

7. Repairs
The tenant should report maintenance issues to the landlord or agent in writing.
```

**中文参考译文（仅供阅读，上传使用上方英文样本）：**

> 模拟测试文档——不可用于签署
> 房屋地址：1 Example Street, Sydney NSW 2000
> 房东：Example Landlord
> 租客：Example Tenant
> 租金：整套房屋每周 650 澳元
> 押金：2600 澳元
> 起租日期：2026-11-01
> 结束日期：2027-11-01
>
> 6. 清洁
> 租客应在退租时使房屋保持合理清洁，但正常损耗除外。
>
> 7. 维修
> 租客应以书面方式向房东或中介报告维修问题。

### C01 — Start a review without selecting a property / 未选房时开始合同审核

In a new case with no selected property:

**中文说明：** 在尚未选定房源的新案例中输入：

```text
I already have a rental contract. I want to check the rent, bond and special terms. Please let me upload it for review without selecting a property first.
```

**中文翻译：**

> 我已经有一份租赁合同，想检查租金、押金和特殊条款。请让我直接上传合同审核，不要要求我先选房。

**Action:** Complete the document-processing consent, choose the sample file, confirm upload authority and select **Upload and review**.

**中文说明：** 完成文档处理授权，选择模拟合同文件，确认自己有权提交该文档，然后点击 **Upload and review（上传并审核）**。

**Check:** The upload/review flow is available without a housing selection. The result shows extracted facts, original evidence and incomplete or uncertain items. It does not create a selected property or certify the document as legally valid.

**检查要点（中文）：** 未选房时仍可上传并审核。结果包含提取字段、原文证据及缺失或不确定事项。不能自动创建已选房源，也不能认证合同合法有效。

### C02 — Retrieve rent and bond with citations / 检索租金和押金，并引用原文

**Setup:** Enable private search for the current review version. To test an AI answer, separately permit cloud processing and per-question AI use. Enter this in the contract question field:

**中文说明：** 为当前审核版本启用私有检索。测试 AI 回答时，还需分别允许云端处理及本次问题使用 AI。将下方问题输入合同问答框：

```text
What are the rent and bond amounts in this contract? Please cite the original wording.
```

**中文翻译：**

> 这份合同中的租金和押金分别是多少？请引用原文。

**Check:** The sources support **AUD 650 per week for the whole property** and **AUD 2600 bond**. An AI summary, when enabled, is English and includes private-contract citations. With local search only, inspect the original excerpts instead.

**检查要点（中文）：** 原文支持“整套每周 650 澳元”和“押金 2600 澳元”。启用 AI 时，摘要为英文并附私有合同引用；仅使用本地检索时，应检查原文片段。

### C03 — Explain a clause rather than inventing a rule / 解释条款，不编造规则

In the same private contract Q&A:

**中文说明：** 在同一个私有合同问答区域中继续：

```text
What does the cleaning clause say about fair wear and tear? Quote the relevant contract text and explain it in plain English.
```

**中文翻译：**

> 清洁条款是如何规定正常损耗的？请引用相关合同原文，并用通俗的英文解释。

**Check:** The response cites clause 6 and preserves the fair-wear-and-tear exception. It distinguishes the document's wording from a separate legal assessment.

**检查要点（中文）：** 回答引用第 6 条，并保留正常损耗的例外；应区分合同原文的含义与另外的法律判断。

### C04 — Ask about information absent from the document / 询问合同中没有的信息

```text
Does this contract allow me to keep a cat? Show me the clause that answers this.
```

**中文翻译：**

> 这份合同允许我养猫吗？请指出能够回答这个问题的条款。

**Check:** The sample document contains no pet clause. The assistant identifies the missing evidence instead of inventing permission, a prohibition or a clause number.

**检查要点（中文）：** 模拟合同没有宠物条款。助手应指出缺少依据，不能编造允许、禁止或条款编号。

### C05 — Remove private search permission / 撤销私有检索权限

**Action test:** Choose **Delete contract search index**. Try C02 again without re-enabling search.

**中文说明：** 点击 **Delete contract search index（删除合同检索索引）**。不重新启用检索，再尝试 C02。

**Check:** The private search index is no longer usable until the required consent/indexing flow is completed again. The assistant does not present an old private answer as a fresh search. Previously saved review records may still exist.

**检查要点（中文）：** 在重新完成必要授权和建索引流程之前，私有索引不可再使用。不能把旧的私有回答当成一次新检索结果展示；此前保存的审核记录可能仍然存在。

## 4. Public knowledge retrieval / 公共知识检索

### K01 — General repair guidance / 一般报修指引

Use a new conversation without a private-contract question pending:

**中文说明：** 新建一个对话，确保当前没有待处理的私有合同问题：

```text
How should I report a non-urgent repair to my landlord or agent in NSW? Please use official sources and show the citations.
```

**中文翻译：**

> 在新南威尔士州，我应该如何向房东或中介报告非紧急维修？请使用官方来源，并展示引用。

**Check:** The answer is English and supported by relevant public source excerpts. Open the citations and compare the material claims and conditions with their sources. This question must not create a repair record or send an email.

**检查要点（中文）：** 回答为英文，且有相关公共来源片段支持。打开引用，核对主要结论和条件。本问题不能创建报修记录或发送邮件。

### K02 — Product help / 产品使用帮助

```text
What is the difference between saving a property to My favorites and selecting it for follow-up? Does either action submit a rental application?
```

**中文翻译：**

> 把房源保存到 My favorites（我的收藏）与选定房源继续跟进有什么区别？这两个操作中的任何一个会提交租房申请吗？

**Check:** Product help explains the two saved states and the optional comparison flow. Neither action is represented as submitting an application or contacting the advertiser.

**检查要点（中文）：** 说明收藏、选定跟进这两种保存状态，以及可选的对比流程。两个操作都不能被描述为提交租房申请或联系广告发布方。

### K03 — Unsupported personal prediction / 缺少依据时不保证个人结果

```text
Can you guarantee that I will get my full bond back? I have not uploaded any evidence or told you whether there are deductions.
```

**中文翻译：**

> 你能保证我拿回全部押金吗？我还没有上传任何证据，也没有告诉你是否有扣款。

**Check:** The assistant does not guarantee an outcome or invent case facts. It explains what information is missing and uses sources for any general guidance.

**检查要点（中文）：** 不能保证结果或编造案例事实。应说明缺少哪些信息；涉及一般指引时提供来源。

## 5. Bond tracking and human review / 押金跟进与人工审核

### B01 — Bond held on an official platform / 押金存放在官方平台

```text
My bond of AUD 2600 is held through Rental Bonds Online. I have returned the keys and I am waiting for the refund. What information do I need to record so I can track the follow-up in this app?
```

**中文翻译：**

> 我的 2600 澳元押金存放在 Rental Bonds Online。我已经归还钥匙，正在等待退款。我需要记录哪些信息，才能在这个应用里跟进进度？

**Check:** The assistant treats the app as a record/follow-up tool. It may guide you to tenancy details, a bond reference, dated facts and evidence. It does not claim to hold the funds, check an official account automatically or submit a refund application. Complete any record-creation/activation steps through the displayed confirmation flow.

**检查要点（中文）：** 将本应用作为记录和跟进工具，可引导补充租约资料、押金编号、带日期的事实和证据。不能声称保管资金、自动查询官方账户或提交退款申请。创建和启用记录需完成界面确认。

### B02 — Bond reported as held by the landlord / 用户称押金由房东持有

Use a separate case:

**中文说明：** 使用一个单独的新案例：

```text
My landlord says they are holding my bond directly. I do not have a Rental Bonds Online reference. Can you help me record what I know and identify what evidence I should check?
```

**中文翻译：**

> 房东说押金直接由他持有，我没有 Rental Bonds Online 的编号。你能帮我记录已经知道的情况，并告诉我应该核查哪些证据吗？

**Check:** The assistant does not invent a government bond reference or assume the money is held by this app. Missing evidence stays unresolved; any general process advice needs appropriate sources.

**检查要点（中文）：** 不能编造官方押金编号，也不能假设钱存在本应用中。缺失证据应保持未解决状态；一般流程建议需要适当来源。

### M01 — Submit a real human-review item and find it in the inbox / 提交人工审核事项，并在收件箱中找到记录

**Setup and actions:**

**中文说明：** 准备与操作步骤：

1. In **Aftercare services**, complete and confirm synthetic tenancy information and create a **Move-out plan**.
   中文：在 **Aftercare services（租后服务）** 中填写并确认模拟租约信息，创建 **Move-out plan（退租计划）**。
2. Open a task using **Edit task**. Select **Human review needed**.
   中文：点击 **Edit task（编辑任务）** 打开一个任务，勾选 **Human review needed（需要人工审核）**。
3. Enter this reason and save the task:
   中文：输入下方审核原因并保存任务：

```text
The wall marks were already present when I moved in. Please compare the entry condition record with the move-out photos before I prepare a response to the proposed deduction.
```

**中文翻译：**

> 墙面的痕迹在我入住时就已经存在。请先比较入住检查记录与退租照片，再让我准备针对这笔拟议扣款的回复。

4. Open **Human review**. Enter your local operator key and select **Load review records**. Use the configured local key; do not paste it into chat or this document.
   中文：打开 **Human review（人工审核）**，输入本地操作员密钥，点击 **Load review records（加载审核记录）**。使用实际配置的本地密钥，不要把密钥粘贴到聊天或本文档中。
5. Find the submission by its case ID and reason.
   中文：根据案例 ID 和审核原因找到刚提交的事项。
6. Record **Defer · Retain restrictions**, with this note:
   中文：选择并记录 **Defer · Retain restrictions（暂缓处理，保留限制）**，填写下方备注：

```text
Please provide the entry condition record and dated photos. Review remains pending until the evidence is available.
```

**中文翻译：**

> 请补充入住检查记录和带日期的照片。在证据齐全前，审核保持待处理状态。

7. For the synthetic review exercise, inspect the supplied evidence and then record **Checked · Allow draft preparation**, with this note:
   中文：在本次模拟审核练习中，检查提供的证据后，选择并记录 **Checked · Allow draft preparation（已核查，允许准备草稿）**，填写下方备注：

```text
The supplied entry record and dated photos have been checked. The tenant may continue preparing a factual enquiry draft. No deduction or refund outcome has been determined.
```

**中文翻译：**

> 已核查提供的入住记录和带日期的照片。租客可以继续准备事实询问草稿。目前尚未决定任何扣款或退款结果。

8. Refresh, reload the review records and inspect the history. Switch to another case and verify that the operator inbox can still locate the original submission.
   中文：刷新页面并重新加载审核记录，检查历史。切换到另一个案例，确认操作员收件箱仍能找到原案例的提交事项。

**Check:** A saved submission appears in the inbox with the correct case, reason and source task. Both decisions and notes persist. Deferral retains restrictions; checking permits the supported draft workflow. A review decision does not transfer money, approve a deduction, determine legal rights or contact an external organisation.

**检查要点（中文）：** 保存的事项出现在收件箱中，关联正确的案例、原因和来源任务。两次决定及备注都应持久保存。暂缓保留限制，核查通过后允许支持的草稿流程。审核决定不转移资金、不批准扣款、不裁定法律权利，也不联系外部机构。

## 6. Services and English output / 服务信息与英文输出

### U01 — Provider research without booking / 查看服务商信息，不进行预订

```text
I need an internet service for my rental in Sydney. Show me available provider information and explain which prices or address-specific details I still need to confirm before choosing a plan.
```

**中文翻译：**

> 我需要为悉尼的出租屋办理网络服务。请展示可查看的服务商信息，并说明选择套餐前，还需要确认哪些价格或与具体地址有关的信息。

**Check:** Provider information, sources and uncertainty are visible in English. Saving a provider choice does not open an account, switch a service or make a booking.

**检查要点（中文）：** 服务商资料、来源和不确定信息均以英文显示。保存服务商选择不会开户、切换服务或预约。

### E01 — Preserve a supplied name inside an English email / 英文邮件保留用户提供的姓名

```text
My name is 张三. The kitchen sink has been leaking since last night. Please draft a polite repair email in English and keep my name exactly as written. Do not send it.
```

**中文翻译：**

> 我叫张三。厨房水槽从昨晚开始漏水。请写一封礼貌的英文报修邮件，保留我的姓名原样。不要发送。

**Check:** The generated subject and prose are English. The supplied name remains `张三`; it is not replaced with an invented English name. The draft is visible in chat.

**检查要点（中文）：** 主题和正文使用英文；用户姓名“张三”保持原样，不能替换成编造的英文名。草稿直接出现在聊天中。

### E02 — Mixed-language input still produces English output / 中英文混合输入，仍使用英文输出

```text
厨房水槽从昨晚开始漏水。Please prepare a polite repair email. 只准备草稿，不要发送。
```

**中文翻译：**

> 厨房水槽从昨晚开始漏水。请准备一封礼貌的报修邮件。只准备草稿，不要发送。

**Check:** The assistant understands the issue and timing, but its new explanation and email are English. The original user message remains unchanged. No email is sent.

**检查要点（中文）：** 理解问题和发生时间，但新生成的说明及邮件仍为英文。用户原始消息保持不变，不发送邮件。

## Result log / 测试结果记录

| Test ID / 测试编号 | Pass / Fail / 通过或失败 | Case ID / 案例编号 | Actual result / evidence / 实际结果与证据 |
| --- | --- | --- | --- |
| H01 | | | |
| H02 | | | |
| H03 | | | |
| H04 | | | |
| H05 | | | |
| R01 | | | |
| R02 | | | |
| R03 | | | |
| R04 | | | |
| C01 | | | |
| C02 | | | |
| C03 | | | |
| C04 | | | |
| C05 | | | |
| K01 | | | |
| K02 | | | |
| K03 | | | |
| B01 | | | |
| B02 | | | |
| M01 | | | |
| U01 | | | |
| E01 | | | |
| E02 | | | |
