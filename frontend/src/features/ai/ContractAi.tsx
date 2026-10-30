import { Alert, App, Button, Checkbox, Space, Tag } from "antd";
import { useEffect, useState } from "react";
import { aiPost, useAiResource, type AiAnalysis } from "../../api/ai";
import { newRequestId } from "../../api/client";
import type { Review } from "../../api/types";
import { Failure, label, text } from "../../components/Common";
import { useAction } from "../../components/useAction";
import AiCallDetails, { AiSetup } from "./AiCallDetails";
export default function ContractAi({
  review,
  active,
  onApplied,
}: {
  review: Review;
  active: boolean;
  onApplied: (review: Review) => Promise<void>;
}) {
  const path = `/contract-reviews/${review.review_id}/ai-analyses`;
  const { config, record, setRecord, loadError, reload } = useAiResource(path);
  const { message } = App.useApp();
  const [consent, setConsent] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const action = useAction(),
    applyAction = useAction();
  useEffect(() => {
    setSelected([]);
    setConfirmed(false);
    applyAction.clear();
    // Acknowledgment belongs to one immutable AI analysis, including manual reloads.
  }, [record?.analysis_id]);
  const busy = action.busy || applyAction.busy;
  const generate = () => {
    const body = {
      request_id: newRequestId(),
      expected_version: review.version,
      allow_external_ai: true,
    };
    void action.run(async () => {
      const next = await aiPost<AiAnalysis>(path, body);
      setRecord(next);
      setSelected([]);
      setConfirmed(false);
      applyAction.clear();
    });
  };
  const apply = () => {
    if (!record) return;
    const analysisId = record.analysis_id,
      previousVersion = review.version;
    const body = {
      request_id: newRequestId(),
      expected_version: previousVersion,
      confirmed: true,
      fields: [...selected],
    };
    void applyAction.run(async () => {
      const result = await aiPost<{ review: Review; analysis_id: string }>(
        `${path}/${analysisId}/apply`,
        body,
      );
      await onApplied(result.review);
      message.success(
        result.review.version > previousVersion
          ? "Checked fields applied and a new review version saved."
          : "Selected fields match the existing values. No new version is needed.",
      );
    });
  };
  const candidates = record?.result?.candidates ?? [];
  const stale =
    record &&
    (record.binding.review_version !== review.version ||
      record.status === "stale" ||
      (!record.can_apply &&
        record.status !== "failed" &&
        candidates.some((c) => c.valid)));
  return (
    <section className="panel ai-panel" aria-label="AI contract analysis">
      <div className="ai-title">
        <h2>AI contract analysis</h2>
        <span className="muted">
          Candidate extraction, source quotations, and difference explanations
        </span>
      </div>
      <p>
        AI helps extract rent, address, and lease dates. Check each candidate
        value. Confirming applies them and updates the review.
      </p>
      <AiSetup config={config} />
      <Checkbox
        checked={consent}
        disabled={busy || !active}
        onChange={(e) => setConsent(e.target.checked)}
      >
        I agree to send this contract text and review information to the
        configured model for this AI analysis.
      </Checkbox>
      <Space wrap>
        <Button
          type="primary"
          disabled={
            !active || !consent || !config?.configured || applyAction.busy
          }
          loading={action.busy}
          onClick={generate}
          aria-label="Analyse contract with AI"
        >
          Analyse contract with AI
        </Button>
        <Button disabled={busy} onClick={reload}>
          Load latest AI analysis
        </Button>
      </Space>
      <Failure
        error={action.error || loadError}
        retry={
          loadError ? reload : consent && active ? action.retry : undefined
        }
      />
      <Failure
        error={applyAction.error}
        retry={active && confirmed ? applyAction.retry : undefined}
      />
      {!active && (
        <p className="muted">
          Separate contract consent is inactive or the selected property has
          changed. AI analysis and field application are paused.
        </p>
      )}
      {record && (
        <>
          {record.error && (
            <Alert
              showIcon
              type="warning"
              title={record.error.message}
              description={`Status: ${record.status} · ${record.error.code}`}
            />
          )}
          {stale && (
            <Alert
              showIcon
              type="warning"
              title="The review linked to these AI candidates has changed. Historical analysis remains readable. Analyse the current version again."
            />
          )}
          {record.result && (
            <>
              <h3>AI candidate fields</h3>
              <p className="muted">
                Analysis for review v{record.binding.review_version}. Unknown
                fields or fields that failed evidence validation remain
                unconfirmed.
              </p>
              <div className="ai-candidates">
                {candidates.map((candidate, i) => {
                  const field = candidate.field;
                  const usable = Boolean(
                    field && candidate.valid && candidate.value !== null,
                  );
                  return (
                    <article className="ai-candidate" key={`${field}:${i}`}>
                      <div className="ai-candidate-heading">
                        <strong>
                          {field ? label(field) : "Unknown field"}
                        </strong>
                        <Tag color={usable ? "cyan" : "default"}>
                          {usable
                            ? "Source validation passed"
                            : "To be confirmed"}
                        </Tag>
                      </div>
                      <p className="ai-candidate-value">
                        {candidate.value === null
                          ? "Uncertain"
                          : text(candidate.value)}
                      </p>
                      {candidate.evidence && (
                        <>
                          <p className="muted">
                            {candidate.evidence.source_name} · Page{" "}
                            {candidate.evidence.page} · Source line{" "}
                            {candidate.evidence.line} line
                          </p>
                          <blockquote className="ai-quote">
                            {candidate.evidence.quote}
                          </blockquote>
                        </>
                      )}
                      {!usable && (
                        <p className="muted">
                          {candidate.reason === "unknown"
                            ? "The model could not determine this. Human review is needed."
                            : (candidate.reason ?? "No verifiable candidates.")}
                        </p>
                      )}
                      {usable && field && (
                        <Checkbox
                          aria-label={`Select AI field: ${label(field)}`}
                          checked={selected.includes(field)}
                          disabled={busy || !active || !record.can_apply}
                          onChange={(e) => {
                            setSelected((list) =>
                              e.target.checked
                                ? [...list, field]
                                : list.filter((x) => x !== field),
                            );
                            setConfirmed(false);
                            applyAction.clear();
                          }}
                        >
                          Apply this field
                        </Checkbox>
                      )}
                    </article>
                  );
                })}
              </div>
              <h3>Rule checks preview using candidate values</h3>
              <p className="muted">
                This is an assisted preview. The saved version remains the
                official review state. Human review is handled through the
                operator workflow.
              </p>
              {(record.result.preview_findings ?? []).length === 0 ? (
                <p>
                  The current preview has no findings. No additional risk
                  explanation is generated.
                </p>
              ) : (
                record.result.preview_findings?.map((finding) => (
                  <article className="ai-finding" key={finding.id}>
                    <strong>
                      {finding.id} · {text(finding.title)}
                    </strong>
                    <p>{finding.reason}</p>
                    {record.result?.explanations
                      ?.filter((e) => e.finding_id === finding.id)
                      .map((e) => (
                        <p key={e.finding_id}>AI explanation: {e.text}</p>
                      ))}
                  </article>
                ))
              )}
              {record.result.explanation_status === "failed" && (
                <Alert
                  type="warning"
                  title="Risk explanation could not be completed. Validated candidates and original rule checks are preserved."
                />
              )}
              <Checkbox
                checked={confirmed}
                disabled={
                  busy || !active || !record.can_apply || selected.length === 0
                }
                onChange={(e) => setConfirmed(e.target.checked)}
              >
                I have checked the source for each selected field and confirm
                applying them to the current review.
              </Checkbox>
              <Button
                type="primary"
                disabled={
                  !active ||
                  !record.can_apply ||
                  !confirmed ||
                  selected.length === 0 ||
                  action.busy
                }
                loading={applyAction.busy}
                aria-label="Confirm selected fields"
                onClick={apply}
              >
                Confirm selected fields
              </Button>
            </>
          )}
          <AiCallDetails record={record} />
        </>
      )}
    </section>
  );
}
