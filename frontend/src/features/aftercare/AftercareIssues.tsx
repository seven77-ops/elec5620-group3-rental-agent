import { useCase } from "../../app/context";
import ReviewEvidenceUpload, { emptyEvidence } from "./ReviewEvidenceUpload";
import ReviewEvidence from "./ReviewEvidence";
import type { LivingAttachment } from "../../api/living";
import { useState } from "react";
import {
  Button,
  Checkbox,
  Collapse,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
} from "antd";
import type { Dict } from "../../api/types";
import { money } from "../../components/Common";
import {
  CommandRecovery,
  type CommandRecoveryProps,
  type SendCommand,
} from "../AftercarePlan";
import {
  issueCategories,
  reviewDecisionNames,
  reviewState,
} from "./issuePresentation";
import { sydneyTime } from "./presentation";

export default function AftercareIssues({
  reviews,
  evidence,
  send,
  busy,
  recovery,
  reportOpen,
  closeReport,
}: {
  reviews: Dict[];
  evidence: Dict[];
  send: SendCommand;
  busy: boolean;
  recovery: CommandRecoveryProps;
  reportOpen: boolean;
  closeReport: () => void;
}) {
  const { current } = useCase();
  const [reportFiles, setReportFiles] = useState(emptyEvidence);
  const [replyFiles, setReplyFiles] = useState(emptyEvidence);
  const [form] = Form.useForm();
  const [replyForm] = Form.useForm();
  const [replyTo, setReplyTo] = useState<Dict | null>(null);
  const locked =
    busy || recovery.refreshing || reportFiles.busy || replyFiles.busy;
  const evidenceOptions = evidence.map((e) => ({
    value: String(e.evidence_id),
    label: String(e.summary),
  }));
  const close = () => {
    closeReport();
    setReplyTo(null);
  };
  const retry = async () => {
    const saved = await recovery.retry();
    if (saved) close();
    return saved;
  };
  const submitReport = async () => {
    try {
      const values = await form.validateFields();
      const saved = await send("report_issue", {
        category: values.category,
        title: values.title,
        description: values.description,
        requested_outcome: values.requested_outcome,
        amount_cents:
          values.amount == null ? null : Math.round(values.amount * 100),
        evidence_refs: values.evidence_refs ?? [],
        tenant_confirmed: true,
        attachment_ids: reportFiles.files.map((file) => file.attachment_id),
      });
      if (saved) closeReport();
    } catch {
      /* Inline validation; preserve the user's input. */
    }
  };
  const submitReply = async () => {
    try {
      const values = await replyForm.validateFields();
      const saved = await send("reply_review", {
        review_id: replyTo!.review_id,
        text: values.text,
        evidence_refs: values.evidence_refs ?? [],
        tenant_confirmed: true,
        attachment_ids: replyFiles.files.map((file) => file.attachment_id),
      });
      if (saved) setReplyTo(null);
    } catch {
      /* Inline validation. */
    }
  };
  const card = (review: Dict) => {
    const report = review.report as Dict | undefined;
    const state = reviewState(review);
    const timeline = [
      ...((review.decisions ?? []) as Dict[]).map((d) => ({
        at: String(d.at),
        label: reviewDecisionNames[String(d.decision)] ?? "Reviewer update",
        text: String(d.note),
        refs: [] as string[],
      })),
      ...((review.updates ?? []) as Dict[]).map((d) => ({
        at: String(d.at),
        label: "Your update",
        text: String(d.text),
        refs: (d.evidence_refs ?? []) as string[],
      })),
    ].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
    const linked = new Set((review.source_refs ?? []) as string[]);
    return (
      <article className="moveout-issue-card" key={String(review.review_id)}>
        <div className="section-heading">
          <div>
            <Space wrap>
              <Tag color={state.color}>{state.label}</Tag>
              {report && (
                <span className="muted small">
                  {
                    issueCategories[
                      report.category as keyof typeof issueCategories
                    ]
                  }
                </span>
              )}
            </Space>
            <h3>{String(report?.title ?? review.reason)}</h3>
          </div>
          {review.status === "open" && (
            <Button
              disabled={locked}
              onClick={() => {
                recovery.abandon();
                replyForm.resetFields();
                setReplyFiles(emptyEvidence);
                setReplyTo(review);
              }}
            >
              Add information
            </Button>
          )}
        </div>
        {report && (
          <>
            <p className="preserve-text">{String(report.description)}</p>
            <dl className="moveout-issue-facts">
              <div>
                <dt>Requested help</dt>
                <dd className="preserve-text">
                  {String(report.requested_outcome)}
                </dd>
              </div>
              {report.amount_cents != null && (
                <div>
                  <dt>Amount reported</dt>
                  <dd>{money(Number(report.amount_cents) / 100)}</dd>
                </div>
              )}
            </dl>
          </>
        )}
        <p className="muted small">Submitted {sydneyTime(review.created_at)}</p>
        {evidence.some((e) => linked.has(String(e.evidence_id))) && (
          <Collapse
            ghost
            size="small"
            items={[
              {
                key: "evidence",
                label: "Supporting references",
                children: evidence
                  .filter((e) => linked.has(String(e.evidence_id)))
                  .map((e) => (
                    <p key={String(e.evidence_id)}>
                      {String(e.summary)} · {String(e.source_ref)}
                    </p>
                  )),
              },
            ]}
          />
        )}
        <ReviewEvidence
          files={(review.attachments ?? []) as unknown as LivingAttachment[]}
        />
        {timeline.length > 0 && (
          <div className="moveout-issue-updates">
            {timeline.map((entry, i) => (
              <div key={i}>
                <strong>{entry.label}</strong>
                <p className="preserve-text">{entry.text}</p>
                <span className="muted small">{sydneyTime(entry.at)}</span>
              </div>
            ))}
          </div>
        )}
      </article>
    );
  };
  const pending = reviews.filter((r) => r.status === "open");
  const closed = reviews.filter((r) => r.status !== "open");
  return (
    <>
      <section
        className="panel moveout-issues"
        aria-label="Move-out issues and human review"
      >
        <div className="section-heading">
          <div>
            <h2>Issues & human review</h2>
            <p className="muted">
              Your reports, additional information and reviewer responses.
            </p>
          </div>
          <Tag>{pending.length} open</Tag>
        </div>
        {!reviews.length ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No issues reported yet"
          />
        ) : (
          <>
            {pending.map(card)}
            {closed.length > 0 && (
              <div className="moveout-completed">
                <h3>Completed reviews</h3>
                {closed.map(card)}
              </div>
            )}
          </>
        )}
      </section>
      <Modal
        title="Report a move-out issue"
        open={reportOpen}
        width={640}
        destroyOnHidden
        afterClose={() => {
          form.resetFields();
          setReportFiles(emptyEvidence);
        }}
        onCancel={() => {
          if (!locked) {
            recovery.abandon();
            closeReport();
          }
        }}
        closable={!locked}
        mask={{ closable: !locked }}
        confirmLoading={busy}
        okText="Submit to Human review"
        onOk={submitReport}
        okButtonProps={{
          disabled: locked || !reportFiles.ready || Boolean(recovery.error),
        }}
        cancelButtonProps={{ disabled: locked }}
      >
        <p className="muted">
          Send a report to the Human review queue on this device. A bond
          reference is not required.
        </p>
        <Form
          form={form}
          layout="vertical"
          disabled={locked}
          initialValues={{ category: "bond", confirmed: false }}
        >
          <div className="moveout-report-grid">
            <Form.Item
              name="category"
              label="Issue type"
              rules={[{ required: true }]}
            >
              <Select
                virtual={false}
                options={Object.entries(issueCategories).map(
                  ([value, label]) => ({ value, label }),
                )}
              />
            </Form.Item>
            <Form.Item name="amount" label="Amount involved (AUD, optional)">
              <InputNumber
                min={0.01}
                max={1000000}
                precision={2}
                style={{ width: "100%" }}
              />
            </Form.Item>
          </div>
          <Form.Item
            name="title"
            label="Issue title"
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Enter a short issue title.",
              },
            ]}
          >
            <Input
              maxLength={120}
              placeholder="For example, a disputed cleaning deduction"
            />
          </Form.Item>
          <Form.Item
            name="description"
            label="What happened?"
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Describe what happened.",
              },
            ]}
          >
            <Input.TextArea
              rows={4}
              maxLength={2000}
              showCount
              placeholder="Include what the agent or landlord said and any relevant dates."
            />
          </Form.Item>
          <Form.Item
            name="requested_outcome"
            label="What help do you need?"
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Describe the help you need.",
              },
            ]}
          >
            <Input.TextArea
              rows={2}
              maxLength={2000}
              placeholder="For example, review the deduction and supporting records."
            />
          </Form.Item>
          {evidenceOptions.length > 0 && (
            <Form.Item
              name="evidence_refs"
              label="Supporting references (optional)"
            >
              <Select mode="multiple" options={evidenceOptions} />
            </Form.Item>
          )}
          <Form.Item
            name="confirmed"
            valuePropName="checked"
            rules={[
              {
                validator: (_, value) =>
                  value
                    ? Promise.resolve()
                    : Promise.reject(
                        new Error("Confirm the report before submitting."),
                      ),
              },
            ]}
          >
            <Checkbox>
              I confirm this report is accurate to the best of my knowledge.
            </Checkbox>
          </Form.Item>
        </Form>
        <ReviewEvidenceUpload
          caseId={current.case_id}
          onChange={setReportFiles}
          disabled={busy || recovery.refreshing}
        />
        <CommandRecovery {...recovery} retry={retry} />
      </Modal>
      <Modal
        title="Add information"
        open={Boolean(replyTo)}
        destroyOnHidden
        onCancel={() => {
          if (!locked) {
            recovery.abandon();
            setReplyTo(null);
          }
        }}
        okText="Send update"
        onOk={submitReply}
        confirmLoading={busy}
        closable={!locked}
        mask={{ closable: !locked }}
        okButtonProps={{
          disabled: locked || !replyFiles.ready || Boolean(recovery.error),
        }}
        cancelButtonProps={{ disabled: locked }}
      >
        <p>
          <strong>{String(replyTo?.reason ?? "")}</strong>
        </p>
        <Form form={replyForm} layout="vertical" disabled={locked}>
          <Form.Item
            name="text"
            label="Additional information"
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Enter an update for the reviewer.",
              },
            ]}
          >
            <Input.TextArea rows={5} maxLength={2000} showCount />
          </Form.Item>
          {evidenceOptions.length > 0 && (
            <Form.Item
              name="evidence_refs"
              label="Supporting references (optional)"
            >
              <Select mode="multiple" options={evidenceOptions} />
            </Form.Item>
          )}
        </Form>
        <ReviewEvidenceUpload
          caseId={current.case_id}
          onChange={setReplyFiles}
          disabled={busy || recovery.refreshing}
        />
        <CommandRecovery {...recovery} retry={retry} />
      </Modal>
    </>
  );
}
