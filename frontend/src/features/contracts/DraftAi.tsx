import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Descriptions,
  Input,
  Modal,
  Space,
} from "antd";
import { api, newRequestId } from "../../api/client";
import type { AiConfig } from "../../api/ai";
import { proposeLeaseFields } from "../../api/leaseDraft";
import type {
  LeaseContext,
  LeaseFields,
  LeaseProposal,
} from "../../api/leaseDraft";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";
import { leaseLabels, leaseText } from "./leaseFields";
export default function DraftAi({
  context,
  fields,
  onApply,
  disabled,
}: {
  context: LeaseContext;
  fields: LeaseFields;
  onApply: (p: Partial<LeaseFields>) => void;
  disabled: boolean;
}) {
  const [config, setConfig] = useState<AiConfig | null>(null);
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  const [proposal, setProposal] = useState<LeaseProposal | null>(null);
  const [show, setShow] = useState(false);
  const action = useAction();
  const sourceRef = useRef(context.context_token);
  sourceRef.current = context.context_token;
  const snapshot = useRef("");
  useEffect(() => {
    let valid = true;
    api<AiConfig>("/ai/config")
      .then((v) => {
        if (valid) setConfig(v);
      })
      .catch(() => {});
    return () => {
      valid = false;
    };
  }, []);
  const generate = () => {
    const source = context.context_token;
    const body = {
      request_id: newRequestId(),
      context_token: source,
      message: description,
      current_fields: fields,
      allow_external_ai: true as const,
    };
    snapshot.current = JSON.stringify(fields);
    void action.run(async () => {
      const result = await proposeLeaseFields(context.sources.case_id, body);
      if (sourceRef.current !== source) return;
      setProposal(result);
      setShow(true);
      setConsent(false);
    });
  };
  const changed = snapshot.current !== JSON.stringify(fields);
  return (
    <section className="lease-ai-panel">
      <h2>用一句话整理合同要点</h2>
      <p className="muted">
        告诉我已经准备好的信息，我会整理成待确认字段，并提示还缺什么。
      </p>
      <Input.TextArea
        aria-label="合同要点描述"
        rows={3}
        maxLength={3000}
        value={description}
        disabled={disabled || action.busy}
        onChange={(e) => {
          setDescription(e.target.value);
          setConsent(false);
          action.clear();
        }}
        placeholder="例如：整租，拟定每周600澳元，押金2400，租客姓名 Zhang San，2026-11-01 起租。"
      />
      <Checkbox
        checked={consent}
        disabled={disabled || action.busy || !config?.configured}
        onChange={(e) => setConsent(e.target.checked)}
      >
        同意将这段文字发送至配置的外部 AI，用于本次字段提取。
      </Checkbox>
      <Space wrap>
        <Button
          onClick={generate}
          loading={action.busy}
          disabled={
            disabled || !consent || !description.trim() || !config?.configured
          }
        >
          AI 整理合同要点
        </Button>
        {!config?.configured && (
          <span className="muted small">AI 未配置，可直接在下方填写。</span>
        )}
      </Space>
      <Failure
        error={action.error}
        retry={consent && !disabled ? action.retry : undefined}
      />
      <Modal
        title="核对 AI 整理的字段"
        open={show}
        onCancel={() => setShow(false)}
        okText="将这些字段填入表单"
        cancelText="继续手动填写"
        okButtonProps={{
          disabled:
            changed ||
            disabled ||
            !proposal ||
            !Object.keys(proposal.patch).length,
        }}
        onOk={() => {
          if (proposal && !changed) {
            onApply(proposal.patch);
            setShow(false);
          }
        }}
      >
        <p>核对后只会填入表单，保存草稿仍需你再次确认。</p>
        {changed && (
          <Alert
            type="warning"
            showIcon
            title="表单已变化，请重新提取，避免覆盖最新填写。"
          />
        )}
        <Descriptions
          column={1}
          size="small"
          items={Object.entries(proposal?.patch ?? {}).map(([key, value]) => ({
            key,
            label: leaseLabels[key as keyof LeaseFields],
            children: leaseText(key as keyof LeaseFields, value),
          }))}
        />
        {proposal?.questions.length ? (
          <div className="lease-ai-questions">
            <strong>还需要补充</strong>
            <ul>
              {proposal.questions.slice(0, 5).map((q) => (
                <li key={q.field}>{q.question}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}
