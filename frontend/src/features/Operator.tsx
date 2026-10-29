import { useEffect, useState } from "react";
import { Alert, App, Button, Form, Input, Select, Space } from "antd";
import { useCase } from "../app/context";
import { api, newRequestId, post } from "../api/client";
import type { AftercareCase, Dict, Review } from "../api/types";
import {
  Failure,
  money,
  PageTitle,
  Status,
  text,
} from "../components/Common";
import { useAction } from "../components/useAction";
import { sydneyTime } from "./aftercare/presentation";
export default function Operator() {
  const { current, refresh } = useCase();
  const [key, setKey] = useState("");
  const [record, setRecord] = useState<AftercareCase | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [form] = Form.useForm();
  const action = useAction();
  const { modal, message } = App.useApp();
  const load = async () => {
    const [rs, m4] = await Promise.all([
      Promise.all(
        current.reviews.map((r) =>
          api<Review>(`/contract-reviews/${r.review_id}`),
        ),
      ),
      current.aftercare_case_id
        ? api<AftercareCase>(`/aftercare/cases/${current.aftercare_case_id}`)
        : Promise.resolve(null),
    ]);
    setReviews(rs);
    setRecord(m4);
  };
  useEffect(() => {
    void load().catch(setError);
  }, [current.reviews, current.aftercare_case_id]);
  const decide = (review: Review, decision: string) => {
    void form
      .validateFields()
      .then((v) => {
        modal.confirm({
          title:
            decision === "approve"
              ? "确认完成合同人工复核？"
              : "退回补充合同？",
          content: "这是本地演示操作员决定，不表示合同合法认证或签约批准。",
          okText: "记录人工决定",
          cancelText: "取消",
          onOk: () =>
            action.run(async () => {
              await post(
                `/contract-reviews/${review.review_id}/decisions`,
                { expected_version: review.version, decision, note: v.note },
                key,
              );
              await refresh();
              await load();
              message.success("人工决定已保存。");
            }),
        });
      })
      .catch(() => undefined);
  };
  const aftercareDecision = (r: Dict) => {
    void form
      .validateFields()
      .then((v) => {
        const decision = v.decision;
        const body = {
          case_id: current.case_id,
          request_id: newRequestId(),
          expected_version: record!.version,
          operation: "operator_decision",
          payload: {
            review_id: r.review_id,
            decision,
            note: v.note,
            gate_resolved: decision === "release",
          },
        };
        modal.confirm({
          title: `记录 ${decision} 决定？`,
          content:
            decision === "release"
              ? "仅在证据和门禁均已核对后解除该审核门禁，不裁定责任或退款。"
              : "该决定保留审核门禁。",
          okText: "确认记录",
          cancelText: "取消",
          onOk: () =>
            action.run(async () => {
              await post("/aftercare/commands", body, key);
              await refresh();
              await load();
              message.success("审核决定已保存。");
            }),
        });
      })
      .catch(() => undefined);
  };
  const pending = reviews.filter((r) => r.status === "Awaiting Human Review");
  const m4reviews = ((record?.reviews ?? []) as Dict[]).filter(
    (r) => r.status === "open",
  );
  return (
    <>
      <PageTitle
        title="本地演示操作员"
        description="人工决定使用服务器配置的演示身份，不代表生产登录或真实审核授权。"
        extra={
          <Button onClick={() => void load().catch(setError)}>
            读取最新待办
          </Button>
        }
      />
      <Alert
        showIcon
        type="info"
        title="需要本机配置的操作员密钥"
        description="在启动服务时设置 RENTAL_OPERATOR_KEY，再在此处输入。密钥仅保留在当前页面内存中，浏览器角色字段不能取得权限。"
      />
      <Failure error={action.error || error} retry={action.retry} />
      <section className="panel">
        <Form
          form={form}
          layout="vertical"
          initialValues={{ decision: "refer" }}
        >
          <Form.Item label="本地操作员密钥" htmlFor="local-operator-key">
            <Input.Password
              id="local-operator-key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="off"
            />
          </Form.Item>
          <Form.Item
            name="note"
            label="人工核对记录"
            rules={[{ required: true, message: "填写本次决定的依据与说明" }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="decision" label="押金审核决定">
            <Select
              options={[
                { value: "annotate", label: "批注 · 保留门禁" },
                { value: "return", label: "退回 · 保留门禁" },
                { value: "hold", label: "暂缓 · 保留门禁" },
                { value: "refer", label: "转交 · 保留门禁" },
                { value: "release", label: "已核对并解除门禁" },
              ]}
            />
          </Form.Item>
        </Form>
      </section>
      <section className="panel">
        <h2>合同人工复核</h2>
        {pending.length === 0 ? (
          <p className="muted">当前案例没有待人工复核的合同。</p>
        ) : (
          pending.map((r) => (
            <article className="detail-row" key={r.review_id}>
              <Status value={r.status} />
              <strong>
                {r.document.source_name} · v{r.version}
              </strong>
              {r.findings.map((f, i) => (
                <div key={i}>
                  <h3>{text(f.title)}</h3>
                  <p>{text(f.reason)}</p>
                  <ul className="plain-list">
                    {((f.evidence as Dict[] | undefined) ?? []).map((e, j) => (
                      <li key={j} className="small">
                        第{text(e.page)}页第{text(e.line)}行：「{text(e.quote)}」
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <Space wrap>
                <Button
                  type="primary"
                  disabled={!key}
                  loading={action.busy}
                  onClick={() => decide(r, "approve")}
                  aria-label="完成本次人工复核"
                >
                  完成本次人工复核
                </Button>
                <Button
                  disabled={!key || action.busy}
                  onClick={() => decide(r, "return")}
                >
                  退回补充
                </Button>
              </Space>
            </article>
          ))
        )}
      </section>
      <section className="panel">
        <h2>押金审核门禁</h2>
        {m4reviews.length === 0 ? (
          <p className="muted">当前案例没有未决押金审核事项。</p>
        ) : (
          m4reviews.map((r, i) => (
            <article className="detail-row" key={i}>
              <strong>{text(r.reason)}</strong>
              <p className="small muted">
                提交于 {sydneyTime(r.created_at)} · 引用：
                {((r.source_refs as string[]) ?? []).join("、") || "无"}
              </p>
              {(() => {
                const bond = (record?.bond ?? null) as Dict | null;
                const refs = new Set((r.source_refs as string[]) ?? []);
                const claims = ((bond?.claims ?? []) as Dict[]).filter((c) =>
                  refs.has(`claim:${c.claim_id}`),
                );
                const history = ((bond?.history ?? []) as Dict[]).slice(-3);
                const evidence = (record?.evidence ?? []) as Dict[];
                return (
                  <>
                    {claims.map((c) => (
                      <p key={String(c.claim_id)}>
                        对方主张：{money(Number(c.amount_cents) / 100)} ·{" "}
                        {text(c.reason)} · {c.disputed ? "租客有争议" : "未标记争议"}
                      </p>
                    ))}
                    {history.length > 0 && (
                      <>
                        <h4>最近的事实记录</h4>
                        <ul className="plain-list">
                          {history.map((h) => (
                            <li key={String(h.entry_id)} className="small">
                              {sydneyTime(h.occurred_at, false)}：{text(h.text)}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    <p className="small">
                      已登记证据：
                      {evidence.length
                        ? evidence
                            .map((e) => String(e.summary ?? e.evidence_id))
                            .join("；")
                        : "无（可请租客补充照片、收据或检查报告）"}
                    </p>
                    {((r.decisions as Dict[]) ?? []).map((d, j) => (
                      <p className="small" key={j}>
                        已记录：{text(d.decision)} · {text(d.note)}（
                        {sydneyTime(d.at)}）
                      </p>
                    ))}
                  </>
                );
              })()}
              <p className="muted small">
                可在核对记录中说明后续途径，例如与对方协商、通过 Rental Bonds
                Online 处理退款申请，或向 NSW Fair Trading / NCAT
                了解争议处理；这些仅为一般信息，不构成法律意见，由租客自行决定。
              </p>
              <Button
                disabled={!key}
                loading={action.busy}
                onClick={() => aftercareDecision(r)}
                aria-label="记录选定的审核决定"
              >
                记录选定的审核决定
              </Button>
            </article>
          ))
        )}
      </section>
    </>
  );
}
