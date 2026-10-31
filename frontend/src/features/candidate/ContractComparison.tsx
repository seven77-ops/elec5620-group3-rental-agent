import { Alert, Space, Tag } from "antd";
import type { RealContractContext } from "../../api/followup";
const statuses = {
  match: { label: "Matches", color: "blue" },
  different: { label: "Review differences", color: "orange" },
  missing: { label: "Contract field missing", color: "default" },
  basis_unknown: { label: "Confirm pricing basis", color: "default" },
};
export default function ContractComparison({
  context,
}: {
  context: RealContractContext;
}) {
  return (
    <section className="panel" data-testid="real-contract-comparison">
      <h2>Compare with listing and follow-up records</h2>
      <p className="muted">
        Upload linked to: {String(context.selection.listing_snapshot.address)} ·
        Needs v{context.profile.version}
      </p>
      <Alert
        type="info"
        showIcon
        title="Listing and user records kept separately"
        description={
          context.followup.version
            ? `Information source: ${context.followup.facts.source_note}. Using follow-up v${context.followup.version}, saved at upload. Later edits do not change this evidence.`
            : "No follow-up record was saved for this upload. The listing snapshot is used as a reference. Its rent pricing basis still needs verification."
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
              {check.reference_value ?? "To confirm"}
            </div>
            <div>
              <span className="muted small">Extracted from contract</span>
              {check.contract_value ?? "Not extracted"}
            </div>
          </div>
        </div>
      ))}
      <p className="muted small">
        A match only means the record and extracted field agree. Check against
        the original contract.
      </p>
    </section>
  );
}
