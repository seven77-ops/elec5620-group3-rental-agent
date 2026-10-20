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
    <section className="panel ai-panel" aria-label="AI 推荐解读">
      <div className="ai-title">
        <h2>AI 推荐解读</h2>
        <span className="muted">基于已保存评分与证据的辅助说明</span>
      </div>
      <p>
        模型解释推荐原因、费用与通勤取舍；房源资格、分数和排名继续使用原评估结果。
      </p>
      <AiSetup config={config} />
      <Checkbox
        checked={consent}
        disabled={action.busy || !active}
        onChange={(e) => setConsent(e.target.checked)}
      >
        我同意将本报告的偏好、评分及证据摘要发送到配置的模型，用于推荐解读。
      </Checkbox>
      <Space wrap>
        <Button
          type="primary"
          disabled={!active || !consent || !config?.configured}
          loading={action.busy}
          onClick={generate}
          aria-label="生成推荐解读"
        >
          生成推荐解读
        </Button>
        <Button disabled={action.busy} onClick={reload}>
          读取最新 AI 解读
        </Button>
      </Space>
      {!active && (
        <p className="muted">
          当前报告未绑定当前确认偏好；历史 AI 解读可读，请切换到最新报告后生成。
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
              description={`状态：${record.status} · ${record.error.code}`}
            />
          )}
          {record.status === "skipped" && (
            <p>当前没有合格推荐，本次未调用模型；请先调整并确认偏好。</p>
          )}
          {record.result?.items?.map((item) => (
            <article className="ai-recommendation" key={item.listing_id}>
              <h3>{item.listing_id} · AI 解读</h3>
              <p>{item.text}</p>
              <p className="muted">
                引用已有证据：{item.evidence_refs.join(" · ")}
              </p>
            </article>
          ))}
          <AiCallDetails record={record} />
        </>
      )}
    </section>
  );
}
