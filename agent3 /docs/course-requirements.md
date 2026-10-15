# M3 课程需求与实现追踪

第一阶段 M3（Zhang Chenyang）承担 FR05、FR06、OF03、SR02，对应 UC05 Review Rental Contract 和 UC06 Generate Contract Questions。这里记录可在本地验证的实现，不把规划中的团队/API 功能描述成已完成。

| 需求或流程 | 当前实现与验证 | 尚有限制 |
|---|---|---|
| UC05 合同接收与同意 | `document.load_document` 在读文件前检查同意；限制 TXT/DOCX/PDF、大小、PDF 页数；CLI 缺同意拒绝 | 无浏览器上传 UI；本地 OCR 依赖 `pdftoppm`/`tesseract` |
| FR05 字段、条款和出处 | `extract.extract_fields` 提取当事人、地址、租金/周期/范围、押金、日期、附加条款；保留页、行、引文及启发式置信度；租客可修正并产生新版本 | 正则只覆盖示例及常见标签，不保证复杂 NSW 标准合同完整提取 |
| FR06 版本化 NSW 参考检查 | `rules.evaluate_findings` 做押金四周参考检查、日期一致性、可比的房源差异；规则来源/版本随发现保存；过期进入 Degraded Summary Only | 不覆盖所有 NSW 租赁条款；不能作法律结论 |
| SR02 人工复核 | 高风险状态为 Awaiting Human Review，`approve_review` 记录人工决定、理由、时间及版本后才进入 Reviewed | CLI 中 reviewer 是声明字符串，尚无账户或角色鉴权 |
| 模型解释与质量检查 | 可选 HTTPS 模型网关；只允许引用现有 finding ID；不合格重试一次后确定性回退，模型不决定风险或状态 | 未接通/验证 Campus Qwen Proxy；结构校验不能证明自然语言句子无虚构 |
| OF03 / UC06 问题清单 | 仅 Reviewed 生成，问题保留 finding ID/证据/复核版本；可本地编辑、JSON/Markdown 导出，空发现返回空问题 | 不对外发送；没有网页编辑 UI |
| Agent 2 → Agent 3 / SCRUM-25 | 校验 `SelectedListingEvidence`；`receive` 要求同意和请求 ID，并保存选房批次/偏好版本/合同哈希绑定；SQLite 收据使本地重试返回原结果，冲突返回结构化错误；可比租金或地址冲突转人工复核 | 文件仍是 prepared_not_sent；无网络投递、身份鉴别或跨机器收件确认 |

第一阶段的理想状态机还包含更细的 `Uploaded → Validating → Parsing → OCR Pending → Extracting Fields → Resolving Rule Pack → Evaluating Rules → Generating Explanation → Quality Checking → Assessing Risk Severity` 内部步骤；此 CLI 保存可观察的结果/等待状态和事件，不逐条持久化每个内部瞬时状态。拒绝的上传以非零退出及原因返回，未保存 `Rejected` 报告对象。
