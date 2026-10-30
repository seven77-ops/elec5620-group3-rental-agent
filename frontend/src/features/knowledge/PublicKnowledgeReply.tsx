import { useEffect, useRef, useState } from "react";
import { Alert, Button } from "antd";
import { askKnowledge, type KnowledgeAnswer } from "../../api/knowledge";
import KnowledgeEvidence from "./KnowledgeEvidence";

/** Read-only presentation repair for old public messages; never rewrites conversation receipts. */
export default function PublicKnowledgeReply({
  caseId,
  answer,
  question,
}: {
  caseId: string;
  answer: KnowledgeAnswer;
  question: string;
}) {
  const [replacement, setReplacement] = useState<KnowledgeAnswer>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const epoch = useRef(0);
  useEffect(() => {
    epoch.current += 1;
    setReplacement(undefined);
    setBusy(false);
    setError(false);
    return () => {
      epoch.current += 1;
    };
  }, [caseId, answer]);
  const current = replacement ?? answer;
  const originalQuestion = answer.question || question;
  const language = "en";
  const isPublic =
    !answer.private_binding &&
    answer.scope !== "contract" &&
    answer.citations.length > 0 &&
    answer.citations.every((c) =>
      [
        "official_guidance",
        "official_template",
        "student_guidance",
        "product_guide",
      ].includes(c.source_type ?? ""),
    );
  const retryable =
    isPublic &&
    originalQuestion.trim() &&
    current.generation_outcome !== "local_only" &&
    (current.status === "sources_only" || current.source_preserving);
  async function retry() {
    const requestEpoch = ++epoch.current;
    setBusy(true);
    setError(false);
    try {
      const result = await askKnowledge(
        caseId,
        originalQuestion,
        true,
        language,
      );
      if (requestEpoch === epoch.current) setReplacement(result);
    } catch {
      if (requestEpoch === epoch.current) setError(true);
    } finally {
      if (requestEpoch === epoch.current) setBusy(false);
    }
  }
  return (
    <>
      <KnowledgeEvidence answer={current} showAnswer />
      {retryable && (
        <div className="knowledge-summary-retry">
          <p className="muted small">
            Sources were found, but the concise summary did not complete. Ask AI
            to summarise the public sources again.
          </p>
          <Button loading={busy} onClick={retry}>
            Summarise again
          </Button>
        </div>
      )}
      {error && (
        <Alert
          type="warning"
          showIcon
          title="Summary unavailable. You can retry or read the source excerpts."
        />
      )}
    </>
  );
}
