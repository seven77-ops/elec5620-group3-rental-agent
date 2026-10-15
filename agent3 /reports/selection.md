# Agent 3 · Rental agreement review

- Review ID: `cr-21ba9a7986464293bec267f23b93350c` · version 1
- Status: **Reviewed**
- Reference date: 2026-10-15
- Document: selection-demo.txt
- NSW reference pack: NSW-reference-2026-10-15
- Explanation mode: rules

This is an informational course prototype. Verify the original agreement; it is not legal advice.

## Extracted fields

| Field | Value | Confidence | Source |
|---|---|---:|---|
| address | 虚构示例楼 6 号房（不存在的地址） | 0.90 | selection-demo.txt p.1 line 4 — Address: 虚构示例楼 6 号房（不存在的地址） |
| landlord | Example Housing Pty Ltd | 0.90 | selection-demo.txt p.1 line 2 — Landlord: Example Housing Pty Ltd |
| tenant | Alex Student | 0.90 | selection-demo.txt p.1 line 3 — Tenant: Alex Student |
| rent_amount | 500.0 | 0.90 | selection-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| rent_period | week | 0.90 | selection-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| rent_scope | per_person | 0.90 | selection-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| currency | AUD | 0.80 | selection-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| bond | 2000.0 | 0.90 | selection-demo.txt p.1 line 6 — Bond: $2000 |
| start_date | 2027-02-01 | 0.90 | selection-demo.txt p.1 line 7 — Start date: 2027-02-01 |
| end_date | 2028-01-31 | 0.90 | selection-demo.txt p.1 line 8 — End date: 2028-01-31 |
| signed_date | 2026-10-15 | 0.90 | selection-demo.txt p.1 line 9 — Date signed: 2026-10-15 |

## Additional clauses located

- Special condition: Tenant and landlord should check the original agreement for the full wording. (selection-demo.txt, page 1)

## Findings

No checklist findings. This does not certify compliance.

## Evidence-linked explanations

No explanation released for the current status.

## Tenant questions (UC06)

No questions generated or no findings require clarification.

## Data limitations

- Course prototype: informational checklist, not legal advice.
- Field extraction is narrow; verify all values against the original agreement.
- 全部房源、路线、设施和证据均为模拟数据，不可用于真实租房决策。
- 本原型仅为 Agent 2 的确定性工具核心，未接入 LLM、房源平台或 TfNSW。
- as_of 是输入快照时点，不代表今天仍可租；分数是偏好匹配，不是房屋安全或签约保证。
- 不支持自动换汇、按人数分摊、真实市场租金估值或未来班次保证。
- user_confirmed 是调用方显式声明，不是用户鉴权或签名；本地原型未发送数据给 Agent 3。
- 来源事实和时效检查基于提供的模拟快照，不等于已实地验证房源真实或已重新联系供方。
