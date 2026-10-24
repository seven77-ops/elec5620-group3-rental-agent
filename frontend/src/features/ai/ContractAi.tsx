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
          ? "已应用核对字段并保存新复核版本。"
          : "所选字段与现有值一致，无需新增版本。",
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
    <section className="panel ai-panel" aria-label="AI 合同辅助分析">
      <div className="ai-title">
        <h2>AI 合同辅助分析</h2>
        <span className="muted">候选提取、原文引用与差异解释</span>
      </div>
      <p>
        模型辅助提取租金、地址与起止日期。候选值需逐项核对，确认应用后更新复核结果。
      </p>
      <AiSetup config={config} />
      <Checkbox
        checked={consent}
        disabled={busy || !active}
        onChange={(e) => setConsent(e.target.checked)}
      >
        我同意将本合同文本及本次复核资料发送到配置的模型，用于本次 AI 辅助分析。
      </Checkbox>
      <Space wrap>
        <Button
          type="primary"
          disabled={
            !active || !consent || !config?.configured || applyAction.busy
          }
          loading={action.busy}
          onClick={generate}
          aria-label="AI 辅助分析合同"
        >
          AI 辅助分析合同
        </Button>
        <Button disabled={busy} onClick={reload}>
          读取最新 AI 分析
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
          独立合同同意未生效或当前选房已变化，AI 分析与应用暂停。
        </p>
      )}
      {record && (
        <>
          {record.error && (
            <Alert
              showIcon
              type="warning"
              title={record.error.message}
              description={`状态：${record.status} · ${record.error.code}`}
            />
          )}
          {stale && (
            <Alert
              showIcon
              type="warning"
              title="AI 候选对应的复核已变化，历史分析可读；请重新分析当前版本。"
            />
          )}
          {record.result && (
            <>
              <h3>AI 候选提取结果</h3>
              <p className="muted">
                分析对应复核 v{record.binding.review_version}
                。未知或未通过证据校验的字段保持待确认。
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
                        <strong>{field ? label(field) : "未知字段"}</strong>
                        <Tag color={usable ? "cyan" : "default"}>
                          {usable ? "原文校验通过" : "待确认"}
                        </Tag>
                      </div>
                      <p className="ai-candidate-value">
                        {candidate.value === null
                          ? "未确定"
                          : text(candidate.value)}
                      </p>
                      {candidate.evidence && (
                        <>
                          <p className="muted">
                            {candidate.evidence.source_name} · 第{" "}
                            {candidate.evidence.page} 页 · 原文第{" "}
                            {candidate.evidence.line} 行
                          </p>
                          <blockquote className="ai-quote">
                            {candidate.evidence.quote}
                          </blockquote>
                        </>
                      )}
                      {!usable && (
                        <p className="muted">
                          {candidate.reason === "unknown"
                            ? "模型未确定，需要人工核对。"
                            : (candidate.reason ?? "没有可核对的候选。")}
                        </p>
                      )}
                      {usable && field && (
                        <Checkbox
                          aria-label={`选择 AI 字段：${label(field)}`}
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
                          应用此字段
                        </Checkbox>
                      )}
                    </article>
                  );
                })}
              </div>
              <h3>按候选值预览的规则核对结果</h3>
              <p className="muted">
                下列为辅助预览，正式复核状态仍以当前已保存版本为准；人工审核由操作员流程处理。
              </p>
              {(record.result.preview_findings ?? []).length === 0 ? (
                <p>当前预览没有发现项，不额外生成风险解释。</p>
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
                        <p key={e.finding_id}>AI 解释：{e.text}</p>
                      ))}
                  </article>
                ))
              )}
              {record.result.explanation_status === "failed" && (
                <Alert
                  type="warning"
                  title="风险解释未完成，已校验的候选和原规则核对结果仍保留。"
                />
              )}
              <Checkbox
                checked={confirmed}
                disabled={
                  busy || !active || !record.can_apply || selected.length === 0
                }
                onChange={(e) => setConfirmed(e.target.checked)}
              >
                我已逐项核对所选字段的原文，确认应用到当前复核。
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
                aria-label="确认应用所选字段"
                onClick={apply}
              >
                确认应用所选字段
              </Button>
            </>
          )}
          <AiCallDetails record={record} />
        </>
      )}
    </section>
  );
}
