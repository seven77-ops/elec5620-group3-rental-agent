import { useState } from "react";
import { Alert, Button, Checkbox, Descriptions, Modal, Tag } from "antd";
import type { LeaseChatProposal } from "../../api/assistant";
import type { LeaseFields } from "../../api/leaseDraft";
import { leaseLabels, leaseText } from "../contracts/leaseFields";
import "./taskResults.css";

export default function LeaseProposalCard({
  proposal,
  disabled,
  onConfirm,
  onOpenContract,
}: {
  proposal: LeaseChatProposal;
  disabled: boolean;
  onConfirm: (id: string) => Promise<boolean>;
  onOpenContract: () => void;
}) {
  const [open, setOpen] = useState(false),
    [applicable, setApplicable] = useState(false),
    [saving, setSaving] = useState(false);
  const pending = proposal.status === "pending";
  const changes = Object.entries(proposal.patch).map(([key, value]) => ({
    key,
    label: leaseLabels[key as keyof LeaseFields] ?? key,
    children: leaseText(key as keyof LeaseFields, value),
  }));
  return (
    <section
      className="task-result-card task-lease-proposal"
      aria-label="Lease field proposal"
    >
      <div className="task-result-heading">
        <h3>
          {pending
            ? "Lease details need confirmation"
            : proposal.status === "applied"
              ? "Synced to Contract assistant"
              : "Lease details have changed"}
        </h3>
        <Tag color={pending ? "blue" : "default"}>
          {pending
            ? "Needs review"
            : proposal.status === "applied"
              ? "Saved"
              : "Needs updating"}
        </Tag>
      </div>
      {pending ? (
        <>
          <p className="muted small">
            {proposal.base_version
              ? `Changes based on draft v${proposal.base_version}.`
              : "Prepare a new unsigned draft."}
            Review before saving.
          </p>
          <Descriptions column={1} size="small" items={changes.slice(0, 5)} />
          <p className="muted small">
            {proposal.questions.length
              ? `There are ${proposal.questions.length} details missing; these can stay blank for now.`
              : "The available details are ready. Please review the full draft."}
          </p>
          <Button
            type="primary"
            disabled={disabled}
            onClick={() => {
              setApplicable(false);
              setOpen(true);
            }}
          >
            Review lease fields
          </Button>
        </>
      ) : (
        <p className="muted small">
          {proposal.status === "applied"
            ? "Chat and Contract assistant share the same saved draft."
            : "Please describe the fields to change using the latest draft."}
        </p>
      )}
      <Button type="link" onClick={onOpenContract} disabled={disabled}>
        Open Contract assistant
      </Button>
      <Modal
        title="Review and sync lease draft"
        open={open && pending}
        onCancel={() => {
          if (!saving) setOpen(false);
        }}
        okText="Confirm, save and sync draft"
        cancelText="Keep editing"
        confirmLoading={saving}
        okButtonProps={{ disabled: disabled || !applicable }}
        cancelButtonProps={{ disabled: saving }}
        styles={{ body: { maxHeight: "62vh", overflowY: "auto" } }}
        onOk={async () => {
          if (!applicable || disabled || saving) return;
          setSaving(true);
          try {
            if (await onConfirm(proposal.proposal_id)) setOpen(false);
          } finally {
            setSaving(false);
          }
        }}
      >
        <p>
          The details below will be saved to Contract assistant as an unsigned
          draft.
        </p>
        <h4>Fields prepared this time</h4>
        <Descriptions column={1} size="small" items={changes} />
        {proposal.questions.length > 0 && (
          <Alert
            type="info"
            showIcon
            title="Details still needed"
            description={
              <ul className="task-missing-fields">
                {proposal.questions.map((q) => (
                  <li key={q.field}>{q.question}</li>
                ))}
              </ul>
            }
          />
        )}
        <details className="task-lease-details">
          <summary>View all draft fields</summary>
          <Descriptions
            column={1}
            size="small"
            items={Object.entries(proposal.fields).map(([key, value]) => ({
              key,
              label: leaseLabels[key as keyof LeaseFields] ?? key,
              children: leaseText(key as keyof LeaseFields, value),
            }))}
          />
        </details>
        <Checkbox
          checked={applicable}
          disabled={saving}
          onChange={(e) => setApplicable(e.target.checked)}
        >
          I confirm this is an ordinary whole-property residential tenancy in
          NSW and have checked the details above.
        </Checkbox>
      </Modal>
    </section>
  );
}
