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
      title="补录押金资料"
      open
      onOk={save}
      okText="保存押金资料"
      cancelText={recovery.error ? "取消本次编辑" : "取消"}
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
        填写押金编号，或选择已登记的押金凭证。保存后仍是草稿，核对事实后再激活跟进。
      </p>
      {!editable && (
        <Alert type="warning" title="跟进已激活，草稿资料不可修改。" />
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
        <Form.Item label="押金记录编号" htmlFor="bond-details-reference">
          <Input
            id="bond-details-reference"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </Form.Item>
        <Form.Item label="押金凭证" htmlFor="bond-details-deposit">
          <Select
            id="bond-details-deposit"
            allowClear
            value={deposit}
            onChange={setDeposit}
            placeholder="选择已登记的押金凭证"
            options={deposits.map((e) => ({
              value: String(e.evidence_id),
              label: `${e.evidence_id} · ${e.summary}`,
            }))}
          />
        </Form.Item>
        {!deposits.length && (
          <p className="muted small">
            暂无押金凭证。可在“查看资料与证据”中登记“押金凭证”，再回来选择。
          </p>
        )}
      </Form>
    </Modal>
  );
}
