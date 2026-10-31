import { useState } from "react";
import { Alert, Form, Input, Modal, Select } from "antd";
import type { Dict } from "../api/types";
import {
  CommandRecovery,
  type CommandRecoveryProps,
  type SendCommand,
} from "./AftercarePlan";

export default function AftercareBondDetails({
  bond,
  evidence,
  send,
  busy,
  recovery,
  onClose,
}: {
  bond: Dict;
  evidence: Dict[];
  send: SendCommand;
  busy: boolean;
  recovery: CommandRecoveryProps;
  onClose: () => void;
}) {
  const [reference, setReference] = useState(String(bond.bond_reference ?? ""));
  const [deposit, setDeposit] = useState<string | undefined>(
    typeof bond.deposit_evidence_ref === "string"
      ? bond.deposit_evidence_ref
      : undefined,
  );
  const editable = bond.state === "Draft";
  const deposits = evidence.filter((e) => e.kind === "deposit_record");
  const save = async () => {
    if (!editable || (!reference.trim() && !deposit)) return;
    const saved = await send("open_bond", {
      bond_reference: reference.trim() || null,
      deposit_evidence_ref: deposit || null,
    });
    if (saved) onClose();
  };
  return (
    <Modal
      title="Add bond details"
      open
      onOk={save}
      okText="Save bond details"
      cancelText={recovery.error ? "Cancel this edit" : "Cancel"}
      confirmLoading={busy}
      okButtonProps={{
        disabled:
          !editable ||
          recovery.refreshing ||
          Boolean(recovery.error) ||
          (!reference.trim() && !deposit),
      }}
      cancelButtonProps={{ disabled: busy || recovery.refreshing }}
      closable={!busy && !recovery.refreshing}
      mask={{ closable: !busy && !recovery.refreshing }}
      onCancel={() => {
        if (!busy && !recovery.refreshing) {
          if (recovery.error) recovery.abandon();
          onClose();
        }
      }}
    >
      <p>
        Enter a bond reference or select registered bond evidence. This remains
        a draft after saving. Check the facts before activating follow-up.
      </p>
      {!editable && (
        <Alert
          type="warning"
          title="Follow-up is active. Draft details cannot be edited."
        />
      )}
      <CommandRecovery
        {...recovery}
        retry={async () => {
          const saved = await recovery.retry();
          if (saved) onClose();
          return saved;
        }}
      />
      <Form
        layout="vertical"
        disabled={busy || recovery.refreshing || !editable}
      >
        <Form.Item label="Bond reference" htmlFor="bond-details-reference">
          <Input
            id="bond-details-reference"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </Form.Item>
        <Form.Item label="Bond evidence" htmlFor="bond-details-deposit">
          <Select
            id="bond-details-deposit"
            allowClear
            value={deposit}
            onChange={setDeposit}
            placeholder="Select registered bond evidence"
            options={deposits.map((e) => ({
              value: String(e.evidence_id),
              label: `${e.evidence_id} · ${e.summary}`,
            }))}
          />
        </Form.Item>
        {!deposits.length && (
          <p className="muted small">
            No bond evidence yet. Register “Bond evidence” in “View details and
            evidence”, then return to select it.
          </p>
        )}
      </Form>
    </Modal>
  );
}
