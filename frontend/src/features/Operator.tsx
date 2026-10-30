import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Form, Input, Select, Space, Tag } from "antd";
import { useNavigate } from "react-router-dom";
import { useCase } from "../app/context";
import { newRequestId, post } from "../api/client";
import { getOperatorReviews } from "../api/operator";
import type { OperatorReview } from "../api/operator";
import { Failure, money, PageTitle, Status, text } from "../components/Common";
import { useAction } from "../components/useAction";
import { sydneyTime } from "./aftercare/presentation";

const decisionNames: Record<string, string> = {
  annotate: "Comment",
  return: "Return for more information",
  hold: "Defer",
  refer: "Referral recommendation",
  release: "Checked; draft preparation may continue",
  approved: "Contract human review complete",
  returned: "Return contract for more information",
};

export default function Operator() {
  const { refresh } = useCase();
  const navigate = useNavigate();
  const [key, setKey] = useState("");
  const [items, setItems] = useState<OperatorReview[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const action = useAction();
  const { modal, message } = App.useApp();
  const generation = useRef(0);
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );
  const load = async () => {
    if (!key.trim()) return;
    const token = ++generation.current;
    setLoading(true);
    try {
      const result = await getOperatorReviews(key);
      if (token === generation.current) {
        setItems(result.items);
        setError(null);
      }
    } catch (e) {
      if (token === generation.current) {
        setItems(null);
        setError(e);
      }
    } finally {
      if (token === generation.current) setLoading(false);
    }
  };
  const decide = (item: OperatorReview, contractDecision?: string) => {
    void form
      .validateFields()
      .then((v) => {
        const decision = contractDecision ?? v.decision;
        // Freeze the exact request so a retry cannot silently use a new version or subject.
        const path =
          item.kind === "contract"
            ? `/contract-reviews/${item.review_id}/decisions`
            : "/aftercare/commands";
        const body =
          item.kind === "contract"
            ? { expected_version: item.version, decision, note: v.note }
            : {
                case_id: item.case_id,
                request_id: newRequestId(),
                expected_version: item.version,
                operation: "operator_decision",
                payload: {
                  review_id: item.review_id,
                  decision,
                  note: v.note,
                  gate_resolved: decision === "release",
                },
              };
        modal.confirm({
          title:
            item.kind === "contract"
              ? decision === "approve"
                ? "Complete contract human review?"
                : "Return contract for more information?"
              : `Record ${decisionNames[decision]} decision?`,
          content:
            item.kind === "contract"
              ? "Record a document review decision. This does not certify the contract or approve signing."
              : decision === "release"
                ? "Only removes this system restriction so factual inquiry drafts can continue. It does not decide deductions or refunds, or handle bond funds."
                : "Save review notes and retain restrictions. Referrals are recorded as recommendations; other organisations are not contacted automatically.",
          okText:
            item.kind === "contract"
              ? "Record human decision"
              : "Confirm record",
          cancelText: "Cancel",
          onOk: () =>
            action.run(async () => {
              await post(path, body, key);
              await refresh();
              await load();
              message.success("Review decision saved. History is preserved.");
            }),
        });
      })
      .catch(() => undefined);
  };
  const pending = (items ?? []).filter((item) => item.status === "open");
  const history = (items ?? []).filter((item) => item.status !== "open");
  const card = (item: OperatorReview) => (
    <article
      className="detail-row operator-review"
      key={`${item.kind}:${item.case_id}:${item.review_id}`}
      data-testid="operator-review"
    >
      <Space wrap>
        <Tag>
          {item.kind === "contract"
            ? "Contract review"
            : "Move-out and bond information"}
        </Tag>
        {item.status === "open" ? (
          <Tag color="gold">Awaiting human action</Tag>
        ) : (
          <Status value={item.status} />
        )}
        <strong>{item.address}</strong>
      </Space>
      <p>{item.reason}</p>
      <p className="small muted">
        Case: {item.case_id} · Submitted at {sydneyTime(item.created_at)}
      </p>
      {item.review?.findings.map((finding, i) => (
        <div key={i}>
          <strong>{text(finding.title)}</strong>
          <p>{text(finding.reason)}</p>
        </div>
      ))}
      {item.claims?.map((claim) => (
        <p key={String(claim.claim_id)}>
          Other party claim: {money(Number(claim.amount_cents) / 100)} ·{" "}
          {text(claim.reason)}
          {claim.disputed ? " · Disputed by tenant" : ""}
        </p>
      ))}
      {item.history?.map((entry) => (
        <p className="small" key={String(entry.entry_id)}>
          {sydneyTime(entry.occurred_at, false)}: {text(entry.text)}
        </p>
      ))}
      {item.kind === "aftercare" && (
        <p className="small">
          Registered evidence:
          {item.evidence?.length
            ? item.evidence.map((entry) => text(entry.summary)).join("; ")
            : "None yet. Add information as needed"}
        </p>
      )}
      {item.decisions.map((decision, i) => (
        <div key={i} className="operator-decision">
          <strong>
            {decisionNames[String(decision.decision ?? decision.status)] ??
              text(decision.decision ?? decision.status)}
          </strong>
          <p>{text(decision.note)}</p>
          <small>{sydneyTime(decision.at ?? decision.decided_at)}</small>
        </div>
      ))}
      <Space wrap>
        {item.status === "open" &&
          (item.kind === "contract" ? (
            <>
              <Button
                type="primary"
                disabled={!key || action.busy || loading}
                onClick={() => decide(item, "approve")}
                aria-label="Complete this human review"
              >
                Complete this human review
              </Button>
              <Button
                disabled={!key || action.busy || loading}
                onClick={() => decide(item, "return")}
              >
                Return for more information
              </Button>
            </>
          ) : (
            <Button
              disabled={!key || action.busy || loading}
              onClick={() => decide(item)}
              aria-label="Record selected review decision"
            >
              Record selected review decision
            </Button>
          ))}
        <Button
          onClick={() =>
            navigate(
              `/cases/${encodeURIComponent(item.case_id)}/${item.kind === "contract" ? "contract?mode=review" : "aftercare?tab=moveout"}`,
            )
          }
        >
          {item.kind === "contract"
            ? "View contract record"
            : "View aftercare record"}
        </Button>
      </Space>
    </article>
  );
  return (
    <>
      <PageTitle
        title="Human review"
        description="View document review submissions and history for cases on this device."
        extra={
          <Button
            disabled={!key || action.busy}
            loading={loading}
            onClick={() => void load()}
          >
            Load review records
          </Button>
        }
      />
      <Alert
        showIcon
        type="info"
        title="Review outcomes support document checks and the in-app process"
        description="They do not approve deductions or refunds, or handle bond funds. The operator key is kept only in this page memory."
      />
      <Failure
        error={action.error || error}
        retry={action.error ? action.retry : () => void load()}
      />
      <section className="panel">
        <Form
          form={form}
          layout="vertical"
          initialValues={{ decision: "refer" }}
        >
          <Form.Item label="Local operator key" htmlFor="local-operator-key">
            <Input.Password
              id="local-operator-key"
              value={key}
              autoComplete="off"
              disabled={action.busy}
              onChange={(e) => {
                generation.current++;
                setKey(e.target.value);
                action.clear();
                setItems(null);
                setError(null);
                setLoading(false);
              }}
            />
          </Form.Item>
          <Form.Item
            name="note"
            label="Human review notes"
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Enter the evidence and explanation for this decision",
              },
            ]}
          >
            <Input.TextArea rows={3} maxLength={1000} disabled={action.busy} />
          </Form.Item>
          <Form.Item name="decision" label="Aftercare review decision">
            <Select
              disabled={action.busy}
              options={[
                { value: "annotate", label: "Comment · Retain restrictions" },
                {
                  value: "return",
                  label: "Return for information · Retain restrictions",
                },
                { value: "hold", label: "Defer · Retain restrictions" },
                {
                  value: "refer",
                  label: "Referral recommendation · Retain restrictions",
                },
                {
                  value: "release",
                  label: "Checked · Allow draft preparation",
                },
              ]}
            />
          </Form.Item>
        </Form>
        {!items && !error && (
          <p className="muted">
            Enter the operator key, then select “Load review records” to view
            tasks and history.
          </p>
        )}
      </section>
      {items && (
        <>
          <section className="panel" aria-label="Human review queue">
            <h2>Pending items · {pending.length}</h2>
            {pending.length ? (
              pending.map(card)
            ) : (
              <p className="muted">No items awaiting human action.</p>
            )}
          </section>
          <section className="panel" aria-label="Review history">
            <h2>Review history · {history.length}</h2>
            {history.length ? (
              history.map(card)
            ) : (
              <p className="muted">
                No completed items yet. Completed records will be preserved
                here.
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
