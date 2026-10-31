import { contractValue, reviewSummary } from "./contracts/reviewPresentation";
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
import { useCase } from "../app/context";
import { api, post } from "../api/client";
import type { Dict, Evidence, Review } from "../api/types";
import {
  EvidenceDrawer,
  Failure,
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
        message.success("Contract details updated and checked again.");
      });
    } catch {
      /* Inline form validation. */
    }
  };
  const findings = review?.findings ?? [];
  const questionList = Array.isArray(review?.questions) ? review.questions : [];
  const overview = review ? reviewSummary(review) : null;
  const editDetails = () => {
    if (!review) return;
    correctionForm.setFieldsValue(
      Object.fromEntries(
        ["address", "rent_amount", "bond", "start_date", "end_date"].map(
          (key) => [key, review.fields[key]?.value],
        ),
      ),
    );
    setCorrect(true);
  };
  const upload = (
    <ContractUpload
      revision={consentRevision}
      onConsentChange={consentChanged}
      onReview={(next) => {
        setReview(next);
        setSelectedReview(next.review_id);
        consentChanged();
      }}
    />
  );
  return (
    <>
      {!embedded && (
        <PageTitle
          title="Contract review"
          description="Upload your contract, check the important details, and see what needs attention."
        />
      )}
      <Failure
        error={action.error || error}
        retry={error ? consentChanged : action.retry}
        showDetails={false}
      />
      {current.reviews.length > 1 && (
        <Select
          className="contract-review-picker"
          aria-label="Select contract review record"
          value={ref}
          onChange={setSelectedReview}
          options={current.reviews.map((r, i) => ({
            value: r.review_id,
            label: `Contract ${i + 1} · v${r.version}`,
          }))}
        />
      )}
      {!review && upload}
      {review && overview && (
        <section
          className="contract-review-results"
          aria-label="Contract review results"
          data-review-id={review.review_id}
          data-review-version={review.version}
        >
          <section className="panel contract-overview review-status">
            <div>
              <p className="muted contract-filename">
                {review.document.source_name}
              </p>
              <Status value={review.status} />
              <h2>{overview.title}</h2>
              <p>{overview.description}</p>
            </div>
            <Button
              onClick={editDetails}
              disabled={!reviewConsent?.consent_active}
            >
              Edit contract details
            </Button>
          </section>
          {!reviewConsent?.consent_active && (
            <Alert
              type="warning"
              showIcon
              title="Permission to process this contract is inactive"
              description="You can still read your results. To make changes, upload the contract again and renew your permission."
            />
          )}
          <section
            className="panel contract-findings"
            aria-label="Contract issues"
          >
            <h2>Items to check</h2>
            {findings.length === 0 ? (
              <p className="muted">
                No specific issues were found by the available checks. Review
                the contract details below.
              </p>
            ) : (
              findings.map((finding, i) => (
                <article className="finding" key={i}>
                  <strong>{text(finding.title)}</strong>
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
                          View source {j + 1}
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
                          Read official guidance
                        </a>
                      </p>
                    )}
                </article>
              ))
            )}
            {review.status === "Awaiting Human Review" && (
              <Alert
                type="warning"
                showIcon
                title="Waiting for a reviewer"
                description="These issues have been referred for human review. You can read the evidence and check the details while you wait."
              />
            )}
            {findings.length > 0 && (
              <div className="consent-actions">
                <Button
                  disabled={
                    !reviewConsent?.consent_active ||
                    !["Reviewed", "Questions Ready"].includes(review.status)
                  }
                  onClick={questions}
                  loading={action.busy}
                >
                  Prepare question list
                </Button>
              </div>
            )}
            {questionList.length > 0 && (
              <div className="contract-questions">
                <h3>Questions to ask your landlord or agent</h3>
                <p className="muted">These questions have not been sent.</p>
                {questionList.map((q, i) => (
                  <p key={i}>{text(q.text)}</p>
                ))}
                <Button
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(
                        questionList.map((q) => text(q.text)).join("\n\n"),
                      );
                      message.success("Questions copied.");
                    } catch {
                      message.error(
                        "Could not copy the questions. Select the text and copy it manually.",
                      );
                    }
                  }}
                >
                  Copy questions
                </Button>
              </div>
            )}
          </section>
          <section className="panel" aria-label="Contract details">
            <div className="contract-section-heading">
              <h2>Contract details</h2>
              <Button
                type="link"
                disabled={!reviewConsent?.consent_active}
                onClick={editDetails}
              >
                Edit details
              </Button>
            </div>
            <Descriptions
              column={1}
              size="small"
              items={[
                "address",
                "landlord",
                "tenant",
                "rent_amount",
                "bond",
                "start_date",
                "end_date",
                ...(review.fields.signed_date?.value ? ["signed_date"] : []),
              ].map((key) => ({
                key,
                label: label(key),
                children: (
                  <div className="field-value">
                    <span>{contractValue(review, key)}</span>
                    {review.fields[key]?.evidence && (
                      <Button
                        type="link"
                        size="small"
                        onClick={() => setSource(review.fields[key].evidence!)}
                      >
                        View source text
                      </Button>
                    )}
                  </div>
                ),
              }))}
            />
          </section>
          {reviewConsent?.real_context && (
            <Collapse
              items={[
                {
                  key: "comparison",
                  label: "Compare with the selected property",
                  children: (
                    <ContractComparison context={reviewConsent.real_context} />
                  ),
                },
              ]}
            />
          )}
          <ContractKnowledgePanel
            caseId={current.case_id}
            reviewId={review.review_id}
            reviewVersion={review.version}
            active={Boolean(reviewConsent?.consent_active)}
          />
          <Collapse
            items={[
              {
                key: "ai",
                label: "AI-assisted check",
                children: (
                  <ContractAi
                    key={`${review.review_id}:${review.version}:${Boolean(reviewConsent?.consent_active)}`}
                    review={review}
                    active={Boolean(reviewConsent?.consent_active)}
                    onApplied={async (next) => {
                      if (
                        !mounted.current ||
                        selectedContext.current.caseId !== current.case_id ||
                        selectedContext.current.reviewId !== next.review_id
                      )
                        return;
                      setReview((previous) =>
                        previous === review ? next : previous,
                      );
                      await refresh();
                    }}
                  />
                ),
              },
            ]}
          />
          <Collapse
            items={[
              {
                key: "manage",
                label: "Manage this contract",
                children: (
                  <>
                    <Space wrap className="contract-management-actions">
                      <Button onClick={() => setHistoryOpen(true)}>
                        View review history
                      </Button>
                      <Button onClick={consentChanged}>Refresh review</Button>
                      {reviewConsent?.consent_active && (
                        <Button
                          disabled={action.busy}
                          onClick={() => {
                            const consentId = reviewConsent.consent_id;
                            void action.run(async () => {
                              await post(
                                `/cases/${current.case_id}/contract-consents`,
                                { confirmed: false, consent_id: consentId },
                              );
                              consentChanged();
                            });
                          }}
                        >
                          Stop processing this contract
                        </Button>
                      )}
                    </Space>
                    <Collapse
                      items={[
                        {
                          key: "upload",
                          label: "Upload another contract",
                          children: upload,
                        },
                      ]}
                    />
                  </>
                ),
              },
            ]}
          />
          <div className="next-action compact">
            <div>
              <h2>Ready for the next step?</h2>
              <p>
                Confirm your tenancy details to start using aftercare services.
              </p>
            </div>
            <Button onClick={() => go("aftercare")}>
              Confirm lease details
            </Button>
          </div>
        </section>
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
              {source.source_name ?? "Contract"}
              {source.page ? ` · Page ${source.page}` : ""}
            </p>
            <blockquote className="source-quote">
              {source.quote ?? "Check the original document for this detail."}
            </blockquote>
          </>
        )}
      </EvidenceDrawer>
      <Modal
        open={correct}
        title="Edit contract details"
        okText="Save changes"
        cancelText="Cancel"
        onCancel={() => setCorrect(false)}
        onOk={saveCorrection}
        confirmLoading={action.busy}
      >
        <p>
          Correct details that were read incorrectly. Saving will run the checks
          again; it does not change your original document.
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
