import { useEffect, useRef, useState } from "react";
import { Button, Checkbox, Input, Modal, Space } from "antd";
import { useCase } from "../../app/context";
import { askKnowledge } from "../../api/knowledge";
import type { KnowledgeAnswer } from "../../api/knowledge";
import { Failure } from "../../components/Common";
import KnowledgeEvidence from "./KnowledgeEvidence";
export default function KnowledgePanel() {
  const { current } = useCase();
  const [open, setOpen] = useState(false),
    [question, setQuestion] = useState("");
  const [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<KnowledgeAnswer | null>(null),
    [error, setError] = useState<unknown>(null);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++;
    setOpen(false);
    setQuestion("");
    setAnswer(null);
    setConsent(false);
    setBusy(false);
    setError(null);
  }, [current.case_id]);
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );
  const ask = async () => {
    const token = ++generation.current;
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      const result = await askKnowledge(current.case_id, question, consent);
      if (generation.current === token) setAnswer(result);
    } catch (e) {
      if (generation.current === token) setError(e);
    } finally {
      if (generation.current === token) setBusy(false);
    }
  };
  return (
    <>
      <Button onClick={() => setOpen(true)}>Ask rental knowledge</Button>
      <Button type="link" href="/api/v1/rag/product-guide" target="_blank" rel="noreferrer">User guide</Button>
      <Modal
        title="Rental knowledge"
        open={open}
        onCancel={() => setOpen(false)}
        footer={<Button onClick={() => setOpen(false)}>Close</Button>}
        width={760}
      >
        <p>
          English official sources for NSW renting, University of Sydney advice,
          and the product user guide. Private contracts use separate search and consent.
        </p>
        <Space orientation="vertical" style={{ width: "100%" }} size="middle">
          <Input.TextArea
            aria-label="Rental knowledge question"
            placeholder="e.g. How do I request repairs?"
            rows={3}
            maxLength={2000}
            value={question}
            disabled={busy}
            onChange={(e) => {
              setQuestion(e.target.value);
              setAnswer(null);
              setError(null);
            }}
          />
          <Checkbox
            checked={consent}
            disabled={busy}
            onChange={(e) => setConsent(e.target.checked)}
          >
            Allow this question and relevant public excerpts to be sent to the
            configured AI services.
          </Checkbox>
          <Button
            type="primary"
            loading={busy}
            disabled={!question.trim() || busy}
            onClick={() => void ask()}
          >
            {consent ? "Ask with AI" : "Find sources"}
          </Button>
          {busy && (
            <p role="status">Searching sources and checking citations…</p>
          )}
          <Failure error={error} />
          {answer && <KnowledgeEvidence answer={answer} showAnswer />}
        </Space>
      </Modal>
    </>
  );
}
