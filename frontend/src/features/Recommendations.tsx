import { useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Collapse,
  Select,
  Space,
  Steps,
  Table,
  Tabs,
} from "antd";
import { useCase, currentConfirmation } from "../app/context";
import { api, downloadUrl, newRequestId, post } from "../api/client";
import type { Dict, Evaluation, Listing } from "../api/types";
import {
  Blank,
  EvidenceDrawer,
  Failure,
  JsonDetails,
  label,
  Loading,
  money,
  PageTitle,
  Status,
  text,
} from "../components/Common";
import { useAction } from "../components/useAction";
import RecommendationAi from "./ai/RecommendationAi";
export default function Recommendations() {
  const { current, refresh, go, config } = useCase();
  const { modal, message } = App.useApp();
  const action = useAction();
  const latest = current.evaluations.at(-1)?.run_id;
  const [run, setRun] = useState(latest);
  const [result, setResult] = useState<Evaluation | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [loadRevision, setLoadRevision] = useState(0);
  const [category, setCategory] = useState("recommendations");
  const [evidence, setEvidence] = useState<Listing | null>(null);
  const [compare, setCompare] = useState(false);
  useEffect(() => {
    if (!run && latest) setRun(latest);
  }, [run, latest]);
  useEffect(() => {
    if (!run) return;
    let valid = true;
    setLoading(true);
    setLoadError(null);
    setEvidence(null);
    setCompare(false);
    api<Evaluation>(`/evaluations/${run}`)
      .then((r) => {
        if (valid) setResult(r);
      })
      .catch((e) => {
        if (valid) setLoadError(e);
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [run, loadRevision]);
  const confirmed = currentConfirmation(current);
  if (!latest)
    return (
      <>
        <PageTitle
          title="房源推荐"
          description="推荐依据你明确确认的偏好生成。"
        />
        <Blank
          text="还没有推荐报告，请先确认当前偏好。"
          action={
            <Button type="primary" onClick={() => go("preferences")}>
              前往确认偏好
            </Button>
          }
        />
      </>
    );
  if (loading && !result) return <Loading />;
  if (!result)
    return (
      <Failure error={loadError} retry={() => setLoadRevision((v) => v + 1)} />
    );
  const report = result.report;
  const reportBound = result.run_id === run && !loading && !loadError;
  const isCurrent =
    reportBound &&
    confirmed?.version === report.profile_version &&
    confirmed.fingerprint === report.profile_fingerprint;
  const selectionCurrent = Boolean(
    current.selection &&
    confirmed &&
    current.selection.profile_version === confirmed.version &&
    current.selection.profile_fingerprint === confirmed.fingerprint,
  );
  const p = report.profile;
  const select = (item: Listing) => {
    const body = {
      request_id: newRequestId(),
      run_id: result.run_id,
      listing_id: item.listing_id,
      confirmed: true,
    };
    modal.confirm({
      title: `确认选择 ${item.listing_id}`,
      content: (
        <>
          <p>
            {money(item.weekly_cost)} / {label(p.budget?.scope ?? "")} /
            周，模拟通勤 {item.commute_minutes} 分钟。
          </p>
          <p>
            将按披露的模拟选择时间重新检查资格与证据时效。此操作不表示已经签约。
          </p>
        </>
      ),
      okText: "确认选择此房源",
      cancelText: "继续比较",
      onOk: () =>
        action.run(async () => {
          await post(`/cases/${current.case_id}/selections`, body);
          await refresh();
          message.success("房源已明确选择，证据包已保存。");
        }),
    });
  };
  const lists: Record<string, Listing[]> = {
    recommendations: report.recommendations,
    eligible: report.eligible,
    pending_confirmation: report.pending_confirmation,
    excluded: report.excluded,
  };
  const rows = lists[category] ?? [];
  const comparisonRows = (result.comparison?.rows ?? []) as Dict[];
  return (
    <>
      <PageTitle
        title="房源推荐"
        description="根据已确认偏好，找到适合你的下一站。"
        extra={
          <Space wrap>
            <Select
              aria-label="选择推荐版本"
              value={run}
              onChange={(value) => {
                setRun(value);
                setEvidence(null);
                setCompare(false);
              }}
              options={current.evaluations.map((e, i) => ({
                value: e.run_id,
                label: `偏好 v${e.profile_version} · 报告 ${i + 1}`,
              }))}
            />
            <Button onClick={() => go("preferences")}>修改偏好</Button>
          </Space>
        }
      />
      <Failure
        error={action.error || loadError}
        retry={loadError ? () => setLoadRevision((v) => v + 1) : action.retry}
      />
      {!reportBound && (
        <Alert
          type="info"
          showIcon
          title={loading ? "正在读取所选报告" : "所选报告尚未成功读取"}
          description={`下方保留上次有效报告：偏好 v${report.profile_version}。重新读取成功前暂停选房与证据操作。`}
        />
      )}
      {!isCurrent && (
        <Alert
          showIcon
          type="warning"
          title="当前查看的是历史报告"
          description="当前草稿或确认版本已改变。历史结果保留，但选房需要使用当前确认版本重新评估。"
        />
      )}
      {current.selection && (
        <Alert
          type={selectionCurrent ? "success" : "warning"}
          showIcon
          title={
            selectionCurrent
              ? `已选择 ${current.selection.listing_id}`
              : `历史选择 ${current.selection.listing_id} · 需重新选择`
          }
          description={
            <Space wrap>
              <span>
                {selectionCurrent
                  ? "选房证据包已保存，尚未对外发送。"
                  : "偏好版本已变化。历史证据包保留，继续合同复核前需按当前偏好重新选择。"}
              </span>
              <a
                href={downloadUrl(
                  `/cases/${current.case_id}/exports/selection`,
                )}
              >
                下载选房证据包
              </a>
              <Button
                size="small"
                disabled={!selectionCurrent}
                onClick={() => go("contract")}
              >
                继续合同复核
              </Button>
            </Space>
          }
        />
      )}
      <RecommendationAi
        key={result.run_id}
        runId={result.run_id}
        active={Boolean(isCurrent)}
      />
      <div className="recommendation-layout">
        <div className="recommendation-main">
          <section className="preference-band">
            <div>
              <span>偏好版本</span>
              <strong>v{report.profile_version}</strong>
            </div>
            <div>
              <span>最高周预算</span>
              <strong>
                {money(p.budget?.maximum)} / {label(p.budget?.scope ?? "")}
              </strong>
            </div>
            <div>
              <span>最长通勤</span>
              <strong>{p.commute?.maximum_minutes} 分钟</strong>
            </div>
            <div>
              <span>必须满足</span>
              <strong>
                {p.hard_requirements?.map(label).join("、") || "无额外设施要求"}
              </strong>
            </div>
          </section>
          <p className="snapshot-note">
            合成快照 {report.as_of} · 固定场景回放 ·{" "}
            {report.report_status === "partial" ? "部分报告" : "评估完成"}
          </p>
          <div className="report-actions">
            <Space wrap>
              <Button
                type="text"
                disabled={!result.comparison || !reportBound}
                onClick={() => setCompare(true)}
              >
                查看偏好版本比较
              </Button>
              <a
                href={downloadUrl(
                  `/evaluations/${result.run_id}/export?format=json`,
                )}
              >
                下载 JSON
              </a>
              <a
                href={downloadUrl(
                  `/evaluations/${result.run_id}/export?format=markdown`,
                )}
              >
                下载报告
              </a>
            </Space>
          </div>
          {result.comparison_error && (
            <Alert
              type="info"
              title="本次结果未生成纯偏好比较"
              description={text(result.comparison_error)}
            />
          )}
          <Tabs
            activeKey={category}
            onChange={setCategory}
            items={[
              {
                key: "recommendations",
                label: `推荐房源 ${report.recommendations.length}`,
              },
              { key: "eligible", label: `全部合格 ${report.counts.eligible}` },
              {
                key: "pending_confirmation",
                label: `待确认 ${report.counts.pending}`,
              },
              { key: "excluded", label: `已排除 ${report.counts.excluded}` },
              {
                key: "duplicates",
                label: `重复记录 ${report.counts.duplicates}`,
              },
            ]}
          />
          {category === "duplicates" ? (
            <section className="panel">
              <h2>同源重复记录</h2>
              {report.duplicates.map((d, i) => (
                <div key={i} className="detail-row">
                  {Object.entries(d).map(([k, v]) => (
                    <p key={k}>
                      <strong>{label(k)}：</strong>
                      {text(v)}
                    </p>
                  ))}
                </div>
              ))}
            </section>
          ) : rows.length === 0 ? (
            <Blank text="当前分类没有房源。可查看其他分类或返回偏好调整条件。" />
          ) : (
            <div className="listing-list">
              {rows.map((item) => (
                <article className="listing-row" key={item.listing_id}>
                  <div className="listing-top">
                    <div className="listing-name">
                      <span className="rank">
                        {item.rank == null
                          ? "—"
                          : String(item.rank).padStart(2, "0")}
                      </span>
                      <div>
                        <h2>{item.listing_id}</h2>
                        <p>合成房源 · {label(p.rental_mode ?? "")}</p>
                      </div>
                    </div>
                    <div className="score">
                      {item.score == null ? (
                        <span className="unscored">未评分</span>
                      ) : (
                        <strong>{item.score.toFixed(2)}</strong>
                      )}
                      <span>
                        {item.score == null ? (
                          <Status value={item.status ?? category} />
                        ) : (
                          "偏好匹配分"
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="listing-facts">
                    <div>
                      <span>可比周费用</span>
                      <strong>
                        {money(item.weekly_cost)} /{" "}
                        {label(p.budget?.scope ?? "")}
                      </strong>
                    </div>
                    <div>
                      <span>模拟通勤</span>
                      <strong>
                        {item.commute_minutes ?? "未提供"}
                        {item.commute_minutes != null ? " 分钟" : ""}
                      </strong>
                    </div>
                    <div>
                      <span>账单范围</span>
                      <strong>
                        {p.budget?.includes_bills
                          ? "按含账单条件评估"
                          : "按不含账单条件评估"}
                      </strong>
                    </div>
                  </div>
                  <div className="listing-reasons">
                    {(item.reasons ?? []).slice(0, 2).map((r, i) => (
                      <p key={i}>{r}</p>
                    ))}
                    {item.tradeoffs?.map((r, i) => (
                      <p className="tradeoff" key={i}>
                        {r}
                      </p>
                    ))}
                    {item.issues?.slice(0, 3).map((r, i) => (
                      <p className="tradeoff" key={i}>
                        {r}
                      </p>
                    ))}
                  </div>
                  <div className="listing-actions">
                    <Button
                      disabled={!reportBound}
                      onClick={() => setEvidence(item)}
                    >
                      查看推荐依据
                    </Button>
                    {item.status === "eligible" && (
                      <Button
                        type="primary"
                        onClick={() => select(item)}
                        disabled={!isCurrent || action.busy}
                        loading={action.busy}
                        aria-label="选择此房源"
                      >
                        选择此房源
                      </Button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
          <Collapse
            ghost
            items={[
              {
                key: "limits",
                label: "数据范围与澄清事项",
                children: (
                  <>
                    <ul>
                      {report.data_limitations.map((t, i) => (
                        <li key={i}>{t}</li>
                      ))}
                    </ul>
                    <JsonDetails value={report.clarification_requests} />
                  </>
                ),
              },
            ]}
          />
        </div>
        <aside className="workflow-rail">
          <h2>当前流程</h2>
          <Steps
            orientation="vertical"
            current={selectionCurrent ? 2 : 1}
            items={[
              {
                title: "确认偏好",
                content: `已确认 v${report.profile_version}`,
              },
              {
                title: "选择房源",
                content: selectionCurrent
                  ? "已选择"
                  : current.selection
                    ? "历史选择待重新确认"
                    : "进行中",
              },
              {
                title: "合同复核",
                content: current.reviews.length ? "查看结果" : "待开始",
              },
            ]}
          />
          <p>由你确认后再进入下一步。</p>
          <small>
            模拟选择时间
            <br />
            {config.clocks.selection}
          </small>
        </aside>
      </div>
      <EvidenceDrawer
        title={`${evidence?.listing_id ?? ""} · 推荐依据`}
        open={Boolean(evidence)}
        onClose={() => setEvidence(null)}
      >
        {evidence && (
          <>
            <h3>四维匹配分与有效权重</h3>
            <div className="score-grid">
              {Object.entries(evidence.score_breakdown ?? {}).map(
                ([key, value]) => (
                  <div key={key}>
                    <span>{label(key)}</span>
                    <strong>{value == null ? "未知" : value.toFixed(2)}</strong>
                    <small>
                      有效权重{" "}
                      {Math.round((report.effective_weights[key] ?? 0) * 100)}%
                    </small>
                  </div>
                ),
              )}
            </div>
            <h3>硬条件检查</h3>
            {Object.entries(evidence.hard_checks ?? {}).map(([key, check]) => (
              <div className="detail-row" key={key}>
                <Status value={check.status} />
                <strong>{label(key)}</strong>
                <p>{check.reason}</p>
              </div>
            ))}
            <h3>来源与观察时间</h3>
            {Object.entries(evidence.evidence_refs ?? {}).map(([key, ref]) => (
              <div className="detail-row" key={key}>
                <strong>{label(key)}</strong>
                <p className="break-word">{ref.source_ref}</p>
                <small>{ref.observed_at} · 合成证据</small>
              </div>
            ))}
            <Collapse
              items={[
                {
                  key: "raw",
                  label: "输入与报告引用",
                  children: (
                    <JsonDetails
                      value={{
                        run_id: result.run_id,
                        profile_fingerprint: report.profile_fingerprint,
                        dataset_fingerprint: report.dataset_fingerprint,
                        profile: report.profile,
                      }}
                    />
                  ),
                },
              ]}
            />
          </>
        )}
      </EvidenceDrawer>
      <EvidenceDrawer
        title="偏好版本比较"
        open={compare}
        onClose={() => setCompare(false)}
      >
        <p>
          比较由 Agent1 核对已保存版本，并复用 Agent2
          的同搜索、同快照与规则版本比较。名次同时受其他合格候选变化影响。
        </p>
        <h3>偏好变化</h3>
        <JsonDetails value={result.comparison?.changed_fields} />
        <Table
          rowKey="listing_id"
          size="small"
          scroll={{ x: 560 }}
          pagination={{ pageSize: 8 }}
          dataSource={comparisonRows}
          columns={[
            { title: "房源", dataIndex: "listing_id" },
            {
              title: "名次变化",
              render: (_, r) =>
                `${text(r.before_rank)} → ${text(r.after_rank)}`,
            },
            {
              title: "分数变化",
              render: (_, r) =>
                `${text(r.before_score)} → ${text(r.after_score)}`,
            },
          ]}
          expandable={{
            expandedRowRender: (r) => (
              <>
                <ul>
                  {((r.change_reasons as string[]) ?? []).map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
                <JsonDetails value={r.score_contributions} />
              </>
            ),
          }}
        />
      </EvidenceDrawer>
    </>
  );
}
