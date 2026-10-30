import ContractKnowledgePanel from "./knowledge/ContractKnowledgePanel";
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
} from "antd";
import { useCase, currentConfirmation } from "../app/context";
import { api, downloadUrl, post } from "../api/client";
import type { Dict, Evidence, Review } from "../api/types";
import {
  EvidenceDrawer,
  Failure,
  JsonDetails,
  label,
  PageTitle,
  Status,
  text,
} from "../components/Common";
import { useAction } from "../components/useAction";
import ContractUpload from "./ContractUpload";
import ContractAi from "./ai/ContractAi";
import ReviewHistory from "./ReviewHistory";
import ContractComparison from "./candidate/ContractComparison";
import type { RealContractContext } from "../api/followup";
export default function Contract({ embedded = false }: { embedded?: boolean }) {
  const { current, refresh, go } = useCase();
  const { message } = App.useApp();
  const action = useAction();
  const [selectedReview, setSelectedReview] = useState<string | undefined>();
  const [loadedReview, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [source, setSource] = useState<Evidence | null>(null);
  const [correct, setCorrect] = useState(false);
  const [correctionForm] = Form.useForm();
  const ref = selectedReview ?? current.reviews.at(-1)?.review_id;
  const selectedContext = useRef({ caseId: current.case_id, reviewId: ref });
  selectedContext.current = { caseId: current.case_id, reviewId: ref };
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const review = loadedReview?.review_id === ref ? loadedReview : null;
  const [consentRevision, setConsentRevision] = useState(0);
  const [reviewConsent, setReviewConsent] = useState<{
    consent_id: string | null;
    consent_active: boolean;
    real_context?: RealContractContext | null;
  } | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const consentChanged = () => setConsentRevision((v) => v + 1);
  const summary = current.reviews.find((r) => r.review_id === ref);
  const currentSelection =
    current.selection?.profile_version ===
    currentConfirmation(current)?.version;
  useEffect(() => {
    if (!ref) return;
    let valid = true;
    setReviewConsent(null);
    setError(null);
    setSource(null);
    Promise.all([
      api<Review>(`/contract-reviews/${ref}`),
      api<{
        consent_id: string | null;
        consent_active: boolean;
        real_context?: RealContractContext | null;
      }>(`/contract-reviews/${ref}/context`),
    ])
      .then(([r, context]) => {
        if (valid) {
          setReview(r);
          setReviewConsent(context);
          setError(null);
        }
      })
      .catch((e) => {
        if (valid) setError(e);
      });
    return () => {
      valid = false;
    };
  }, [ref, summary?.version, summary?.status, consentRevision]);
  const questions = () => {
    if (!review) return;
    const id = review.review_id,
      body = { expected_version: review.version };
    void action.run(async () => {
      const r = await post<Review>(`/contract-reviews/${id}/questions`, body);
      setReview(r);
      await refresh();
    });
  };
  const saveCorrection = async () => {
    try {
      const corrections = await correctionForm.validateFields();
      if (!review) return;
      const id = review.review_id,
        body = { expected_version: review.version, corrections };
      void action.run(async () => {
        const r = await post<Review>(
          `/contract-reviews/${id}/corrections`,
          body,
        );
        setReview(r);
        setCorrect(false);
        await refresh();
        message.success(
          "New review version saved. Earlier questions are no longer current.",
        );
      });
    } catch {
      /* Inline form validation. */
    }
  };
  const findings = review?.findings ?? [];
  const questionList = Array.isArray(review?.questions) ? review.questions : [];
  return (
    <>
      {!embedded && (
        <PageTitle
          title="Contract review"
          description="Upload a contract to review key clauses, items to check, and source evidence. Cross-check against a selected property when available."
          extra={
            current.reviews.length > 0 ? (
              <Select
                aria-label="Select contract review record"
                value={ref}
                onChange={setSelectedReview}
                options={current.reviews.map((r, i) => ({
                  value: r.review_id,
                  label: `Contract ${i + 1} · v${r.version}`,
                }))}
              />
            ) : undefined
          }
        />
      )}
      {embedded && current.reviews.length > 0 && (
        <Select
          aria-label="Select contract review record"
          value={ref}
          onChange={setSelectedReview}
          options={current.reviews.map((r, i) => ({
            value: r.review_id,
            label: `Contract ${i + 1} · v${r.version}`,
          }))}
        />
      )}
      <Failure
        error={action.error || error}
        retry={error ? consentChanged : action.retry}
      />
      {current.selection ? (
        <section className="selection-strip">
          <div>
            <span>Selected property</span>
            <strong>
              {current.selection.data_mode === "real_listings"
                ? text(current.selection.listing_snapshot.address)
                : current.selection.listing_id}
            </strong>
            <p>
              {current.selection.data_mode === "real_listings"
                ? `Listing AUD ${text(current.selection.listing_snapshot.weekly_rent)}/week · Pricing basis to be confirmed`
                : text(current.selection.listing_snapshot.address)}
            </p>
          </div>
          <Button onClick={() => go("recommendations")}>
            View selection evidence
          </Button>
        </section>
      ) : (
        <Alert
          type="info"
          showIcon
          title="Upload an existing contract directly"
          description="No rental needs or property selection is required. Give separate consent to review the contract, then continue asking about its clauses here."
        />
      )}
      {current.selection && !currentSelection && (
        <Alert
          type="warning"
          showIcon
          title="The selected property uses an earlier preference version"
          description="Reassess and select a property using your current confirmed preferences. Historical contract results are preserved."
        />
      )}
      {current.selection?.data_mode === "real_listings" && (
        <Alert
          type="info"
          showIcon
          title="Review an existing contract directly"
          description="The property remains an unverified snapshot. Contract fields are extracted locally and compared separately with the property and supplementary records."
        />
      )}
      <ContractUpload
        revision={consentRevision}
        onConsentChange={consentChanged}
        onReview={(r) => {
          setReview(r);
          setSelectedReview(r.review_id);
          consentChanged();
        }}
      />
      {review && (
        <>
          <ContractKnowledgePanel
            caseId={current.case_id}
            reviewId={review.review_id}
            reviewVersion={review.version}
            active={Boolean(reviewConsent?.consent_active)}
          />
          <ContractAi
            key={`${review.review_id}:${review.version}:${Boolean(reviewConsent?.consent_active)}`}
            review={review}
            active={Boolean(reviewConsent?.consent_active)}
            onApplied={async (next) => {
              // Apply can finish after selecting another review or leaving this
              // page. Only the current owner may update its view or refresh.
              if (
                !mounted.current ||
                selectedContext.current.caseId !== current.case_id ||
                selectedContext.current.reviewId !== next.review_id
              )
                return;
              // A reload or another saved action may have replaced this exact
              // source object, including changes that keep the same version.
              setReview((previous) => (previous === review ? next : previous));
              await refresh();
            }}
          />
          <section className="review-status">
            <div>
              <Status value={review.status} />
              <strong>Review version v{review.version}</strong>
              <p>
                {review.status_reason ??
                  "Check the contract against extracted fields, sources, and findings. Review completion does not approve signing."}
              </p>
            </div>
            <Space wrap>
              <Button onClick={() => setHistoryOpen(true)}>
                View review history
              </Button>
              <Button onClick={consentChanged}>Load latest review state</Button>
              <Button
                disabled={!reviewConsent?.consent_active}
                onClick={() => {
                  correctionForm.setFieldsValue(
                    Object.fromEntries(
                      Object.entries(review.fields)
                        .filter(([key]) =>
                          [
                            "address",
                            "rent_amount",
                            "bond",
                            "start_date",
                            "end_date",
                          ].includes(key),
                        )
                        .map(([key, f]) => [key, f.value]),
                    ),
                  );
                  setCorrect(true);
                }}
              >
                Correct extracted fields
              </Button>
              <a
                href={downloadUrl(
                  `/contract-reviews/${review.review_id}/export`,
                )}
              >
                Download review JSON
              </a>
            </Space>
          </section>
          {!reviewConsent?.consent_active && (
            <Alert
              type="warning"
              showIcon
              title="Review processing consent is inactive or the context has changed"
              description="Historical results remain readable. Further analysis and edits are paused. To continue, check the processing scope, give consent again, and submit the contract."
            />
          )}
          {reviewConsent?.consent_active && (
            <div className="consent-actions">
              <Button
                disabled={action.busy}
                onClick={() => {
                  const consentId = reviewConsent.consent_id;
                  void action.run(async () => {
                    await post(`/cases/${current.case_id}/contract-consents`, {
                      confirmed: false,
                      consent_id: consentId,
                    });
                    consentChanged();
                  });
                }}
              >
                Revoke processing consent for this review
              </Button>
            </div>
          )}
          {reviewConsent?.real_context && (
            <ContractComparison context={reviewConsent.real_context} />
          )}
          <div className="contract-result">
            <section className="panel">
              <h2>Extracted contract fields</h2>
              <Descriptions
                column={1}
                size="small"
                items={Object.entries(review.fields).map(([key, field]) => ({
                  key,
                  label: label(key),
                  children: (
                    <div className="field-value">
                      <span>{text(field.value)}</span>
                      {field.evidence && (
                        <Button
                          type="link"
                          size="small"
                          onClick={() => setSource(field.evidence!)}
                        >
                          View source text
                        </Button>
                      )}
                    </div>
                  ),
                }))}
              />
            </section>
            <section className="panel">
              <h2>Findings and tasks</h2>
              {findings.length === 0 ? (
                <p className="muted">
                  This review has no findings. No additional questions will be
                  generated.
                </p>
              ) : (
                findings.map((finding, i) => (
                  <article className="finding" key={i}>
                    <Space>
                      <Status
                        value={
                          String(finding.severity) === "high"
                            ? "Awaiting Human Review"
                            : String(finding.severity)
                        }
                      />
                      <strong>{text(finding.title)}</strong>
                    </Space>
                    <p>{text(finding.reason)}</p>
                    {Array.isArray(finding.evidence) && (
                      <Space wrap>
                        {(finding.evidence as Dict[]).map((e, j) => (
                          <Button
                            type="link"
                            size="small"
                            key={j}
                            onClick={() => setSource(e as Evidence)}
                          >
                            Evidence {j + 1}
                          </Button>
                        ))}
                      </Space>
                    )}
                    {typeof finding.rule_url === "string" &&
                      /^https:\/\//.test(finding.rule_url) && (
                        <p>
                          <a
                            href={finding.rule_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            View cited rule
                          </a>{" "}
                          · {text(finding.rule_version)}
                        </p>
                      )}
                  </article>
                ))
              )}
              {review.status === "Awaiting Human Review" && (
                <Alert
                  type="warning"
                  showIcon
                  title="Awaiting local demo operator"
                  description="Tenants cannot release high-risk findings. Question generation remains unavailable until a human decision."
                />
              )}
              <div className="consent-actions">
                <Button
                  disabled={
                    !reviewConsent?.consent_active ||
                    !["Reviewed", "Questions Ready"].includes(review.status) ||
                    findings.length === 0
                  }
                  onClick={questions}
                  loading={action.busy}
                  aria-label="Prepare question list"
                >
                  Prepare question list
                </Button>
              </div>
              {questionList.length > 0 && (
                <>
                  <h3>Questions · Not sent</h3>
                  <a
                    href={downloadUrl(
                      `/contract-reviews/${review.review_id}/questions/export`,
                    )}
                  >
                    Download questions
                  </a>
                  {questionList.map((q, i) => (
                    <div className="detail-row" key={i}>
                      <p>{text(q.text)}</p>
                      <small>
                        Finding {text(q.finding_id)} · Review version{" "}
                        {text(q.review_version)}
                      </small>
                    </div>
                  ))}
                </>
              )}
            </section>
          </div>
          <Collapse
            items={[
              {
                key: "trace",
                label: "Review references and version history",
                children: (
                  <JsonDetails
                    value={{
                      review_id: review.review_id,
                      version: review.version,
                      document: review.document,
                      intake: review.intake,
                      revisions: review.revisions,
                      events: review.events,
                    }}
                  />
                ),
              },
            ]}
          />
          <div className="next-action compact">
            <div>
              <h2>Continue to aftercare services</h2>
              <p>
                Complete and confirm lease details first. Contract review
                results serve only as candidate facts.
              </p>
            </div>
            <Button onClick={() => go("aftercare")}>
              Confirm lease details
            </Button>
          </div>
        </>
      )}
      {review && (
        <ReviewHistory
          reviewId={review.review_id}
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
        />
      )}
      <EvidenceDrawer
        title="Contract source evidence"
        open={Boolean(source)}
        onClose={() => setSource(null)}
      >
        {source && (
          <>
            <p className="muted">
              {source.source_name ?? source.source_ref} · Page{" "}
              {source.page ?? "—"} · Line {source.line ?? "—"}
            </p>
            <blockquote className="source-quote">
              {source.quote ??
                "This reference has no locatable quotation. Check the full source."}
            </blockquote>
            <JsonDetails value={source} />
          </>
        )}
      </EvidenceDrawer>
      <Modal
        open={correct}
        title="Correct extracted fields"
        okText="Save as a new review version"
        cancelText="Cancel"
        onCancel={() => setCorrect(false)}
        onOk={saveCorrection}
        confirmLoading={action.busy}
      >
        <p>
          Only correct fields extracted incorrectly. Changes trigger a new
          review and invalidate earlier questions.
        </p>
        <Form form={correctionForm} layout="vertical">
          <Form.Item
            name="address"
            label="Contract address"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <div className="form-grid">
            <Form.Item name="rent_amount" label="Contract rent (AUD)">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="bond" label="Bond (AUD)">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="start_date" label="Lease start">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="end_date" label="Lease end">
              <Input type="date" />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </>
  );
}
