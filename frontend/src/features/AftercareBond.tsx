import { useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Timeline,
} from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { useCase } from "../app/context";
import { post } from "../api/client";
import type { Dict } from "../api/types";
import {
  CommandRecovery,
  type CommandRecoveryProps,
  type SendCommand,
} from "./AftercarePlan";
import { Failure, money, Status, text } from "../components/Common";
import { useAction } from "../components/useAction";
import AftercareBondDetails from "./AftercareBondDetails";
import type { PrefillValue } from "./aftercare/prefill";
import {
  reportedEventAt,
  sydneyTime,
  sydneyToday,
} from "./aftercare/presentation";

interface ExtractedClaim {
  amount: number;
  amount_cents: number;
  reason: string;
  quote: string;
}
interface Extraction {
  claims: ExtractedClaim[];
  rejected: number;
  event_date: string | null;
  event_date_quote: string | null;
  notice: string;
}

const draftModes: Record<string, string> = {
  template: "Fact template",
  constrained_model: "AI selects points · Each sentence is validated",
};

export default function AftercareBond({
  bond,
  evidence,
  send,
  busy,
  recovery,
  bondAmount,
  clock,
}: {
  bond: Dict | null;
  evidence: Dict[];
  send: SendCommand;
  busy: boolean;
  clock?: string;
  recovery: CommandRecoveryProps;
  bondAmount?: PrefillValue;
}) {
  const { config, current } = useCase();
  const real = config.mode === "real_listings";
  const aiEnabled = Boolean((config.capabilities as Dict).external_ai);
  const [bondRef, setBondRef] = useState(real ? "" : "SYNTHETIC-RBO-001");
  const [update, setUpdate] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [form] = Form.useForm();
  const [outcome, setOutcome] = useState("");
  const [agentMessage, setAgentMessage] = useState("");
  const [aiConsent, setAiConsent] = useState(false);
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const extract = useAction();
  const { modal, message } = App.useApp();
  const state = String(bond?.state ?? "");
  const history = (bond?.history ?? []) as Dict[];
  const claims = (bond?.claims ?? []) as Dict[];
  const drafts = (bond?.drafts ?? []) as Dict[];
  const today = real
    ? sydneyToday()
    : sydneyTime(clock ?? config.clocks.aftercare, false);
  const openUpdate = () => {
    form.resetFields();
    form.setFieldsValue({
      occurred_on: today,
      claims: [],
      conflicting_evidence: false,
    });
    setExtraction(null);
    setAgentMessage("");
    setAiConsent(false);
    extract.clear();
    setUpdate(true);
  };
  const readDeductions = () =>
    extract.run(async () => {
      const result = await post<Extraction>(
        `/cases/${encodeURIComponent(current.case_id)}/aftercare/deduction-extract`,
        { allow_external_ai: true, message: agentMessage },
      );
      setExtraction(result);
      const existing = (form.getFieldValue("claims") ?? []) as Dict[];
      form.setFieldsValue({
        claims: [
          ...existing,
          ...result.claims.map((c) => ({
            amount: c.amount,
            reason: c.reason,
            disputed: false,
            quote: c.quote,
          })),
        ],
        ...(result.event_date ? { occurred_on: result.event_date } : {}),
        ...(!form.getFieldValue("text")
          ? {
              text: `Received a bond deduction notice from the agent/landlord (${result.claims.length}  claims).`,
            }
          : {}),
      });
    });
  const submitUpdate = async () => {
    try {
      const v = await form.validateFields();
      const entryClaims = ((v.claims ?? []) as Dict[]).map((c) => ({
        claim_id: `claim-${crypto.randomUUID()}`,
        amount_cents: Math.round(Number(c.amount) * 100),
        reason: String(c.reason).trim(),
        evidence_refs: v.evidence_refs ?? [],
        disputed: Boolean(c.disputed),
      }));
      // Today keeps the current time (a minute back for clock drift); earlier days use midday Sydney.
      const occurred = reportedEventAt(
        v.occurred_on,
        real
          ? new Date(Date.now() - 60_000).toISOString()
          : (clock ?? config.clocks.aftercare),
      );
      const saved = await send(
        state === "Draft" ? "activate_bond" : "bond_update",
        {
          entry: {
            text: v.text,
            occurred_at: occurred,
            evidence_refs: v.evidence_refs ?? [],
            tenant_confirmed: true,
            claims: entryClaims,
            conflicting_evidence: Boolean(v.conflicting_evidence),
          },
        },
      );
      if (saved) setUpdate(false);
    } catch {
      /* Inline errors. */
    }
  };
  const currentDraft = drafts.filter((d) => d.status === "current").at(-1);
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Bond follow-up</h2>
        {bond && <Status value={state} />}
      </div>
      <p className="muted">
        Record facts reported by the tenant and deduction claims. Recording a
        deduction does not mean you accept it. Follow-up drafts are not sent
        automatically.
      </p>
      {bondAmount && (
        <Alert
          className="aftercare-prefill"
          type="info"
          showIcon
          title={`Bond recorded in the contract: ${money(Number(bondAmount.value))}`}
          description={`Source: ${bondAmount.label}${bondAmount.quote ? `“${bondAmount.quote}”` : ""}. Check the bond reference and actual amount against Rental Bonds Online records.`}
        />
      )}
      {!bond ? (
        <div className="date-actions">
          <label htmlFor="bond-reference">
            {real
              ? "Bond reference (optional for now)"
              : "Synthetic bond reference"}
          </label>
          <Input
            id="bond-reference"
            value={bondRef}
            onChange={(e) => setBondRef(e.target.value)}
          />
          <Button
            type="primary"
            loading={busy}
            onClick={() =>
              send("open_bond", {
                bond_reference: bondRef || null,
                deposit_evidence_ref: null,
              })
            }
            aria-label="Create bond follow-up"
          >
            Create bond follow-up
          </Button>
        </div>
      ) : (
        <>
          <p>Bond reference: {text(bond.bond_reference)}</p>
          <p>Bond evidence: {text(bond.deposit_evidence_ref)}</p>
          {state === "Draft" && (
            <>
              {!bond.bond_reference && !bond.deposit_evidence_ref && (
                <Alert
                  type="info"
                  showIcon
                  title="Add a bond reference or link bond evidence before activation."
                />
              )}
              <Button
                disabled={busy || recovery.refreshing}
                onClick={() => {
                  recovery.abandon();
                  setDetailsOpen(true);
                }}
              >
                Add bond details
              </Button>
            </>
          )}
          {state === "UnderReview" && (
            <Alert
              type="warning"
              showIcon
              title="Dispute or review restriction"
              description="Referred for human review. Follow-up drafts are paused until release. You can still record new facts or explicitly confirm the outcome."
            />
          )}
          <Space wrap className="section-actions">
            <Button
              type="primary"
              disabled={["Resolved", "Withdrawn"].includes(state)}
              loading={busy}
              onClick={openUpdate}
              aria-label={
                state === "Draft"
                  ? "Confirm facts and activate follow-up"
                  : "Record new facts or deduction claims"
              }
            >
              {state === "Draft"
                ? "Confirm facts and activate follow-up"
                : "Record new facts or deduction claims"}
            </Button>
            <Button
              disabled={state !== "AwaitingOutcome"}
              loading={busy}
              onClick={() =>
                send("request_draft", {
                  use_model: false,
                  allow_external_ai: false,
                })
              }
              aria-label="Prepare follow-up draft"
            >
              Prepare factual draft
            </Button>
            {aiEnabled && (
              <Button
                disabled={state !== "AwaitingOutcome"}
                loading={busy}
                onClick={() =>
                  modal.confirm({
                    title: "Use AI to select draft points?",
                    content:
                      "The recorded fact sentence catalogue will be sent to the configured AI. AI can only select sentence IDs. Required facts and references are validated; no new facts are generated and no email is sent.",
                    okText: "Agree and generate",
                    cancelText: "Cancel",
                    onOk: () =>
                      send("request_draft", {
                        use_model: true,
                        allow_external_ai: true,
                      }),
                  })
                }
                aria-label="Prepare draft with AI"
              >
                Prepare draft with AI
              </Button>
            )}
          </Space>
          <h3>Fact timeline</h3>
          {history.length ? (
            <Timeline
              items={history.map((h) => ({
                content: (
                  <>
                    <strong>{sydneyTime(h.occurred_at, false)}</strong>
                    <p>{text(h.text)}</p>
                    <small>
                      Evidence references:
                      {text(
                        ((h.evidence_refs as string[]) ?? []).join(", ") ||
                          "None",
                      )}
                      {h.conflicting_evidence
                        ? " · Evidence conflict flagged"
                        : ""}
                      {" · Recorded at "}
                      {sydneyTime(h.recorded_at)}
                    </small>
                  </>
                ),
              }))}
            />
          ) : (
            <p className="muted">No facts recorded yet.</p>
          )}
          {claims.length > 0 && (
            <>
              <h3>
                Reported deduction claims (claims only; deductions are not
                established)
              </h3>
              {claims.map((c, i) => (
                <div key={i} className="detail-row">
                  <strong>{money(Number(c.amount_cents) / 100)}</strong>
                  <p>
                    {text(c.reason)} ·{" "}
                    {c.disputed ? "Disputed by tenant" : "No dispute flagged"}
                  </p>
                  <small>
                    Evidence references:
                    {text(
                      ((c.evidence_refs as string[]) ?? []).join(", ") ||
                        "None",
                    )}
                  </small>
                </div>
              ))}
            </>
          )}
          {currentDraft && (
            <>
              <h3>Follow-up draft · Not sent</h3>
              <article className="draft-block">
                <Space wrap>
                  <Status value={String(currentDraft.status)} />
                  <span className="muted small">
                    {draftModes[String(currentDraft.mode)] ??
                      text(currentDraft.mode)}{" "}
                    · Based on case version{" "}
                    {text(currentDraft.based_on_version)} · Tenant review
                    required
                  </span>
                </Space>
                <p className="source-quote">{text(currentDraft.text)}</p>
                <Button
                  size="small"
                  onClick={() =>
                    void navigator.clipboard
                      .writeText(String(currentDraft.text))
                      .then(() =>
                        message.success(
                          "Copied. Paste it into your own email application.",
                        ),
                      )
                  }
                >
                  Copy draft
                </Button>
              </article>
            </>
          )}
          {drafts.length > (currentDraft ? 1 : 0) && (
            <Collapse
              ghost
              items={[
                {
                  key: "old",
                  label: `View earlier or superseded drafts (${drafts.length - (currentDraft ? 1 : 0)})`,
                  children: drafts
                    .filter((d) => d !== currentDraft)
                    .map((d, i) => (
                      <article className="draft-block" key={i}>
                        <Status value={String(d.status)} />
                        <p className="source-quote">{text(d.text)}</p>
                      </article>
                    )),
                },
              ]}
            />
          )}
          {!["Resolved", "Withdrawn"].includes(state) && (
            <div className="closure-box">
              <h3>Confirm outcome or withdraw</h3>
              <label htmlFor="bond-outcome">
                Your confirmed outcome or reason for withdrawal
              </label>
              <Input.TextArea
                id="bond-outcome"
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                rows={3}
              />
              <Space wrap>
                <Button
                  disabled={
                    !outcome.trim() ||
                    !["AwaitingOutcome", "UnderReview"].includes(state)
                  }
                  loading={busy}
                  onClick={() =>
                    modal.confirm({
                      title: "Confirm the bond outcome and close follow-up?",
                      content: outcome,
                      okText: "Confirm outcome and close",
                      cancelText: "Continue checking",
                      onOk: () =>
                        send("confirm_outcome", {
                          outcome,
                          evidence_refs: [],
                          tenant_confirmed: true,
                        }),
                    })
                  }
                  aria-label="Confirm outcome and close follow-up"
                >
                  Confirm outcome and close follow-up
                </Button>
                <Button
                  danger
                  disabled={!outcome.trim() || busy}
                  onClick={() =>
                    modal.confirm({
                      title: "Withdraw bond follow-up?",
                      content: outcome,
                      okText: "Confirm withdrawal",
                      cancelText: "Back",
                      onOk: () =>
                        send("withdraw", {
                          reason: outcome,
                          tenant_confirmed: true,
                        }),
                    })
                  }
                >
                  Withdraw follow-up
                </Button>
              </Space>
            </div>
          )}
          {Boolean(bond.outcome) && (
            <Alert
              type={state === "Resolved" ? "success" : "info"}
              showIcon
              title={
                state === "Resolved"
                  ? "You have confirmed the bond outcome"
                  : "You have withdrawn follow-up"
              }
              description={`${text(
                (bond.outcome as Dict).outcome ?? (bond.outcome as Dict).reason,
              )} · Recorded at ${sydneyTime((bond.outcome as Dict).recorded_at)}`}
            />
          )}
        </>
      )}
      {detailsOpen && bond && (
        <AftercareBondDetails
          bond={bond}
          evidence={evidence}
          send={send}
          busy={busy}
          recovery={recovery}
          onClose={() => setDetailsOpen(false)}
        />
      )}
      <Modal
        title={
          state === "Draft"
            ? "Confirm facts and activate follow-up"
            : "Record new facts or deduction claims"
        }
        open={update}
        width={720}
        onCancel={() => {
          if (busy || recovery.refreshing) return;
          if (recovery.error) recovery.abandon();
          setUpdate(false);
        }}
        confirmLoading={busy}
        okButtonProps={{
          "aria-label": "Confirm and record",
          disabled: recovery.refreshing || extract.busy,
        }}
        cancelButtonProps={{ disabled: busy || recovery.refreshing }}
        closable={!busy && !recovery.refreshing}
        mask={{ closable: !busy && !recovery.refreshing }}
        onOk={submitUpdate}
        okText="Confirm and record"
        cancelText={recovery.error ? "Cancel this edit" : "Cancel"}
      >
        <CommandRecovery
          {...recovery}
          retry={async () => {
            const saved = await recovery.retry();
            if (saved) setUpdate(false);
            return saved;
          }}
        />
        <p className="muted small">
          Currently saved follow-up status:
          <Status value={state} />
        </p>
        {aiEnabled ? (
          <Collapse
            className="aftercare-ai"
            items={[
              {
                key: "ai",
                label:
                  "Optional: Use AI to extract deduction claims from the agent/landlord text",
                children: (
                  <>
                    <Input.TextArea
                      aria-label="Original agent or landlord text"
                      rows={4}
                      maxLength={8000}
                      value={agentMessage}
                      placeholder="Paste the original agent or landlord email/message"
                      onChange={(e) => setAgentMessage(e.target.value)}
                    />
                    <Checkbox
                      checked={aiConsent}
                      onChange={(e) => setAiConsent(e.target.checked)}
                    >
                      I agree to send only this text to the configured AI. It
                      will not be saved to the case.
                    </Checkbox>
                    <div>
                      <Button
                        disabled={!aiConsent || !agentMessage.trim()}
                        loading={extract.busy}
                        onClick={() => void readDeductions()}
                      >
                        Extract deduction claims
                      </Button>
                    </div>
                    <Failure error={extract.error} retry={extract.retry} />
                    {extraction && (
                      <Alert
                        type={extraction.claims.length ? "success" : "warning"}
                        showIcon
                        title={
                          extraction.claims.length
                            ? `Added ${extraction.claims.length} candidate claims. Check each amount and reason`
                            : "No verifiable deduction amounts found. Please enter them manually"
                        }
                        description={
                          <>
                            <p className="small">{extraction.notice}</p>
                            {extraction.rejected > 0 && (
                              <p className="small">
                                Another {extraction.rejected} claims were
                                discarded because amounts or quotations did not
                                match the source.
                              </p>
                            )}
                            {extraction.event_date && (
                              <p className="small">
                                Fact date taken from the source: “
                                {extraction.event_date_quote}”
                              </p>
                            )}
                          </>
                        }
                      />
                    )}
                  </>
                ),
              },
            ]}
          />
        ) : (
          <p className="muted small">
            Configure AI to extract deduction claims from agent text. Please
            enter them manually for now.
          </p>
        )}
        <Form
          disabled={busy || recovery.refreshing}
          form={form}
          layout="vertical"
          initialValues={{
            occurred_on: today,
            claims: [],
            conflicting_evidence: false,
          }}
        >
          <Form.Item
            name="text"
            label="Facts reported by the tenant"
            rules={[
              { required: true, message: "Enter facts you have confirmed" },
            ]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            name="occurred_on"
            label="Date of event (Sydney time)"
            rules={[
              { required: true, message: "Select date" },
              {
                validator: (_, value) =>
                  !value || value <= today
                    ? Promise.resolve()
                    : Promise.reject(new Error("Future dates are not allowed")),
              },
            ]}
          >
            <Input type="date" max={today} />
          </Form.Item>
          <Form.Item name="evidence_refs" label="Linked evidence">
            <Select
              mode="multiple"
              options={evidence.map((e) => ({
                value: String(e.evidence_id),
                label: `${e.summary ?? e.evidence_id}`,
              }))}
            />
          </Form.Item>
          <h4>Deduction claims reported by the other party</h4>
          <Form.List name="claims">
            {(fields, { add, remove }) => (
              <>
                {fields.map((f) => (
                  <div className="list-form-row claim-row" key={f.key}>
                    <Form.Item
                      name={[f.name, "amount"]}
                      label="Amount (AUD)"
                      rules={[{ required: true, message: "Enter amount" }]}
                    >
                      <InputNumber min={0.01} max={100000} precision={2} />
                    </Form.Item>
                    <Form.Item
                      name={[f.name, "reason"]}
                      label="Reason given by the other party"
                      rules={[{ required: true, message: "Enter reason" }]}
                    >
                      <Input maxLength={300} />
                    </Form.Item>
                    <Form.Item
                      name={[f.name, "disputed"]}
                      valuePropName="checked"
                      label="Is this disputed?"
                    >
                      <Checkbox>I dispute this</Checkbox>
                    </Form.Item>
                    <Button
                      aria-label="Remove deduction claim"
                      icon={<MinusCircleOutlined />}
                      onClick={() => remove(f.name)}
                    />
                  </div>
                ))}
                <Button
                  icon={<PlusOutlined aria-hidden="true" />}
                  onClick={() =>
                    add({ amount: null, reason: "", disputed: false })
                  }
                >
                  Add deduction claim
                </Button>
              </>
            )}
          </Form.List>
          <Form.Item name="conflicting_evidence" valuePropName="checked">
            <Checkbox>
              Existing evidence conflicts (for example, the condition report and
              photos differ) and needs human review
            </Checkbox>
          </Form.Item>
          <p className="muted small">
            Disputed deductions or conflicting evidence are referred for human
            review. Confirming records this report; it does not accept the
            deduction.
          </p>
        </Form>
      </Modal>
    </section>
  );
}
