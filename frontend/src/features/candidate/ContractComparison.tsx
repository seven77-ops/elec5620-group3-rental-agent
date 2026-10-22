import { Alert, Space, Tag } from "antd";
import type { RealContractContext } from "../../api/followup";
const statuses = {
  match: { label: "内容一致", color: "blue" },
  different: { label: "需要核对差异", color: "orange" },
  missing: { label: "合同字段待补充", color: "default" },
  basis_unknown: { label: "计价口径待确认", color: "default" },
};
export default function ContractComparison({
  context,
}: {
  context: RealContractContext;
}) {
  return (
    <section className="panel" data-testid="real-contract-comparison">
      <h2>与房源和补充记录比对</h2>
      <p className="muted">
        本次上传关联：{String(context.selection.listing_snapshot.address)} ·
        需求 v{context.profile.version}
      </p>
      <Alert
        type="info"
        showIcon
        title="房源与用户记录分别保留"
        description={
          context.followup.version
            ? `信息来源：${context.followup.facts.source_note}。使用上传时保存的跟进 v${context.followup.version}，后续修改不会覆盖本次依据。`
            : "本次上传尚无补充记录，使用房源快照作为参考。房源租金的计价对象仍待核实。"
        }
      />
      {context.checks.map((check) => (
        <div
          className="contract-comparison-row"
          key={check.key}
          data-testid={`comparison-${check.key}`}
        >
          <Space wrap>
            <strong>{check.label}</strong>
            <Tag color={statuses[check.status].color}>
              {statuses[check.status].label}
            </Tag>
          </Space>
          <div className="contract-comparison-values">
            <div>
              <span className="muted small">{check.source}</span>
              {check.reference_value ?? "待确认"}
            </div>
            <div>
              <span className="muted small">合同提取</span>
              {check.contract_value ?? "未提取到"}
            </div>
          </div>
        </div>
      ))}
      <p className="muted small">
        内容一致仅表示记录与提取字段相同；请结合合同原文核对。
      </p>
    </section>
  );
}
