import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Button, Checkbox, Tag } from "antd";
import { CheckCircleOutlined } from "@ant-design/icons";
import { useCase } from "../../app/context";
import { api, newRequestId, post } from "../../api/client";
import { aiPost } from "../../api/ai";
import {
  getContractChecklist,
  type ContractCheck,
  type ContractChecklist,
} from "../../api/contractReview";
import type { Review } from "../../api/types";
import { Failure, Loading } from "../../components/Common";
import { useAction } from "../../components/useAction";
import ReviewUpload from "./ReviewUpload";
import "./simpleContractReview.css";

type Processing = { consent_id: string | null; consent_active: boolean };
type Result = {
  caseId: string;
  report: ContractChecklist;
  processing: Processing;
  aiFailed: boolean;
};

function checkValue(check: ContractCheck) {
  if (typeof check.value === "number")
    return check.value.toLocaleString("en-AU");
  const labels: Record<string, Record<string, string>> = {
    "field:rent_period": {
      week: "Weekly",
      fortnight: "Fortnightly",
      month: "Monthly",
    },
    "field:rent_scope": {
      whole_property: "Whole property",
      per_room: "Per room",
      per_person: "Per person",
    },
  };
  return labels[check.id]?.[String(check.value)] ?? check.value;
}

function CheckSource({ check }: { check: ContractCheck }) {
  const sources = check.evidence.filter((evidence) => evidence?.quote);
  return sources.length ? (
    <details className="contract-check-source">
      <summary>View source text</summary>
      {sources.map((evidence, index) => (
        <div key={index}>
          {evidence.page && <p className="muted small">Page {evidence.page}</p>}
          <blockquote>{evidence.quote}</blockquote>
        </div>
      ))}
    </details>
  ) : null;
}

export default function SimpleContractReview() {
  const { current, refresh } = useCase();
  const [query, setQuery] = useSearchParams();
  const requestedReviewId = query.get("review_id");
  const invalidRequestedReview =
    requestedReviewId !== null &&
    !current.reviews.some((item) => item.review_id === requestedReviewId);
  const caseId = current.case_id;
  const liveCase = useRef(caseId);
  liveCase.current = caseId;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [selected, setSelected] = useState<{
    caseId: string;
    reviewId: string;
  }>();
  const [newUpload, setNewUpload] = useState<string>();
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  const [allowAi, setAllowAi] = useState(false);
  const action = useAction();
  const reviewId =
    requestedReviewId !== null
      ? invalidRequestedReview
        ? undefined
        : requestedReviewId
      : selected?.caseId === caseId
        ? selected.reviewId
        : current.reviews.at(-1)?.review_id;
  const summary = current.reviews.find((item) => item.review_id === reviewId);
  const visible =
    result?.caseId === caseId && result.report.review_id === reviewId
      ? result
      : undefined;
  const load = async (id: string) => {
    const [report, processing] = await Promise.all([
      getContractChecklist(id),
      api<Processing>(`/contract-reviews/${id}/context`),
    ]);
    return { report, processing };
  };
  useEffect(() => {
    let valid = true;
    setError(undefined);
    setAllowAi(false);
    action.clear();
    if (reviewId) {
      load(reviewId)
        .then((next) => {
          if (valid)
            setResult((previous) => ({
              caseId,
              ...next,
              aiFailed:
                previous?.caseId === caseId &&
                previous.report.review_id === reviewId
                  ? previous.aiFailed
                  : false,
            }));
        })
        .catch((failure) => {
          if (valid) setError(failure);
        });
    }
    return () => {
      valid = false;
    };
  }, [caseId, reviewId, summary?.version, summary?.status, revision]);
  const uploaded = async (review: Review, aiFailed: boolean) => {
    const next = await load(review.review_id);
    if (!mounted.current || liveCase.current !== caseId) return;
    setSelected({ caseId, reviewId: review.review_id });
    setQuery(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete("review_id");
        return next;
      },
      { replace: true },
    );
    setResult({ caseId, ...next, aiFailed });
    setNewUpload(undefined);
    setAllowAi(false);
    await refresh();
  };
  const analyse = () => {
    if (!visible || !allowAi || !visible.processing.consent_active) return;
    const id = visible.report.review_id;
    const body = {
      request_id: newRequestId(),
      expected_version: visible.report.review_version,
      allow_external_ai: true,
    };
    void action.run(async () => {
      let aiFailed = false;
      try {
        await aiPost(`/contract-reviews/${id}/ai-analyses`, body);
      } catch {
        aiFailed = true;
      }
      const next = await load(id);
      if (!mounted.current || liveCase.current !== caseId) return;
      setResult({ caseId, ...next, aiFailed });
      setAllowAi(false);
    });
  };
  if (invalidRequestedReview)
    return (
      <Alert
        type="error"
        message="This contract is not available in the current case."
        action={
          <Button
            onClick={() =>
              setQuery(
                (previous) => {
                  const next = new URLSearchParams(previous);
                  next.delete("review_id");
                  return next;
                },
                { replace: true },
              )
            }
          >
            View latest contract
          </Button>
        }
      />
    );
  if (!reviewId || newUpload === caseId)
    return (
      <ReviewUpload
        key={caseId}
        caseId={caseId}
        onReviewed={uploaded}
        onCancel={reviewId ? () => setNewUpload(undefined) : undefined}
      />
    );
  if (!visible)
    return (
      <>
        <Failure
          error={error}
          retry={() => setRevision((value) => value + 1)}
          showDetails={false}
        />
        {!error && <Loading />}
      </>
    );
  const { report, processing } = visible;
  const failed =
    visible.aiFailed ||
    ["failed", "unavailable"].includes(report.analysis.status);
  const retryAi =
    failed || ["not_run", "stale", "partial"].includes(report.analysis.status);
  return (
    <section
      className="simple-contract-review"
      aria-label="Contract review results"
      data-review-id={report.review_id}
    >
      <section className="panel contract-check-overview">
        <div className="contract-check-title">
          <div>
            <p className="muted contract-check-filename">
              {report.document_name}
            </p>
            <h2>Contract check results</h2>
          </div>
          <Button disabled={action.busy} onClick={() => setNewUpload(caseId)}>
            Upload another contract
          </Button>
        </div>
        <p>{report.summary}</p>
        <div className="contract-check-counts" aria-label="Check totals">
          <div>
            <strong>{report.total}</strong>
            <span>Checks</span>
          </div>
          <div>
            <strong>{report.attention.length}</strong>
            <span>Needs attention</span>
          </div>
          <div>
            <strong>{report.passed.length}</strong>
            <span>Passed</span>
          </div>
        </div>
        <Failure
          error={action.error || error}
          retry={error ? () => setRevision((value) => value + 1) : action.retry}
          showDetails={false}
        />
        {(failed ||
          report.analysis.status === "not_run" ||
          report.analysis.status === "stale") && (
          <Alert
            type={failed ? "warning" : "info"}
            showIcon
            title={
              failed
                ? "AI analysis did not complete"
                : report.analysis.status === "stale"
                  ? "AI analysis needs updating"
                  : "AI analysis has not run yet"
            }
            description="The available document checks are shown below. This is not a completed AI review."
          />
        )}
        {!processing.consent_active ? (
          <p className="muted">
            Processing permission is inactive. You can read these results or
            upload the contract again for a new AI review.
          </p>
        ) : (
          retryAi && (
            <div className="contract-check-retry">
              <Checkbox
                checked={allowAi}
                disabled={action.busy}
                onChange={(event) => setAllowAi(event.target.checked)}
              >
                I agree to send this contract to the AI service for this review.
              </Checkbox>
              <Button
                type="primary"
                loading={action.busy}
                disabled={!allowAi}
                onClick={analyse}
              >
                {failed ? "Try AI again" : "Analyse contract"}
              </Button>
            </div>
          )
        )}
      </section>
      <section
        className="panel contract-check-list"
        aria-label="Checks needing attention"
      >
        <h2>Needs attention ({report.attention.length})</h2>
        {report.attention.length ? (
          report.attention.map((check) => (
            <article className="contract-check-item" key={check.id}>
              <div className="contract-check-item-title">
                <h3>{check.label}</h3>
                <Tag color={check.status === "issue" ? "orange" : "default"}>
                  {check.status === "issue" ? "Issue found" : "To confirm"}
                </Tag>
              </div>
              {check.value != null && (
                <p className="contract-check-value">{checkValue(check)}</p>
              )}
              <p>{check.detail}</p>
              {check.question && (
                <p className="contract-check-question">
                  Ask your agent: {check.question}
                </p>
              )}
              <CheckSource check={check} />
            </article>
          ))
        ) : (
          <p>No issues found in the completed checks.</p>
        )}
      </section>
      <section className="panel contract-check-list" aria-label="Passed checks">
        <h2>Passed ({report.passed.length})</h2>
        <p className="muted small">
          These details were found in the contract or passed the check shown
          here.
        </p>
        {report.passed.length ? (
          report.passed.map((check) => (
            <article
              className="contract-check-item contract-check-passed"
              key={check.id}
            >
              <CheckCircleOutlined aria-hidden="true" />
              <div>
                <h3>{check.label}</h3>
                {check.value != null && <p>{checkValue(check)}</p>}
                <CheckSource check={check} />
              </div>
            </article>
          ))
        ) : (
          <p>No checks have passed yet.</p>
        )}
      </section>
      {processing.consent_active && (
        <div className="contract-check-permission">
          <Button
            type="link"
            disabled={action.busy}
            onClick={() => {
              const consentId = processing.consent_id;
              void action.run(async () => {
                await post(`/cases/${caseId}/contract-consents`, {
                  confirmed: false,
                  consent_id: consentId,
                });
                const next = await load(report.review_id);
                if (mounted.current && liveCase.current === caseId)
                  setResult({ caseId, ...next, aiFailed: false });
              });
            }}
          >
            Stop processing this contract
          </Button>
        </div>
      )}
    </section>
  );
}
