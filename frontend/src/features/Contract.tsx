import { useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
} from "antd";
import { useCase, currentConfirmation } from "../app/context";
import { api, downloadUrl, post } from "../api/client";
import type { Dict, Evidence, Review } from "../api/types";
import {
  Blank,
  EvidenceDrawer,
  Failure,
  JsonDetails,
  label,
  PageTitle,
  Status,
  text,
} from "../components/Common";
import { useAction } from "../components/useAction";
import ContractUpload from "./ContractUpload";
import ContractAi from "./ai/ContractAi";
import ReviewHistory from "./ReviewHistory";
import ContractComparison from "./candidate/ContractComparison";
import type { RealContractContext } from "../api/followup";
export default function Contract({ embedded = false }: { embedded?: boolean }) {
  const { current, refresh, go } = useCase();
  const { message } = App.useApp();
  const action = useAction();
  const [selectedReview, setSelectedReview] = useState<string | undefined>();
  const [loadedReview, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [source, setSource] = useState<Evidence | null>(null);
  const [correct, setCorrect] = useState(false);
  const [correctionForm] = Form.useForm();
  const ref = selectedReview ?? current.reviews.at(-1)?.review_id;
  const selectedContext = useRef({ caseId: current.case_id, reviewId: ref });
  selectedContext.current = { caseId: current.case_id, reviewId: ref };
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const review = loadedReview?.review_id === ref ? loadedReview : null;
  const [consentRevision, setConsentRevision] = useState(0);
  const [reviewConsent, setReviewConsent] = useState<{
    consent_id: string | null;
    consent_active: boolean;
    real_context?: RealContractContext | null;
  } | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const consentChanged = () => setConsentRevision((v) => v + 1);
  const summary = current.reviews.find((r) => r.review_id === ref);
  const currentSelection =
    current.selection?.profile_version ===
    currentConfirmation(current)?.version;
  useEffect(() => {
    if (!ref) return;
    let valid = true;
    setReviewConsent(null);
    setError(null);
    setSource(null);
    Promise.all([
      api<Review>(`/contract-reviews/${ref}`),
      api<{
        consent_id: string | null;
        consent_active: boolean;
        real_context?: RealContractContext | null;
      }>(`/contract-reviews/${ref}/context`),
    ])
      .then(([r, context]) => {
        if (valid) {
          setReview(r);
          setReviewConsent(context);
          setError(null);
        }
      })
      .catch((e) => {
        if (valid) setError(e);
      });
    return () => {
      valid = false;
    };
  }, [ref, summary?.version, summary?.status, consentRevision]);
  const questions = () => {
    if (!review) return;
    const id = review.review_id,
      body = { expected_version: review.version };
    void action.run(async () => {
      const r = await post<Review>(`/contract-reviews/${id}/questions`, body);
      setReview(r);
      await refresh();
    });
  };
  const saveCorrection = async () => {
    try {
      const corrections = await correctionForm.validateFields();
      if (!review) return;
      const id = review.review_id,
        body = { expected_version: review.version, corrections };
      void action.run(async () => {
        const r = await post<Review>(
          `/contract-reviews/${id}/corrections`,
          body,
        );
        setReview(r);
        setCorrect(false);
        await refresh();
        message.success("新复核版本已保存，旧问题已失效。");
      });
    } catch {
      /* Inline form validation. */
    }
  };
  const findings = review?.findings ?? [];
  const questionList = Array.isArray(review?.questions) ? review.questions : [];
  return (
    <>
      {!embedded && (
        <PageTitle
          title="合同复核"
          description="将合同事实与所选房源交叉核对，查看每项结果的原文依据。"
          extra={
            current.reviews.length > 0 ? (
              <Select
                aria-label="选择合同复核记录"
                value={ref}
                onChange={setSelectedReview}
                options={current.reviews.map((r, i) => ({
                  value: r.review_id,
                  label: `合同 ${i + 1} · v${r.version}`,
                }))}
              />
            ) : undefined
          }
        />
      )}
      {embedded && current.reviews.length > 0 && (
        <Select
          aria-label="选择合同复核记录"
          value={ref}
          onChange={setSelectedReview}
          options={current.reviews.map((r, i) => ({
            value: r.review_id,
            label: `合同 ${i + 1} · v${r.version}`,
          }))}
        />
      )}
      <Failure
        error={action.error || error}
        retry={error ? consentChanged : action.retry}
      />
      {current.selection ? (
        <section className="selection-strip">
          <div>
            <span>已选房源</span>
            <strong>
              {current.selection.data_mode === "real_listings"
                ? text(current.selection.listing_snapshot.address)
                : current.selection.listing_id}
            </strong>
            <p>
              {current.selection.data_mode === "real_listings"
                ? `房源 AUD ${text(current.selection.listing_snapshot.weekly_rent)}/周 · 计价对象待确认`
                : text(current.selection.listing_snapshot.address)}
            </p>
          </div>
          <Button onClick={() => go("recommendations")}>查看选房依据</Button>
        </section>
      ) : (
        <Blank
          text="请先保存一套房源候选，再上传合同核对。"
          action={
            <Button onClick={() => go("recommendations")}>前往房源推荐</Button>
          }
        />
      )}
      {current.selection && !currentSelection && (
        <Alert
          type="warning"
          showIcon
          title="当前选房来自旧偏好版本"
          description="请先按当前确认偏好重新评估并选择房源。历史合同结果仍然保留。"
        />
      )}
      {current.selection?.data_mode === "real_listings" && (
        <Alert
          type="info"
          showIcon
          title="可以直接复核已有合同"
          description="房源房源仍是待核实快照。合同先在本地提取，与房源及补充记录分别比对。"
        />
      )}
      {current.selection && (
        <ContractUpload
          revision={consentRevision}
          onConsentChange={consentChanged}
          onReview={(r) => {
            setReview(r);
            setSelectedReview(r.review_id);
            consentChanged();
          }}
        />
      )}
      {review && (
        <>
          <ContractAi
            key={`${review.review_id}:${review.version}:${Boolean(reviewConsent?.consent_active)}`}
            review={review}
            active={Boolean(reviewConsent?.consent_active)}
            onApplied={async (next) => {
              // Apply can finish after selecting another review or leaving this
              // page. Only the current owner may update its view or refresh.
              if (
                !mounted.current ||
                selectedContext.current.caseId !== current.case_id ||
                selectedContext.current.reviewId !== next.review_id
              )
                return;
              // A reload or another saved action may have replaced this exact
              // source object, including changes that keep the same version.
              setReview((previous) => (previous === review ? next : previous));
              await refresh();
            }}
          />
          <section className="review-status">
            <div>
              <Status value={review.status} />
              <strong>复核版本 v{review.version}</strong>
              <p>
                {review.status_reason ??
                  "请结合提取字段、来源及发现项核对合同。复核完成不表示签约批准。"}
              </p>
            </div>
            <Space wrap>
              <Button onClick={() => setHistoryOpen(true)}>
                查看历史复核版本
              </Button>
              <Button onClick={consentChanged}>读取最新复核状态</Button>
              <Button
                disabled={!reviewConsent?.consent_active}
                onClick={() => {
                  correctionForm.setFieldsValue(
                    Object.fromEntries(
                      Object.entries(review.fields)
                        .filter(([key]) =>
                          [
                            "address",
                            "rent_amount",
                            "bond",
                            "start_date",
                            "end_date",
                          ].includes(key),
                        )
                        .map(([key, f]) => [key, f.value]),
                    ),
                  );
                  setCorrect(true);
                }}
              >
                修正提取字段
              </Button>
              <a
                href={downloadUrl(
                  `/contract-reviews/${review.review_id}/export`,
                )}
              >
                下载复核 JSON
              </a>
            </Space>
          </section>
          {!reviewConsent?.consent_active && (
            <Alert
              type="warning"
              showIcon
              title="本次复核处理同意未生效或上下文已变化"
              description="历史结果可读，后续分析与修改暂停。需要继续处理时，请核对选房并重新同意、提交合同。"
            />
          )}
          {reviewConsent?.consent_active && (
            <div className="consent-actions">
              <Button
                disabled={action.busy}
                onClick={() => {
                  const consentId = reviewConsent.consent_id;
                  void action.run(async () => {
                    await post(`/cases/${current.case_id}/contract-consents`, {
                      confirmed: false,
                      consent_id: consentId,
                    });
                    consentChanged();
                  });
                }}
              >
                撤销本次复核处理同意
              </Button>
            </div>
          )}
          {reviewConsent?.real_context && (
            <ContractComparison context={reviewConsent.real_context} />
          )}
          <div className="contract-result">
            <section className="panel">
              <h2>合同提取字段</h2>
              <Descriptions
                column={1}
                size="small"
                items={Object.entries(review.fields).map(([key, field]) => ({
                  key,
                  label: label(key),
                  children: (
                    <div className="field-value">
                      <span>{text(field.value)}</span>
                      {field.evidence && (
                        <Button
                          type="link"
                          size="small"
                          onClick={() => setSource(field.evidence!)}
                        >
                          查看原文
                        </Button>
                      )}
                    </div>
                  ),
                }))}
              />
            </section>
            <section className="panel">
              <h2>发现与待办</h2>
              {findings.length === 0 ? (
                <p className="muted">当前复核没有发现项，不生成额外问题。</p>
              ) : (
                findings.map((finding, i) => (
                  <article className="finding" key={i}>
                    <Space>
                      <Status
                        value={
                          String(finding.severity) === "high"
                            ? "Awaiting Human Review"
                            : String(finding.severity)
                        }
                      />
                      <strong>{text(finding.title)}</strong>
                    </Space>
                    <p>{text(finding.reason)}</p>
                    {Array.isArray(finding.evidence) && (
                      <Space wrap>
                        {(finding.evidence as Dict[]).map((e, j) => (
                          <Button
                            type="link"
                            size="small"
                            key={j}
                            onClick={() => setSource(e as Evidence)}
                          >
                            依据 {j + 1}
                          </Button>
                        ))}
                      </Space>
                    )}
                    {typeof finding.rule_url === "string" &&
                      /^https:\/\//.test(finding.rule_url) && (
                        <p>
                          <a
                            href={finding.rule_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            查看引用规则
                          </a>{" "}
                          · {text(finding.rule_version)}
                        </p>
                      )}
                  </article>
                ))
              )}
              {review.status === "Awaiting Human Review" && (
                <Alert
                  type="warning"
                  showIcon
                  title="等待本地演示操作员处理"
                  description="租客不能放行高风险发现，人工决定前问题生成功能保持不可用。"
                />
              )}
              <div className="consent-actions">
                <Button
                  disabled={
                    !reviewConsent?.consent_active ||
                    !["Reviewed", "Questions Ready"].includes(review.status) ||
                    findings.length === 0
                  }
                  onClick={questions}
                  loading={action.busy}
                  aria-label="准备问题清单"
                >
                  准备问题清单
                </Button>
              </div>
              {questionList.length > 0 && (
                <>
                  <h3>问题清单 · 尚未发送</h3>
                  <a
                    href={downloadUrl(
                      `/contract-reviews/${review.review_id}/questions/export`,
                    )}
                  >
                    下载问题清单
                  </a>
                  {questionList.map((q, i) => (
                    <div className="detail-row" key={i}>
                      <p>{text(q.text)}</p>
                      <small>
                        发现 {text(q.finding_id)} · 复核版本{" "}
                        {text(q.review_version)}
                      </small>
                    </div>
                  ))}
                </>
              )}
            </section>
          </div>
          <Collapse
            items={[
              {
                key: "trace",
                label: "复核引用与版本历史",
                children: (
                  <JsonDetails
                    value={{
                      review_id: review.review_id,
                      version: review.version,
                      document: review.document,
                      intake: review.intake,
                      revisions: review.revisions,
                      events: review.events,
                    }}
                  />
                ),
              },
            ]}
          />
          <div className="next-action compact">
            <div>
              <h2>继续租后服务</h2>
              <p>先补齐并确认租约资料。合同复核结果只作为候选事实来源。</p>
            </div>
            <Button onClick={() => go("aftercare")}>确认租约资料</Button>
          </div>
        </>
      )}
      {review && (
        <ReviewHistory
          reviewId={review.review_id}
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
        />
      )}
      <EvidenceDrawer
        title="合同原文依据"
        open={Boolean(source)}
        onClose={() => setSource(null)}
      >
        {source && (
          <>
            <p className="muted">
              {source.source_name ?? source.source_ref} · 第{" "}
              {source.page ?? "—"} 页 · 第 {source.line ?? "—"} 行
            </p>
            <blockquote className="source-quote">
              {source.quote ?? "该引用未提供可定位引文，请核对完整来源。"}
            </blockquote>
            <JsonDetails value={source} />
          </>
        )}
      </EvidenceDrawer>
      <Modal
        open={correct}
        title="修正提取字段"
        okText="保存为新复核版本"
        cancelText="取消"
        onCancel={() => setCorrect(false)}
        onOk={saveCorrection}
        confirmLoading={action.busy}
      >
        <p>仅修正实际提取有误的字段。修改将重新复核并使旧问题失效。</p>
        <Form form={correctionForm} layout="vertical">
          <Form.Item
            name="address"
            label="合同地址"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <div className="form-grid">
            <Form.Item name="rent_amount" label="合同租金（AUD）">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="bond" label="押金（AUD）">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="start_date" label="租期开始">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="end_date" label="租期结束">
              <Input type="date" />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </>
  );
}
