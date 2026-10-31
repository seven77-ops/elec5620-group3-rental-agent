import { Alert, App, Button, Checkbox, Space } from "antd";
import { useEffect, useState } from "react";
import { aiPost, useAiResource, type AiAnalysis } from "../../api/ai";
import { newRequestId } from "../../api/client";
import type { Review } from "../../api/types";
import { Failure, label, text } from "../../components/Common";
import { useAction } from "../../components/useAction";
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
          ? "Selected details saved and checked again."
          : "The selected details already match your saved contract.",
      );
    });
  };
  const candidates = (record?.result?.candidates ?? []).filter(
    (candidate) =>
      candidate.field && candidate.valid && candidate.value !== null,
  );
  const stale =
    record &&
    (record.binding.review_version !== review.version ||
      record.status === "stale" ||
      (!record.can_apply &&
        record.status !== "failed" &&
        candidates.some((c) => c.valid)));
  return (
    <section
      className="ai-panel contract-ai-check"
      aria-label="AI contract analysis"
    >
      <h2>Check details with AI</h2>
      <p>
        Use AI for a second look at the details read from your contract. Review
        any suggestions before saving.
      </p>
      {!config ? (
        <p className="muted" role="status">
          Checking availability…
        </p>
      ) : (
        !config.configured && (
          <Alert
            type="info"
            showIcon
            title="AI checking is currently unavailable"
            description="You can still read your review and edit the contract details yourself."
          />
        )
      )}
      <Checkbox
        checked={consent}
        disabled={busy || !active}
        onChange={(event) => setConsent(event.target.checked)}
      >
        I agree to send this contract to the AI service for this check.
      </Checkbox>
      <Space wrap>
        <Button
          type="primary"
          disabled={
            !active || !consent || !config?.configured || applyAction.busy
          }
          loading={action.busy}
          onClick={generate}
        >
          Analyse contract with AI
        </Button>
        {record && (
          <Button disabled={busy} onClick={reload}>
            Refresh AI suggestions
          </Button>
        )}
      </Space>
      <Failure
        error={action.error || loadError}
        retry={
          loadError ? reload : consent && active ? action.retry : undefined
        }
        showDetails={false}
      />
      <Failure
        error={applyAction.error}
        retry={active && confirmed ? applyAction.retry : undefined}
        showDetails={false}
      />
      {!active && (
        <p className="muted">
          Permission to process this contract is inactive. Your saved results
          remain available to read.
        </p>
      )}
      {record && (
        <>
          {(record.error || record.status === "failed") && (
            <Alert
              showIcon
              type="warning"
              title="AI could not confirm any changes"
              description="Your saved review is unchanged. You can edit the contract details yourself or try the AI check again."
            />
          )}
          {stale && (
            <Alert
              showIcon
              type="info"
              title="These suggestions are from an earlier review"
              description="Run AI analysis again before using them. Your saved contract details are shown in the review above."
            />
          )}
          {candidates.length > 0 && record.status !== "failed" && (
            <>
              <h3>Suggested details</h3>
              <p className="muted">
                Compare each suggestion with the quoted contract text. Only
                selected and confirmed details will be saved.
              </p>
              <div className="ai-candidates">
                {candidates.map((candidate, index) => {
                  const field = candidate.field!;
                  return (
                    <article className="ai-candidate" key={`${field}:${index}`}>
                      <strong>{label(field)}</strong>
                      <p className="ai-candidate-value">
                        {text(candidate.value)}
                      </p>
                      {candidate.evidence && (
                        <>
                          <p className="muted">
                            {candidate.evidence.source_name}
                            {candidate.evidence.page
                              ? ` · Page ${candidate.evidence.page}`
                              : ""}
                          </p>
                          <blockquote className="ai-quote">
                            {candidate.evidence.quote}
                          </blockquote>
                        </>
                      )}
                      <Checkbox
                        aria-label={`Use suggestion: ${label(field)}`}
                        checked={selected.includes(field)}
                        disabled={
                          busy || !active || !record.can_apply || Boolean(stale)
                        }
                        onChange={(event) => {
                          setSelected((list) =>
                            event.target.checked
                              ? [...list, field]
                              : list.filter((item) => item !== field),
                          );
                          setConfirmed(false);
                          applyAction.clear();
                        }}
                      >
                        Use this detail
                      </Checkbox>
                    </article>
                  );
                })}
              </div>
              {(record.result?.preview_findings ?? []).length > 0 && (
                <>
                  <h3>What these suggestions would change</h3>
                  {record.result?.preview_findings?.map((finding) => (
                    <article className="ai-finding" key={finding.id}>
                      <strong>{finding.title}</strong>
                      <p>{finding.reason}</p>
                      {record.result?.explanations
                        ?.filter((item) => item.finding_id === finding.id)
                        .map((item) => (
                          <p key={item.finding_id}>{item.text}</p>
                        ))}
                    </article>
                  ))}
                </>
              )}
              <Checkbox
                checked={confirmed}
                disabled={
                  busy ||
                  !active ||
                  !record.can_apply ||
                  Boolean(stale) ||
                  selected.length === 0
                }
                onChange={(event) => setConfirmed(event.target.checked)}
              >
                I have checked the original text and want to save the selected
                details.
              </Checkbox>
              <Button
                type="primary"
                disabled={
                  !active ||
                  !record.can_apply ||
                  Boolean(stale) ||
                  !confirmed ||
                  selected.length === 0 ||
                  action.busy
                }
                loading={applyAction.busy}
                onClick={apply}
              >
                Save selected details
              </Button>
            </>
          )}
          {!record.error &&
            record.status !== "failed" &&
            candidates.length === 0 && (
              <p className="muted">
                No suggested changes are available. Check your contract details
                in the review above.
              </p>
            )}
        </>
      )}
    </section>
  );
}
