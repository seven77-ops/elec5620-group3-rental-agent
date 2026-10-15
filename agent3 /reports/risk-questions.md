# Agent 3 · Rental agreement review

- Review ID: `cr-447ec668f1e3449eb316f758dc9d0c21` · version 1
- Status: **Questions Ready**
- Reference date: 2026-10-15
- Document: risk-demo.txt
- NSW reference pack: NSW-reference-2026-10-15
- Explanation mode: rules

This is an informational course prototype. Verify the original agreement; it is not legal advice.

## Extracted fields

| Field | Value | Confidence | Source |
|---|---|---:|---|
| address | Different Example Building 9 | 0.90 | risk-demo.txt p.1 line 4 — Address: Different Example Building 9 |
| landlord | Example Housing Pty Ltd | 0.90 | risk-demo.txt p.1 line 2 — Landlord: Example Housing Pty Ltd |
| tenant | Alex Student | 0.90 | risk-demo.txt p.1 line 3 — Tenant: Alex Student |
| rent_amount | 500.0 | 0.90 | risk-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| rent_period | week | 0.90 | risk-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| rent_scope | per_person | 0.90 | risk-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| currency | AUD | 0.80 | risk-demo.txt p.1 line 5 — Weekly rent: $500 per person |
| bond | 2500.0 | 0.90 | risk-demo.txt p.1 line 6 — Bond: $2500 |
| start_date | 2027-02-01 | 0.90 | risk-demo.txt p.1 line 7 — Start date: 2027-02-01 |
| end_date | 2028-01-31 | 0.90 | risk-demo.txt p.1 line 8 — End date: 2028-01-31 |
| signed_date | unknown | 0.00 | not located |

## Additional clauses located

No labelled additional clauses located; inspect the original.

## Findings

- **F01 · high · Bond exceeds four weeks of rent** — The extracted bond exceeds four times the extracted weekly agreement rent; verify both values and seek qualified help if needed.
  - Rule reference: NSW-reference-2026-10-15 · https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/starting-a-residential-tenancy/signing-a-lease-and-moving
  - Evidence: Bond: $2500
  - Evidence: Weekly rent: $500 per person
- **F02 · high · Agreement and selected listing addresses differ** — The listing location may be less precise than the agreement; a human must confirm the actual premises.
  - Evidence: Address: Different Example Building 9
  - Evidence: listing_snapshot.address

## Human escalation

- Status: approved
- Reviewer note: Synthetic escalation path reviewed

## Evidence-linked explanations

- F01: The extracted bond exceeds four times the extracted weekly agreement rent; verify both values and seek qualified help if needed.
- F02: The listing location may be less precise than the agreement; a human must confirm the actual premises.

## Tenant questions (UC06)

- F01 · review v1: Could you clarify: Bond exceeds four weeks of rent? The extracted bond exceeds four times the extracted weekly agreement rent; verify both values and seek qualified help if needed.
- F02 · review v1: Could you clarify: Agreement and selected listing addresses differ? The listing location may be less precise than the agreement; a human must confirm the actual premises.

## Data limitations

- Course prototype: informational checklist, not legal advice.
- Field extraction is narrow; verify all values against the original agreement.
- 全部房源、路线、设施和证据均为模拟数据，不可用于真实租房决策。
- 本原型仅为 Agent 2 的确定性工具核心，未接入 LLM、房源平台或 TfNSW。
- as_of 是输入快照时点，不代表今天仍可租；分数是偏好匹配，不是房屋安全或签约保证。
- 不支持自动换汇、按人数分摊、真实市场租金估值或未来班次保证。
- user_confirmed 是调用方显式声明，不是用户鉴权或签名；本地原型未发送数据给 Agent 3。
- 来源事实和时效检查基于提供的模拟快照，不等于已实地验证房源真实或已重新联系供方。
