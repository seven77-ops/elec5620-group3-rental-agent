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
      <h2>Describe the contract details in a sentence</h2>
      <p className="muted">
        Tell me what you have ready. I will organise it into fields to confirm
        and identify what is missing.
      </p>
      <Input.TextArea
        aria-label="Contract details description"
        rows={3}
        maxLength={3000}
        value={description}
        disabled={disabled || action.busy}
        onChange={(e) => {
          setDescription(e.target.value);
          setConsent(false);
          action.clear();
        }}
        placeholder="For example: whole property, proposed rent AUD600/week, bond AUD2400, tenant Zhang San, starting 2026-11-01."
      />
      <Checkbox
        checked={consent}
        disabled={disabled || action.busy || !config?.configured}
        onChange={(e) => setConsent(e.target.checked)}
      >
        I agree to send this text to the configured external AI for this field
        extraction.
      </Checkbox>
      <Space wrap>
        <Button
          onClick={generate}
          loading={action.busy}
          disabled={
            disabled || !consent || !description.trim() || !config?.configured
          }
        >
          Extract contract details with AI
        </Button>
        {!config?.configured && (
          <span className="muted small">
            AI is not configured. You can fill in the form below directly.
          </span>
        )}
      </Space>
      {action.busy && (
        <p className="muted small" role="status">
          Organising contract fields. Larger inputs may take several dozen
          seconds. Please wait.
        </p>
      )}
      <Failure
        error={action.error}
        retry={consent && !disabled ? action.retry : undefined}
      />
      <Modal
        title="Check AI-extracted fields"
        open={show}
        onCancel={() => setShow(false)}
        okText="Fill these fields into the form"
        cancelText="Continue manual entry"
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
        <p>
          Checking only fills the form. Saving the draft still requires your
          confirmation.
        </p>
        {!!proposal?.warnings?.length && (
          <Alert
            type="warning"
            showIcon
            title="Some fields need manual checking"
            description={`These fields were not filled automatically: ${proposal.warnings.map((item) => item.label).join(", ")}. Other checked fields can still be filled into the form.`}
          />
        )}
        {changed && (
          <Alert
            type="warning"
            showIcon
            title="The form has changed. Extract again to avoid overwriting your latest input."
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
            <strong>Still needed</strong>
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
