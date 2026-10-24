import { Alert, Collapse, Tag } from "antd";
import type { AiAnalysis, AiConfig } from "../../api/ai";
const tasks: Record<string, string> = {
  contract_extract: "合同字段提取",
  contract_explain: "差异风险解释",
  recommendation_explain: "推荐解读",
};
const states: Record<string, string> = {
  succeeded: "请求成功",
  failed: "请求失败",
  not_configured: "未配置，未调用模型",
};
export function AiSetup({ config }: { config: AiConfig | null }) {
  if (!config) return <p className="muted">正在读取模型配置状态…</p>;
  return (
    <>
      <p className="muted">
        模型：{config.model ?? "尚未配置"} · 每个请求超时{" "}
        {config.timeout_seconds} 秒
      </p>
      {!config.configured && (
        <Alert
          type="info"
          showIcon
          title="模型 API 尚未开启或配置完整"
          description="请按本地 AI 运行说明在后端填写 .env 并重启。密钥不需要输入网页；当前规则流程仍可正常使用。"
        />
      )}
      {config.provider === "test_stub" && (
        <Alert
          type="warning"
          showIcon
          title="测试替身模式"
          description="此页面用于本地自动化验证，返回内容不是实际大模型生成。"
        />
      )}
    </>
  );
}
export default function AiCallDetails({ record }: { record: AiAnalysis }) {
  return (
    <Collapse
      items={[
        {
          key: "calls",
          label: "本次 AI 调用",
          children: (
            <>
              <p className="muted">
                分析 {record.analysis_id} · {record.created_at}
              </p>
              {record.calls.length === 0 ? (
                <p>本次没有发起模型请求。</p>
              ) : (
                record.calls.map((call, i) => (
                  <article className="ai-call" key={i}>
                    <strong>{tasks[call.task] ?? call.task}</strong>{" "}
                    <Tag>{states[call.status] ?? call.status}</Tag>
                    <p>
                      服务来源：<span>{call.provider}</span>
                      {call.simulated && " · 测试替身，未调用真实模型"}
                    </p>
                    <p>
                      模型：{call.model ?? "未配置"} · 耗时：{call.duration_ms}{" "}
                      ms
                    </p>
                    <p>开始时间：{call.started_at}</p>
                    {!call.attempted && <p>未向外部模型发送请求。</p>}
                    {call.error_code && <p>错误代码：{call.error_code}</p>}
                    {call.provider_request_id && (
                      <p>服务请求 ID：{call.provider_request_id}</p>
                    )}
                    {call.provider_response_id && (
                      <p>服务响应 ID：{call.provider_response_id}</p>
                    )}
                    {call.usage && (
                      <p>
                        服务返回用量：
                        {Object.entries(call.usage)
                          .map(([key, value]) => `${key}: ${value}`)
                          .join(" · ")}
                      </p>
                    )}
                  </article>
                ))
              )}
              <p className="muted">
                请求成功表示收到模型响应；字段、引用和业务规则仍由后端继续校验。
              </p>
            </>
          ),
        },
      ]}
    />
  );
}
