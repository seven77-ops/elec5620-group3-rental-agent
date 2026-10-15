# Agent 3 原型验证记录

日期：2026-10-15。环境：Python 3.12，本地合成演示数据。代码位于本仓库的 `agent3/`，依赖 `jsonschema` 与 `pypdf`；运行步骤见 [README](../README.md)。

## 已执行

| 验证 | 结果 |
|---|---|
| `python -m unittest discover -s tests -q`（从独立交付的 `outputs/agent3/`） | 25 项；24 通过、1 项同级 Agent 2 Schema 对比因独立交付而跳过；包括文字 PDF 解析和低精度地址冲突 |
| `python -m unittest discover -s tests -q`（从 `agent2/`） | Agent 2 原有 71 项通过 |
| Agent 2 CLI 使用 `DEMO-006` 现场生成 `.selection.json`，Agent 3 `receive` 使用新文件、合同和固定请求 ID | Agent 3 绑定 `DEMO-006` 与原始批次/偏好版本，结果 `Reviewed`；相同请求重试返回原复核 ID |
| Agent 2 上游 Schema 与 Agent 3 携带的契约快照字节比较 | 一致；SHA-256 `0516ce0296ad53ea5339a71d4c1eed913ea61d1b26ca8419f64e09e303e229b8` |
| Agent 3 CLI 高风险合同 → 人工决定 → 问题生成 | `Awaiting Human Review` → `Reviewed` → `Questions Ready`；`ContractQuestionList.handoff_status=prepared_not_sent` |
| 无同意、同名输出、无资格/身份/指纹不一致选房包、同请求 ID 不同内容、房源租金冲突、陈旧规则包、租金计价对象不一致、模型结构错误 | 单元/CLI 测试覆盖对应拒绝、人工复核、降级或回退路径 |

`agent3/reports/` 中的 JSON/Markdown 是合成样本报告；文件名按 Agent 2 的 `reports/` 习惯组织。报告的 UUID 和生成时间随运行改变，不能当作固定快照断言。

## 尚待团队联调

- 本地验证不等于跨进程消息已投递。Agent 2 的选房包与 Agent 3 的问题包都标记 `prepared_not_sent`；Agent 3 已有 SQLite 请求 ID 收据，但编排层仍需网络鉴权、跨机器共享存储和收件确认。
- 扫描 PDF 的 OCR 路径已有本地实现及模拟测试；本机尚未安装 `tesseract`，未用真实扫描件验证识别质量。普通文字 PDF 由 `pypdf` 读取。
- 可选模型端点只定义了 OpenAI-compatible HTTPS chat completions 适配形式；Campus Qwen Proxy 的协议、凭证和输出没有联调验证。模型失败会回退到规则说明。
- NSW 参考规则目前仅覆盖明确周租下的四周押金检查；其他条款需要补充已核实的规则、测试样本和人工审查。当前示例不构成法律结论。
- 未接入上传界面、业务数据库、真人操作员鉴权、M4 自动投递或真实合同。正式演示前应由团队补齐这些接口或明确展示本地原型范围。
