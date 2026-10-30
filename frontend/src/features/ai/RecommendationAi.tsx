import { Alert, Button, Checkbox, Space } from "antd";
import { useState } from "react";
import { aiPost, useAiResource, type AiAnalysis } from "../../api/ai";
import { newRequestId } from "../../api/client";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";
import AiCallDetails, { AiSetup } from "./AiCallDetails";
export default function RecommendationAi({
  runId,
  active,
}: {
  runId: string;
  active: boolean;
}) {
  const path = `/evaluations/${runId}/ai-explanations`;
  const { config, record, setRecord, loadError, reload } = useAiResource(path);
  const [consent, setConsent] = useState(false);
  const action = useAction();
  const generate = () => {
    const body = { request_id: newRequestId(), allow_external_ai: true };
    void action.run(async () =>
      setRecord(await aiPost<AiAnalysis>(path, body)),
    );
  };
  return (
    <section
      className="panel ai-panel"
      aria-label="AI recommendation explanation"
    >
      <div className="ai-title">
        <h2>AI recommendation explanation</h2>
        <span className="muted">
          Assisted explanation based on saved scores and evidence
        </span>
      </div>
      <p>
        AI explains recommendation reasons and cost/commute trade-offs.
        Eligibility, scores, and rankings continue to use the original
        assessment.
      </p>
      <AiSetup config={config} />
      <Checkbox
        checked={consent}
        disabled={action.busy || !active}
        onChange={(e) => setConsent(e.target.checked)}
      >
        I agree to send the preferences, scores, and evidence summary in this
        report to the configured model for recommendation explanation.
      </Checkbox>
      <Space wrap>
        <Button
          type="primary"
          disabled={!active || !consent || !config?.configured}
          loading={action.busy}
          onClick={generate}
          aria-label="Generate recommendation explanation"
        >
          Generate recommendation explanation
        </Button>
        <Button disabled={action.busy} onClick={reload}>
          Load latest AI explanation
        </Button>
      </Space>
      {!active && (
        <p className="muted">
          This report is not linked to the current confirmed preferences.
          Historical AI explanations remain readable. Switch to the latest
          report before generating one.
        </p>
      )}
      <Failure
        error={action.error || loadError}
        retry={
          loadError ? reload : consent && active ? action.retry : undefined
        }
      />
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
          {record.status === "skipped" && (
            <p>
              There are no eligible recommendations. No model was called. Adjust
              and confirm preferences first.
            </p>
          )}
          {record.result?.items?.map((item) => (
            <article className="ai-recommendation" key={item.listing_id}>
              <h3>{item.listing_id} · AI explanation</h3>
              <p>{item.text}</p>
              <p className="muted">
                Existing evidence cited: {item.evidence_refs.join(" · ")}
              </p>
            </article>
          ))}
          <AiCallDetails record={record} />
        </>
      )}
    </section>
  );
}
