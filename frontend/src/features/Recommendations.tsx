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
          title="Housing recommendations"
          description="Recommendations use the preferences you explicitly confirm."
        />
        <Blank
          text="No recommendation report yet. Confirm your current preferences first."
          action={
            <Button type="primary" onClick={() => go("preferences")}>
              Confirm preferences
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
      title: `Confirm selection of ${item.listing_id}`,
      content: (
        <>
          <p>
            {money(item.weekly_cost)} / {label(p.budget?.scope ?? "")} / week;
            simulated commute {item.commute_minutes} minutes.
          </p>
          <p>
            Eligibility and evidence freshness are checked again at the
            disclosed simulated selection time. This does not mean a lease is
            signed.
          </p>
        </>
      ),
      okText: "Confirm this listing",
      cancelText: "Keep comparing",
      onOk: () =>
        action.run(async () => {
          await post(`/cases/${current.case_id}/selections`, body);
          await refresh();
          message.success("Listing selected and evidence pack saved.");
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
        title="Housing recommendations"
        description="Find your next home using your confirmed preferences."
        extra={
          <Space wrap>
            <Select
              aria-label="Choose recommendation version"
              value={run}
              onChange={(value) => {
                setRun(value);
                setEvidence(null);
                setCompare(false);
              }}
              options={current.evaluations.map((e, i) => ({
                value: e.run_id,
                label: `Preferences v${e.profile_version} · Report ${i + 1}`,
              }))}
            />
            <Button onClick={() => go("preferences")}>Edit preferences</Button>
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
          title={
            loading
              ? "Loading selected report"
              : "Could not load selected report"
          }
          description={`The last valid report remains below: preferences v${report.profile_version}.Selection and evidence actions are paused until the report reloads successfully.`}
        />
      )}
      {!isCurrent && (
        <Alert
          showIcon
          type="warning"
          title="You are viewing a historical report"
          description="The draft or confirmed version has changed. Historical results remain available, but selection needs a new assessment using current confirmed preferences."
        />
      )}
      {current.selection && (
        <Alert
          type={selectionCurrent ? "success" : "warning"}
          showIcon
          title={
            selectionCurrent
              ? `Selected ${current.selection.listing_id}`
              : `Previous selection ${current.selection.listing_id} · Select again`
          }
          description={
            <Space wrap>
              <span>
                {selectionCurrent
                  ? "Selection evidence pack saved. It has not been sent externally."
                  : "Preferences have changed. The historical evidence pack is retained. Select again using current preferences before contract review."}
              </span>
              <a
                href={downloadUrl(
                  `/cases/${current.case_id}/exports/selection`,
                )}
              >
                Download selection evidence pack
              </a>
              <Button
                size="small"
                disabled={!selectionCurrent}
                onClick={() => go("contract")}
              >
                Continue to contract review
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
              <span>Preference version</span>
              <strong>v{report.profile_version}</strong>
            </div>
            <div>
              <span>Maximum weekly budget</span>
              <strong>
                {money(p.budget?.maximum)} / {label(p.budget?.scope ?? "")}
              </strong>
            </div>
            <div>
              <span>Maximum commute</span>
              <strong>{p.commute?.maximum_minutes} minutes</strong>
            </div>
            <div>
              <span>Must-haves</span>
              <strong>
                {p.hard_requirements?.map(label).join(", ") ||
                  "No additional facility requirements"}
              </strong>
            </div>
          </section>
          <p className="snapshot-note">
            Synthetic snapshot {report.as_of} · fixed scenario replay ·{" "}
            {report.report_status === "partial"
              ? "Partial report"
              : "Assessment complete"}
          </p>
          <div className="report-actions">
            <Space wrap>
              <Button
                type="text"
                disabled={!result.comparison || !reportBound}
                onClick={() => setCompare(true)}
              >
                Compare preference versions
              </Button>
              <a
                href={downloadUrl(
                  `/evaluations/${result.run_id}/export?format=json`,
                )}
              >
                Download JSON
              </a>
              <a
                href={downloadUrl(
                  `/evaluations/${result.run_id}/export?format=markdown`,
                )}
              >
                Download report
              </a>
            </Space>
          </div>
          {result.comparison_error && (
            <Alert
              type="info"
              title="No preference-only comparison was generated"
              description={text(result.comparison_error)}
            />
          )}
          <Tabs
            activeKey={category}
            onChange={setCategory}
            items={[
              {
                key: "recommendations",
                label: `Recommended listings ${report.recommendations.length}`,
              },
              {
                key: "eligible",
                label: `All eligible ${report.counts.eligible}`,
              },
              {
                key: "pending_confirmation",
                label: `To confirm ${report.counts.pending}`,
              },
              { key: "excluded", label: `Excluded ${report.counts.excluded}` },
              {
                key: "duplicates",
                label: `Duplicate records ${report.counts.duplicates}`,
              },
            ]}
          />
          {category === "duplicates" ? (
            <section className="panel">
              <h2>Duplicates from the same source</h2>
              {report.duplicates.map((d, i) => (
                <div key={i} className="detail-row">
                  {Object.entries(d).map(([k, v]) => (
                    <p key={k}>
                      <strong>{label(k)}: </strong>
                      {text(v)}
                    </p>
                  ))}
                </div>
              ))}
            </section>
          ) : rows.length === 0 ? (
            <Blank text="No listings in this category. Try another category or adjust your preferences." />
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
                        <p>Synthetic listing · {label(p.rental_mode ?? "")}</p>
                      </div>
                    </div>
                    <div className="score">
                      {item.score == null ? (
                        <span className="unscored">Unscored</span>
                      ) : (
                        <strong>{item.score.toFixed(2)}</strong>
                      )}
                      <span>
                        {item.score == null ? (
                          <Status value={item.status ?? category} />
                        ) : (
                          "Preference match score"
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="listing-facts">
                    <div>
                      <span>Comparable weekly cost</span>
                      <strong>
                        {money(item.weekly_cost)} /{" "}
                        {label(p.budget?.scope ?? "")}
                      </strong>
                    </div>
                    <div>
                      <span>Simulated commute</span>
                      <strong>
                        {item.commute_minutes ?? "Not provided"}
                        {item.commute_minutes != null ? " minutes" : ""}
                      </strong>
                    </div>
                    <div>
                      <span>Bills coverage</span>
                      <strong>
                        {p.budget?.includes_bills
                          ? "Assessed with bills included"
                          : "Assessed with bills excluded"}
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
                      View recommendation evidence
                    </Button>
                    {item.status === "eligible" && (
                      <Button
                        type="primary"
                        onClick={() => select(item)}
                        disabled={!isCurrent || action.busy}
                        loading={action.busy}
                        aria-label="Select this listing"
                      >
                        Select this listing
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
                label: "Data scope and clarifications",
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
          <h2>Current workflow</h2>
          <Steps
            orientation="vertical"
            current={selectionCurrent ? 2 : 1}
            items={[
              {
                title: "Confirm preferences",
                content: `Confirmed v${report.profile_version}`,
              },
              {
                title: "Select a listing",
                content: selectionCurrent
                  ? "Selected"
                  : current.selection
                    ? "Historical selection needs confirmation again"
                    : "In progress",
              },
              {
                title: "Contract review",
                content: current.reviews.length
                  ? "View results"
                  : "Not started",
              },
            ]}
          />
          <p>Each next step requires your confirmation.</p>
          <small>
            Simulated selection time
            <br />
            {config.clocks.selection}
          </small>
        </aside>
      </div>
      <EvidenceDrawer
        title={`${evidence?.listing_id ?? ""} · Recommendation evidence`}
        open={Boolean(evidence)}
        onClose={() => setEvidence(null)}
      >
        {evidence && (
          <>
            <h3>Four-dimension scores and effective weights</h3>
            <div className="score-grid">
              {Object.entries(evidence.score_breakdown ?? {}).map(
                ([key, value]) => (
                  <div key={key}>
                    <span>{label(key)}</span>
                    <strong>
                      {value == null ? "Unknown" : value.toFixed(2)}
                    </strong>
                    <small>
                      Effective weight{" "}
                      {Math.round((report.effective_weights[key] ?? 0) * 100)}%
                    </small>
                  </div>
                ),
              )}
            </div>
            <h3>Hard requirement checks</h3>
            {Object.entries(evidence.hard_checks ?? {}).map(([key, check]) => (
              <div className="detail-row" key={key}>
                <Status value={check.status} />
                <strong>{label(key)}</strong>
                <p>{check.reason}</p>
              </div>
            ))}
            <h3>Sources and observation times</h3>
            {Object.entries(evidence.evidence_refs ?? {}).map(([key, ref]) => (
              <div className="detail-row" key={key}>
                <strong>{label(key)}</strong>
                <p className="break-word">{ref.source_ref}</p>
                <small>{ref.observed_at} · Synthetic evidence</small>
              </div>
            ))}
            <Collapse
              items={[
                {
                  key: "raw",
                  label: "Input and report references",
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
        title="Preference version comparison"
        open={compare}
        onClose={() => setCompare(false)}
      >
        <p>
          Agent1 checks saved versions and reuses Agent2 comparisons with the
          same search, snapshot and rule version. Rankings also depend on
          changes to other eligible candidates.
        </p>
        <h3>Preference changes</h3>
        <JsonDetails value={result.comparison?.changed_fields} />
        <Table
          rowKey="listing_id"
          size="small"
          scroll={{ x: 560 }}
          pagination={{ pageSize: 8 }}
          dataSource={comparisonRows}
          columns={[
            { title: "Listings", dataIndex: "listing_id" },
            {
              title: "Rank change",
              render: (_, r) =>
                `${text(r.before_rank)} → ${text(r.after_rank)}`,
            },
            {
              title: "Score change",
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
