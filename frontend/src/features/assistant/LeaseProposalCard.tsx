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
      aria-label="合同字段提案"
    >
      <div className="task-result-heading">
        <h3>
          {pending
            ? "合同信息待确认"
            : proposal.status === "applied"
              ? "已同步到合同助手"
              : "合同资料已有更新"}
        </h3>
        <Tag color={pending ? "blue" : "default"}>
          {pending
            ? "待核对"
            : proposal.status === "applied"
              ? "已保存"
              : "需重新整理"}
        </Tag>
      </div>
      {pending ? (
        <>
          <p className="muted small">
            {proposal.base_version
              ? `基于当前草稿 v${proposal.base_version} 整理修改。`
              : "准备一份新的未签署草稿。"}
            核对后再保存。
          </p>
          <Descriptions column={1} size="small" items={changes.slice(0, 5)} />
          <p className="muted small">
            {proposal.questions.length
              ? `还有 ${proposal.questions.length} 项信息待补充，可先保留空白。`
              : "已有信息已整理好，请核对完整内容。"}
          </p>
          <Button
            type="primary"
            disabled={disabled}
            onClick={() => {
              setApplicable(false);
              setOpen(true);
            }}
          >
            核对合同字段
          </Button>
        </>
      ) : (
        <p className="muted small">
          {proposal.status === "applied"
            ? "聊天和合同助手使用同一份已保存草稿。"
            : "请基于最新草稿重新说明需要修改的字段。"}
        </p>
      )}
      <Button type="link" onClick={onOpenContract} disabled={disabled}>
        查看合同助手
      </Button>
      <Modal
        title="核对并同步合同草稿"
        open={open && pending}
        onCancel={() => {
          if (!saving) setOpen(false);
        }}
        okText="确认保存并同步合同"
        cancelText="继续修改"
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
        <p>下面的信息将保存到合同助手，作为未签署草稿。</p>
        <h4>本次整理的字段</h4>
        <Descriptions column={1} size="small" items={changes} />
        {proposal.questions.length > 0 && (
          <Alert
            type="info"
            showIcon
            title="仍需补充的信息"
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
          <summary>查看完整草稿字段</summary>
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
          我确认适用于新州普通整租住宅，并已核对以上信息。
        </Checkbox>
      </Modal>
    </section>
  );
}
