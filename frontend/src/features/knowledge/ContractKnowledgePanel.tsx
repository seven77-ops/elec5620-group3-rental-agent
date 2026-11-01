import { useEffect, useRef, useState } from "react";
import { Alert, Button, Checkbox, Collapse, Input, Space, Tag } from "antd";
import {
  getContractKnowledge,
  indexContractKnowledge,
  forgetContractKnowledge,
  askContractKnowledge,
} from "../../api/contractKnowledge";
import type { ContractKnowledgeStatus } from "../../api/contractKnowledge";
import type { KnowledgeAnswer } from "../../api/knowledge";
import { Failure } from "../../components/Common";
import KnowledgeEvidence from "./KnowledgeEvidence";
export default function ContractKnowledgePanel({
  caseId,
  reviewId,
  reviewVersion,
  active,
  expanded = false,
}: {
  caseId: string;
  reviewId: string;
  reviewVersion: number;
  active: boolean;
  expanded?: boolean;
}) {
  const [status, setStatus] = useState<ContractKnowledgeStatus | null>(null),
    [error, setError] = useState<unknown>(null);
  const [localConsent, setLocalConsent] = useState(false),
    [cloudConsent, setCloudConsent] = useState(false),
    [useAi, setUseAi] = useState(false);
  const [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<KnowledgeAnswer | null>(null),
    [busy, setBusy] = useState(false);
  const epoch = useRef(0);
  useEffect(() => {
    const token = ++epoch.current;
    setStatus(null);
    setAnswer(null);
    setError(null);
    setLocalConsent(false);
    setCloudConsent(false);
    setUseAi(false);
    setQuestion("");
    setBusy(false);
    if (active)
      getContractKnowledge(caseId, reviewId)
        .then((v) => {
          if (epoch.current === token) setStatus(v);
        })
        .catch((e) => {
          if (epoch.current === token) setError(e);
        });
    return () => {
      epoch.current++;
    };
  }, [caseId, reviewId, reviewVersion, active]);
  const perform = async (task: () => Promise<void>) => {
    const token = epoch.current;
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (e) {
      if (epoch.current === token) setError(e);
    } finally {
      if (epoch.current === token) setBusy(false);
    }
  };
  const enable = () => {
    if (!status) return;
    const token = epoch.current;
    void perform(async () => {
      await indexContractKnowledge(caseId, reviewId, status, cloudConsent);
      const next = await getContractKnowledge(caseId, reviewId);
      if (epoch.current !== token) return;
      setStatus(next);
      setAnswer(null);
      setLocalConsent(false);
      setUseAi(false);
    });
  };
  const forget = () => {
    setAnswer(null);
    const token = ++epoch.current;
    void perform(async () => {
      await forgetContractKnowledge(caseId, reviewId);
      const next = await getContractKnowledge(caseId, reviewId);
      if (epoch.current !== token) return;
      setStatus(next);
      setAnswer(null);
      setLocalConsent(false);
      setUseAi(false);
    });
  };
  const ask = () => {
    if (!status) return;
    const token = epoch.current;
    void perform(async () => {
      const next = await askContractKnowledge(
        caseId,
        reviewId,
        status,
        question,
        useAi,
      );
      if (epoch.current === token) setAnswer(next);
    });
  };
  const permissionControls = (
    <Space orientation="vertical" size="middle">
      <Checkbox
        checked={localConsent}
        disabled={!active || busy || !status}
        onChange={(e) => setLocalConsent(e.target.checked)}
      >
        I agree to enable private search for this contract on this device.
      </Checkbox>
      <Checkbox
        checked={cloudConsent}
        disabled={!active || busy || !status}
        onChange={(e) => setCloudConsent(e.target.checked)}
      >
        I also allow the AI service to process this contract for search and
        answers.
      </Checkbox>
      <Space wrap>
        <Button
          aria-label={
            status?.status === "ready"
              ? "Update search permissions"
              : "Enable contract search"
          }
          disabled={!active || busy || !status || !localConsent}
          loading={busy}
          onClick={enable}
        >
          {status?.status === "ready"
            ? "Update search permissions"
            : "Enable contract search"}
        </Button>
        {status?.status === "ready" && (
          <Button danger onClick={forget}>
            Turn off contract search
          </Button>
        )}
      </Space>
    </Space>
  );
  return (
    <Collapse
      defaultActiveKey={expanded ? ["contract-knowledge"] : []}
      items={[
        {
          key: "contract-knowledge",
          label: "Ask more about this contract",
          children: (
            <section aria-label="Private contract Q&A">
              <p>
                Ask about rent, bond, cleaning or other clauses. Check the
                quoted contract text alongside each answer.
              </p>
              {!active && (
                <Alert
                  type="info"
                  title="Confirm that processing consent for this contract is still valid first."
                />
              )}
              {status && (
                <p>
                  <Tag color={status.status === "ready" ? "blue" : "default"}>
                    {status.status === "ready"
                      ? "Contract search ready"
                      : ((
                          {
                            not_enabled: "Not enabled",
                            indexing: "Preparing search",
                            needs_reindex: "Refresh needed",
                            revoked: "Revoked",
                            failed: "Search could not be prepared",
                          } as Record<string, string>
                        )[status.status] ?? status.status)}
                  </Tag>
                  {status.source_name} · {status.page_count} pages
                </p>
              )}
              <Space
                orientation="vertical"
                size="middle"
                style={{ width: "100%" }}
              >
                {status?.status === "ready" ? (
                  <Collapse
                    className="full-width"
                    items={[
                      {
                        key: "permissions",
                        label: "Search permissions",
                        children: permissionControls,
                      },
                    ]}
                  />
                ) : (
                  permissionControls
                )}
                {!!status?.warnings.length && (
                  <Alert type="info" title={status.warnings.join(" ")} />
                )}
                <Input.TextArea
                  aria-label="Contract question"
                  placeholder="For example: What does the contract say about cleaning?"
                  rows={3}
                  maxLength={2000}
                  value={question}
                  disabled={busy || status?.status !== "ready"}
                  onChange={(e) => {
                    setQuestion(e.target.value);
                    setAnswer(null);
                  }}
                />
                <Checkbox
                  checked={useAi}
                  disabled={
                    busy ||
                    status?.status !== "ready" ||
                    !status.allow_external_ai
                  }
                  onChange={(e) => setUseAi(e.target.checked)}
                >
                  Allow AI to process this question and relevant contract text
                  for this request.
                </Checkbox>
                <Button
                  aria-label={
                    useAi ? "Explain contract with AI" : "Find contract text"
                  }
                  type="primary"
                  disabled={
                    busy || !question.trim() || status?.status !== "ready"
                  }
                  loading={busy}
                  onClick={ask}
                >
                  {useAi ? "Explain contract with AI" : "Find contract text"}
                </Button>
                {busy && <p role="status">Finding relevant contract text…</p>}
                <Failure error={error} showDetails={false} />
                {answer && <KnowledgeEvidence answer={answer} showAnswer />}
              </Space>
            </section>
          ),
        },
      ]}
    />
  );
}
