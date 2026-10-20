# Agent 2 / Agent 3 与前端 AI 接入方案（本地核对版）

日期：2026-10-20（Australia/Sydney）。用户已授权先写方案，再在本地实现；本轮不推送、不创建/更新 PR、不更新 Jira，先供 Agent 3 同学核对。

## 基线与现状

- 基于 GitHub 前端分支 `origin/codex/frontend-demo` 的 `2e375bb`；本地开发分支 `codex/local-ai-integration`。
- GitHub main 为 `4701fa1`；其 Agent 3 与本地基线的目录树指纹均为 `60d469b2ab24986124d4f4d5fc275a3ff09b944f`，使用的是已发布的原 Agent 3 代码，不引入其他成员未合并分支。
- 保留已接入的真实 Agent 1 偏好服务、Agent 2 规则评分和 Agent 4 租后流程。
- 原 Agent 3 可选模型网关仅解释既有发现；本轮新增有原文校验的候选提取与预览分析，复用原规则和修正入口，既有 CLI 默认行为与 ContractReview Schema 保持兼容。

## 功能与职责

### Agent 3：提取与解释一起做

用户完成合同处理同意并上传合成文件，获得原规则复核后，可另行同意将合同文本发送到配置的模型，点击“AI 辅助分析合同”。模型提取 address / rent_amount / start_date / end_date，另允许 rent_period / rent_scope / currency 支撑可比租金核对。每个非空候选必须附原文行号与逐字引文；金额为有限正数、日期为有效 ISO 日期、枚举必须在既有允许范围内。服务端按保存的合同校验，不信任模型提供的来源名、页码或权限。

结果按“模型候选 → 原文引用 → 与选房包的确定性差异 → 风险解释”显示。未知/不可信候选标为待确认，不自动使用。用原 correct_review 生成内存预览并调用原规则生成发现；解释仅接受预览中已有 finding_id。无发现时不编造解释，也不声称调用了不存在的解释请求。

候选分析保存在外层 AI sidecar，不修改原 ContractReview。用户勾选已核对字段，再明确确认应用，才调用原修正逻辑产生新版本、使旧问题失效并保留历史；原人工审核门禁不会被模型解除。应用必须绑定原复核完整指纹（不仅数字版本）、文件指纹、当前选房和有效同意；过期结果可读但不能应用。

### Agent 2：推荐解读

在现有报告上点击“生成推荐解读”，用户确认外部模型处理范围后，将已保存 Top 5 的分数、分项分数、理由、取舍和证据引用发送到模型；不用合同正文。输出必须严格对应当前合格推荐的 listing_id，并只引用已提供的 source_ref；零匹配不调用模型。输出独立保存，不能改变资格、分数、排名、选房包或确认版本。解读为辅助文字，仍需对照原证据。

### 前端

沿用现有布局，增加推荐解读卡和合同 AI 分析卡，均有独立勾选同意、提交 loading、失败提示、原请求重试、历史结果恢复和“本次 AI 调用”详情。详情显示真实模型名、任务、时间、耗时、状态，以及服务实际返回的用量/请求 ID；没有返回就不补造。测试替身必须显著标为 test_stub，不冒充真实调用。

## API 与数据约定

基路径 `/api/v1`；沿用 `{error:{code,message,request_id,fields?}}` 错误格式。

- `GET /ai/config` → `{enabled,configured,provider,model,timeout_seconds}`，不含 endpoint、key。
- `POST /evaluations/{run_id}/ai-explanations` 请求 `{request_id,allow_external_ai:true}`。
- `GET /evaluations/{run_id}/ai-explanations/latest` → 最近一次结果或 null。
- `POST /contract-reviews/{review_id}/ai-analyses` 请求 `{request_id,expected_version,allow_external_ai:true}`。
- `GET /contract-reviews/{review_id}/ai-analyses/latest` → 最近一次结果或 null，附当前 `can_apply`。
- `POST /contract-reviews/{review_id}/ai-analyses/{analysis_id}/apply` 请求 `{request_id,expected_version,confirmed:true,fields:[字段名]}`，返回 `{review,analysis_id}`。

AI 结果 envelope：`{analysis_id,kind,status,created_at,binding,result,calls,error?,can_apply?}`。status 为 success / partial / failed / skipped / stale；binding 为服务端保存的 case/run/review/version/内容指纹关联。每项 calls 记录 task/provider/model/status/started_at/duration_ms，可选 usage / provider_request_id / provider_response_id / error_code。未配置时写明 not_configured 且没有伪造 provider 请求；拒绝同意时零调用。

外部网络请求在 SQLite 写事务之外执行。先保存原请求与 pending reservation，相同逻辑请求重试返回原结果，变更输入冲突；并发重复请求提示进行中。调用后重新检查同意与上下文再保存可应用结果，期间发生撤销/变更则拒绝应用。崩溃遗留 reservation 可在超时后重试；不承诺外部服务在崩溃情况下严格只计费一次。

## 配置与失败处理

后端环境变量：`RENTAL_AI_ENABLED=1`、`RENTAL_AI_URL`（完整 HTTPS Chat Completions URL）、`RENTAL_AI_MODEL`、`RENTAL_AI_API_KEY`；`RENTAL_AI_TIMEOUT_SECONDS` 默认 12、上限 15。默认关闭。既有 AGENT3_MODEL_* 可作为兼容别名，配置说明明确优先顺序。启动脚本读取本地忽略的 `.env`，只接受白名单项，不执行文件内容；前端不保存密钥。

复用现有 OpenAI-compatible 消息协议，模型返回 JSON；不新增厂商 SDK。供应商待用户填写配置，不假设学校 Qwen 接口一定兼容。单次 HTTP 请求有超时/响应体大小限制、严格 JSON/非有限数校验、禁重定向，错误不会回传密钥、原始 provider 响应或合同正文。没有配置也能运行原规则流程。

本机尚未配置上述模型环境变量；可完成模块/API/UI 与受控测试，但真实外部模型成功必须等实际 API 配置后验证，不能把测试替身称为真实模型成功。

## 验证与交接

先写失败测试，再实现：候选类型/日期/金额/逐字引用、恶意引用、未知字段、评分不变、无同意零调用、配置缺失、超时/非法 JSON、并发/幂等、撤销/版本变化、手动确认应用与旧问题失效。跑原 Agent 1/2/3/4、服务端和集成测试，生产构建及真实接口下的页面流程。截图和日志区分规则、test_stub 与真实 provider。

交付包括本方案、配置样例、运行说明、测试结果和给 Agent 3 同学的核对清单。保留本地改动供核对，不上传。
