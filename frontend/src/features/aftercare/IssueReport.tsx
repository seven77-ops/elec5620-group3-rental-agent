import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button,
  Collapse,
  Empty,
  Form,
  Input,
  Select,
  Space,
  Tabs,
  Tag,
} from "antd";
import { useSearchParams } from "react-router-dom";
import { useCase } from "../../app/context";
import { newRequestId } from "../../api/client";
import { getIssueReports, submitIssueReport } from "../../api/issueReports";
import type { OperatorReview } from "../../api/operator";
import { Failure, money } from "../../components/Common";
import { useAction } from "../../components/useAction";
import ReviewEvidenceUpload, { emptyEvidence } from "./ReviewEvidenceUpload";
import ReviewEvidence from "./ReviewEvidence";
import {
  issueCategories,
  reportCategories,
  reviewState,
} from "./issuePresentation";
import { sydneyTime } from "./presentation";

export default function IssueReport() {
  const { current } = useCase();
  const [query, setQuery] = useSearchParams();
  const [form] = Form.useForm();
  const action = useAction();
  const [upload, setUpload] = useState(emptyEvidence);
  const [uploadKey, setUploadKey] = useState(0);
  const [items, setItems] = useState<OperatorReview[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const generation = useRef(0);
  const mounted = useRef(false);
  const [tab, setTab] = useState(
    ["history", "review"].includes(query.get("section") ?? "")
      ? "history"
      : "report",
  );
  const changeTab = (value: string) => {
    setTab(value);
    setQuery(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("section", value);
        return next;
      },
      { replace: true },
    );
  };
  const load = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true);
    try {
      const result = await getIssueReports();
      if (mounted.current && token === generation.current) {
        setItems(result.items);
        setError(null);
        return true;
      }
      return false;
    } catch (error) {
      if (token === generation.current) setError(error);
      return false;
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      generation.current++;
    };
  }, [load]);
  const submit = async () => {
    if (action.busy || upload.busy || !upload.ready || action.error) return;
    try {
      const values = await form.validateFields();
      const body = {
        request_id: newRequestId(),
        category: values.category,
        description: values.description,
        attachment_ids: upload.files.map((file) => file.attachment_id),
      };
      let committed = false;
      await action.run(async () => {
        if (!committed) {
          await submitIssueReport(current.case_id, body);
          committed = true;
        }
        if (!mounted.current) return;
        const loaded = await load();
        if (!mounted.current) return;
        if (!loaded)
          throw new Error("Report submitted. Retry to refresh your history.");
        form.resetFields();
        setUpload(emptyEvidence);
        setUploadKey((value) => value + 1);
        changeTab("history");
      });
    } catch {
      /* Inline validation; preserve the original description and selected files. */
    }
  };
  const locked = action.busy || upload.busy || Boolean(action.error);
  return (
    <Tabs
      className="issue-report-tabs"
      activeKey={tab}
      onChange={changeTab}
      items={[
        {
          key: "report",
          label: "Report issue",
          children: (
            <section
              className="panel flat-issue-form"
              aria-label="Report issue"
            >
              <Form form={form} layout="vertical" disabled={locked}>
                <Form.Item
                  name="category"
                  label="Issue type"
                  rules={[{ required: true, message: "Choose an issue type." }]}
                >
                  <Select
                    virtual={false}
                    placeholder="Choose an issue type"
                    options={Object.entries(reportCategories).map(
                      ([value, label]) => ({ value, label }),
                    )}
                  />
                </Form.Item>
                <Form.Item
                  name="description"
                  label="Issue description"
                  rules={[
                    {
                      required: true,
                      whitespace: true,
                      message: "Describe the issue.",
                    },
                  ]}
                >
                  <Input.TextArea
                    rows={7}
                    maxLength={5000}
                    showCount
                    placeholder="Describe the problem and what happened."
                  />
                </Form.Item>
              </Form>
              <ReviewEvidenceUpload
                key={uploadKey}
                caseId={current.case_id}
                onChange={setUpload}
                disabled={action.busy || Boolean(action.error)}
              />
              <Space wrap>
                <Button
                  type="primary"
                  loading={action.busy}
                  disabled={locked || !upload.ready}
                  onClick={() => void submit()}
                >
                  Submit report
                </Button>
                <span className="muted small">
                  The submission date is recorded automatically.
                </span>
              </Space>
              <Failure error={action.error} retry={action.retry} />
            </section>
          ),
        },
        {
          key: "history",
          label: "History",
          children: (
            <section
              className="issue-report-history"
              aria-label="Issue report history"
            >
              <div className="issue-history-actions">
                <Button loading={loading} onClick={() => void load()}>
                  Refresh history
                </Button>
              </div>
              <Failure error={error} retry={() => void load()} />
              {!loading && !items.length ? (
                <div className="panel">
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="No reports submitted yet"
                  />
                </div>
              ) : (
                items.map((item) => {
                  const state = reviewState({
                    status: item.status,
                    decisions: item.decisions,
                    updates: item.updates ?? [],
                  });
                  const report = item.report!;
                  return (
                    <article
                      className="panel issue-history-card"
                      key={`${item.kind}:${item.case_id}:${item.review_id}`}
                    >
                      <div className="section-heading">
                        <Space wrap>
                          <Tag>
                            {issueCategories[
                              report.category as keyof typeof issueCategories
                            ] ?? String(report.category)}
                          </Tag>
                          <Tag color={state.color}>{state.label}</Tag>
                        </Space>
                        <span className="muted small">
                          {sydneyTime(item.created_at)}
                        </span>
                      </div>
                      {item.kind !== "issue" && report.title && (
                        <h3>{String(report.title)}</h3>
                      )}
                      <p className="preserve-text">
                        {String(report.description)}
                      </p>
                      <ReviewEvidence files={item.attachments ?? []} />
                      {item.kind !== "issue" &&
                        Boolean(
                          report.requested_outcome ||
                          report.amount_cents != null ||
                          item.evidence?.length,
                        ) && (
                          <Collapse
                            ghost
                            size="small"
                            items={[
                              {
                                key: "original",
                                label: "Original report details",
                                children: (
                                  <>
                                    {report.requested_outcome && (
                                      <p className="preserve-text">
                                        <strong>Requested help: </strong>
                                        {String(report.requested_outcome)}
                                      </p>
                                    )}
                                    {report.amount_cents != null && (
                                      <p>
                                        Amount reported:{" "}
                                        {money(
                                          Number(report.amount_cents) / 100,
                                        )}
                                      </p>
                                    )}
                                    {item.evidence?.map((source) => (
                                      <p
                                        className="preserve-text"
                                        key={String(source.evidence_id)}
                                      >
                                        {String(source.summary)} ·{" "}
                                        {String(source.source_ref)}
                                      </p>
                                    ))}
                                  </>
                                ),
                              },
                            ]}
                          />
                        )}

                      {item.updates?.map((update, i) => (
                        <p className="preserve-text" key={i}>
                          {String(update.text)}
                        </p>
                      ))}
                      {item.decisions.map((decision, i) => (
                        <div className="review-saved-advice" key={i}>
                          <strong>Review advice</strong>
                          <p className="preserve-text">
                            {String(decision.note)}
                          </p>
                        </div>
                      ))}
                    </article>
                  );
                })
              )}
            </section>
          ),
        },
      ]}
    />
  );
}
