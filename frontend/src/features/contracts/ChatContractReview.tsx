import { useEffect, useState } from "react";
import { Alert, Button, Descriptions, Select, Space } from "antd";
import { useCase } from "../../app/context";
import { api } from "../../api/client";
import type { Dict, Evidence, Review } from "../../api/types";
import {
  EvidenceDrawer,
  Failure,
  label,
  Status,
  text,
} from "../../components/Common";
import ContractUpload from "../ContractUpload";
import ContractKnowledgePanel from "../knowledge/ContractKnowledgePanel";

/** Contract intake and private Q&A embedded in the assistant conversation. */
export default function ChatContractReview({
  onReview,
}: { onReview?: (review: Review) => void } = {}) {
  const { current, go } = useCase();
  const [selected, setSelected] = useState<{
    caseId: string;
    reviewId: string;
  } | null>(null);
  const [loaded, setLoaded] = useState<{
    caseId: string;
    review: Review;
    active: boolean;
  } | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [source, setSource] = useState<Evidence | null>(null);
  const reviewId =
    selected?.caseId === current.case_id
      ? selected.reviewId
      : current.reviews.at(-1)?.review_id;
  const summary = current.reviews.find((r) => r.review_id === reviewId);
  const review =
    loaded?.caseId === current.case_id && loaded.review.review_id === reviewId
      ? loaded.review
      : null;
  const changed = () => setRevision((value) => value + 1);
  useEffect(() => {
    let valid = true;
    setLoaded(null);
    setError(null);
    setSource(null);
    if (reviewId) {
      Promise.all([
        api<Review>(`/contract-reviews/${reviewId}`),
        api<{ consent_active: boolean }>(
          `/contract-reviews/${reviewId}/context`,
        ),
      ])
        .then(([next, context]) => {
          if (valid)
            setLoaded({
              caseId: current.case_id,
              review: next,
              active: context.consent_active,
            });
        })
        .catch((failure) => {
          if (valid) setError(failure);
        });
    }
    return () => {
      valid = false;
    };
  }, [current.case_id, reviewId, summary?.version, summary?.status, revision]);
  return (
    <section
      aria-label="Contract review in chat"
      className="chat-contract-review"
    >
      <p>
        Send me a contract to organise rent, bond, lease dates, and clauses to
        check. No property selection is required. After review, ask about the
        contract text below.
      </p>
      <ContractUpload
        revision={revision}
        onConsentChange={changed}
        onReview={(next) => {
          setSelected({ caseId: current.case_id, reviewId: next.review_id });
          setLoaded({ caseId: current.case_id, review: next, active: true });
          onReview?.(next);
        }}
      />
      <Failure error={error} retry={changed} />
      {current.reviews.length > 1 && (
        <Select
          aria-label="Select contract in chat"
          value={reviewId}
          onChange={(id) =>
            setSelected({ caseId: current.case_id, reviewId: id })
          }
          options={current.reviews.map((item, i) => ({
            value: item.review_id,
            label: `Contract ${i + 1} · v${item.version}`,
          }))}
        />
      )}
      {review && (
        <>
          <section className="panel" aria-label="Contract review summary">
            <Space wrap>
              <h3>{review.document.source_name}</h3>
              <Status value={review.status} />
            </Space>
            <p>
              {review.status_reason ??
                "Check extracted fields and sources before asking more about the clauses."}
            </p>
            <Descriptions
              column={1}
              size="small"
              items={Object.entries(review.fields).map(([key, field]) => ({
                key,
                label: label(key),
                children: (
                  <Space wrap>
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
                  </Space>
                ),
              }))}
            />
            <h3>Findings and items to check</h3>
            {review.findings.length ? (
              review.findings.map((finding, i) => (
                <article className="finding" key={i}>
                  <strong>{text(finding.title)}</strong>
                  <p>{text(finding.reason)}</p>
                  {Array.isArray(finding.evidence) &&
                    (finding.evidence as Dict[]).map((item, j) => (
                      <Button
                        type="link"
                        size="small"
                        key={j}
                        onClick={() => setSource(item as Evidence)}
                      >
                        Source evidence {j + 1}
                      </Button>
                    ))}
                </article>
              ))
            ) : (
              <p>
                {["Reviewed", "Questions Ready"].includes(review.status)
                  ? "Current basic field checks are complete with no new findings. Continue checking special clauses against the source text."
                  : "Complete findings are not available yet. Check missing fields or review status above, then continue with the source text."}
              </p>
            )}
            <Button onClick={() => go("contract?mode=review")}>
              View full review and edit fields
            </Button>
          </section>
          {!loaded?.active && (
            <Alert
              type="info"
              title="Contract processing consent was revoked or the context changed. Historical results remain available. Give consent again and upload to continue processing."
            />
          )}
          <ContractKnowledgePanel
            key={`${current.case_id}:${review.review_id}`}
            caseId={current.case_id}
            reviewId={review.review_id}
            reviewVersion={review.version}
            active={Boolean(loaded?.active)}
            expanded
          />
        </>
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
          </>
        )}
      </EvidenceDrawer>
    </section>
  );
}
