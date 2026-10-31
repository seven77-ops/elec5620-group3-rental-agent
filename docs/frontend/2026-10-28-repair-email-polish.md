# Agent4 报修邮件润色交接

日常报修页面已接入真实 AI 润色；聊天页顶部“润色报修邮件”直达该页面。原稿可为中文或英文，收件人姓名可修改或留空。默认生成英文、礼貌语气，可改为中文、正式或简洁。标题可在润色前留空；保存时自动采用已核对的邮件主题。

## 流程与边界

- 点击“AI 润色邮件”调用 `POST /api/v1/cases/{case_id}/living-services/repair-email/polish`，使用当前配置的 `ModelProvider`，任务为 `repair_email_polish`。
- 仅发送表单里的原稿、称呼、标题、位置、优先级与语言/语气。界面注明 AI 处理；不携带合同、历史聊天、邮箱或附件。
- 生成主题/正文可编辑和复制。生成本身不创建报修记录，也不更改租后资料版本。
- “保存润色报修草稿”展示核对确认，再通过已有版本化报修 API 保存。`email_draft` 保留用户审定内容；`description` 保留原始问题。状态始终为 `prepared_not_sent`，没有发信调用。
- API 重试按案例和请求 ID 回放，拒绝同 ID 不同输入；格式错误或 AI 失败可重试。页面保留原稿和上次手工编辑结果，输入修改后提示重新润色或手工同步。
- 原有普通模板报修和紧急维修提示保留。已使用自定义润色稿的记录不再显示固定模板语气切换，避免无效调整；状态及后续记录仍可保存。

## 文件

- `server/app/living/email_ai.py`：验证、AI 生成、严格输出及请求回执。
- `server/app/living/fields.py` / `repairs.py`：自定义邮件校验与原文保存。
- `frontend/src/features/living/RepairComposer.tsx`：原稿、润色、编辑、复制和确认保存。
- `frontend/src/features/living/Repairs.tsx` / `RepairFollowup.tsx`：记录列表与原有后续操作。
- `frontend/src/api/living.ts`：输入/输出类型和润色 API。
- 聊天页新增直达入口；自然语言报修的原有模板流程保留。

## 验证（2026-10-28）

- 45 条后端测试通过：新邮件 AI、租后服务、聊天及连续跟进、模型传输。
- 15 条浏览器测试通过：3 条新润色用例和 12 条租后服务/租约资料回归。涵盖无标题生成、原稿与姓名传递、编辑保存并刷新回读、失败保留、请求重试、390px 页面和聊天入口。
- 32 条前端单元测试、TypeScript/Vite 构建和本次 TS/TSX 文件格式检查通过。构建仅保留既有 vendor chunk 体积提示。
- 实际 `qwen-plus` 合成原稿调用成功，耗时约 6.7 秒，生成给 Alex 的英文维修请求；无模拟标识、无邮件发送、无用户案例修改。
- 修正一条旧租约导入回归断言，匹配现有“资料已更新”友好提示；未修改租约导入产品逻辑。
- 本地服务 `5191` / API `8011` 已重载；健康检查及 OpenAPI 路由存在。重启前后真实运行库的 168 个对象数量及 SHA256 摘要一致。

测试截图：`/tmp/repair-email-desktop.png`、`/tmp/repair-email-mobile.png`。真实模型合成测试结果：`/tmp/repair-email-real-ai.json`。所有写入验证使用临时数据库。
