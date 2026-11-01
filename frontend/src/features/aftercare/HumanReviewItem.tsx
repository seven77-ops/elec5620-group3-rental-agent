import { Button, Form, Input, Space, Tag } from "antd";
import type { Dict } from "../../api/types";
import type { OperatorReview } from "../../api/operator";
import { newRequestId, post } from "../../api/client";
import { Failure, money } from "../../components/Common";
import { useAction } from "../../components/useAction";
import { issueCategories } from "./issuePresentation";
import { sydneyTime } from "./presentation";
import ReviewEvidence from "./ReviewEvidence";
import { useNavigate } from "react-router-dom";
import { demoAddress } from "../contracts/demoAddress";

export default function HumanReviewItem({
  item,
  onSaved,
  onReload,
}: {
  item: OperatorReview;
  onSaved: () => Promise<void>;
  onReload: () => Promise<boolean>;
}) {
  const [form] = Form.useForm();
  const action = useAction();
  const navigate = useNavigate();
  const report = item.report;
  const open = item.status === "open" && !item.is_demo;
  const save = async (decision?: string) => {
    try {
      const values = await form.validateFields();
      const path =
        item.kind === "contract"
          ? `/contract-reviews/${item.review_id}/decisions`
          : item.kind === "issue"
            ? `/issue-reports/${item.review_id}/advice`
            : "/aftercare/commands";
      const body =
        item.kind === "contract"
          ? {
              expected_version: item.version,
              decision: decision ?? "approve",
              note: values.note,
            }
          : item.kind === "issue"
            ? {
                request_id: newRequestId(),
                expected_version: item.version,
                note: values.note,
              }
            : {
                case_id: item.case_id,
                request_id: newRequestId(),
                expected_version: item.version,
                operation: "operator_decision",
                payload: {
                  review_id: item.review_id,
                  decision: "release",
                  note: values.note,
                  gate_resolved: true,
                },
              };
      let committed = false;
      await action.run(async () => {
        if (!committed) {
          await post(path, body);
          committed = true;
        }
        await onSaved();
      });
    } catch {
      /* Inline validation; keep advice on a failed request. */
    }
  };
  return (
    <article
      className="panel simple-review-card"
      data-testid="operator-review"
      data-case-id={item.case_id}
    >
      <div className="section-heading">
        <div>
          <Space wrap>
            {item.is_demo && <Tag>Demo example</Tag>}
            <Tag color={open ? "blue" : "green"}>
              {open
                ? "Awaiting review"
                : item.decisions.length
                  ? "Reviewed"
                  : "Closed"}
            </Tag>
            <span className="muted small">
              {report
                ? issueCategories[
                    report.category as keyof typeof issueCategories
                  ]
                : item.kind === "contract"
                  ? "Contract"
                  : "Move-out issue"}
            </span>
          </Space>
          <h2>{String(report?.title ?? item.reason)}</h2>
          {item.address && (
            <p className="muted">
              {demoAddress(item.address, item.review?.selection_evidence)}
            </p>
          )}
        </div>
      </div>
      <section aria-label="Report details">
        <h3>Report details</h3>
        {report ? (
          <>
            <p className="preserve-text">{String(report.description)}</p>
            {report.requested_outcome && (
              <p className="preserve-text">
                <strong>Requested help: </strong>
                {String(report.requested_outcome)}
              </p>
            )}
            {report.amount_cents != null && (
              <p>
                Amount reported:{" "}
                <strong>{money(Number(report.amount_cents) / 100)}</strong>
              </p>
            )}
          </>
        ) : (
          <>
            {item.review?.findings.map((finding, i) => (
              <div key={i}>
                <p className="preserve-text">
                  <strong>{String(finding.title)}: </strong>
                  {String(finding.reason)}
                </p>
                {Array.isArray(finding.evidence) &&
                  (finding.evidence as Dict[]).map((source, j) => (
                    <blockquote className="preserve-text" key={j}>
                      {String(
                        source.quote ?? source.value ?? source.source_ref ?? "",
                      )}
                      <div className="muted small">
                        {String(source.source_name ?? "Source")}
                        {source.page != null ? ` · Page ${source.page}` : ""}
                        {source.line != null ? ` · Line ${source.line}` : ""}
                      </div>
                    </blockquote>
                  ))}
              </div>
            ))}
            {item.claims?.map((claim) => (
              <p key={String(claim.claim_id)}>
                {String(claim.reason)} ·{" "}
                {money(Number(claim.amount_cents) / 100)}
              </p>
            ))}
            {item.history?.map((entry) => (
              <p className="preserve-text" key={String(entry.entry_id)}>
                {String(entry.text)}
              </p>
            ))}
          </>
        )}
        {item.updates?.map((update, i) => (
          <div className="review-tenant-update" key={i}>
            <strong>Additional information</strong>
            <p className="preserve-text">{String(update.text)}</p>
          </div>
        ))}
      </section>
      {Boolean(item.attachments?.length || item.evidence?.length) && (
        <section aria-label="Report evidence">
          <h3>Evidence</h3>
          <ReviewEvidence files={item.attachments ?? []} />
          {item.evidence?.map((e) => (
            <p key={String(e.evidence_id)}>
              {String(e.summary)} · {String(e.source_ref)}
            </p>
          ))}
        </section>
      )}
      {item.decisions.map((decision, i) => (
        <div className="review-saved-advice" key={i}>
          <strong>Review advice</strong>
          <p className="preserve-text">{String(decision.note)}</p>
          <span className="muted small">
            {sydneyTime(decision.at ?? decision.decided_at)}
          </span>
        </div>
      ))}
      {open && (
        <Form
          name={`review-${item.kind}-${item.case_id}-${item.review_id}`}
          form={form}
          layout="vertical"
          disabled={action.busy || Boolean(action.error)}
        >
          <Form.Item
            name="note"
            label="Review advice"
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Enter your review advice.",
              },
            ]}
          >
            <Input.TextArea
              rows={3}
              maxLength={item.kind === "contract" ? 1000 : 2000}
              placeholder="Summarise your assessment and suggested next steps."
            />
          </Form.Item>
          <Space wrap>
            <Button
              type="primary"
              loading={action.busy}
              disabled={Boolean(action.error)}
              onClick={() => void save()}
            >
              Save advice and complete review
            </Button>
            {item.kind === "contract" && (
              <Button onClick={() => void save("return")}>
                Request more information
              </Button>
            )}
          </Space>
        </Form>
      )}
      <Failure
        error={action.error}
        retry={async () => {
          const saved = await action.retry();
          if (saved) form.resetFields();
        }}
      />
      {Boolean(action.error) && (
        <Button
          disabled={action.busy}
          onClick={async () => {
            if (await onReload()) action.clear();
          }}
        >
          Load latest report
        </Button>
      )}
      <div className="review-record-footer">
        <span className="muted small">
          Submitted {sydneyTime(item.created_at)}
        </span>
        {!item.is_demo && (
          <Button
            type="link"
            onClick={() =>
              navigate(
                `/cases/${encodeURIComponent(item.case_id)}/${item.kind === "contract" ? `contract?mode=review&review_id=${encodeURIComponent(item.review_id)}` : "aftercare?tab=issues&section=history"}`,
              )
            }
          >
            {item.kind === "contract" ? "View contract record" : "View report"}
          </Button>
        )}
      </div>
    </article>
  );
}
