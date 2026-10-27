import { Button, Tag } from "antd";
import type { AreaContext, AreaAdviceReport } from "../../api/areas";
import { lifestyleTopics } from "../../api/areas";
import "./areaAdvice.css";

const evidenceLabels = {
  official: "官方设施资料",
  venue: "运营方介绍",
  media: "媒体背景",
  resident_opinion: "住户观点",
};
const topicNames = (topics: (keyof typeof lifestyleTopics)[]) =>
  topics.map((t) => lifestyleTopics[t]).join("、");

export function AreaEvidenceDetails({ area }: { area: AreaContext }) {
  return (
    <div className="area-evidence-details">
      {area.matched_topics.length > 0 && (
        <p className="area-relevance">
          与你的偏好相关：{topicNames(area.matched_topics)}
        </p>
      )}
      {area.missing_topics.length > 0 && (
        <p className="area-missing">
          还不能确认：{topicNames(area.missing_topics)}
        </p>
      )}
      {area.notes.map((note) => (
        <p className="muted small" key={note}>
          {note}
        </p>
      ))}
      {area.evidence.length > 0 && (
        <>
          <p className="area-preview">{area.evidence[0].summary}</p>
          <details className="area-sources">
            <summary>查看来源与适用范围</summary>
            {area.evidence.map((record) => (
              <article className="area-source" key={record.evidence_id}>
                <div className="area-source-tags">
                  <Tag color={record.kind === "official" ? "blue" : undefined}>
                    {evidenceLabels[record.kind]}
                  </Tag>
                  {record.freshness === "needs_review" && (
                    <Tag color="orange">需重新核对</Tag>
                  )}
                  {record.freshness === "background" && <Tag>背景参考</Tag>}
                </div>
                <p>{record.summary}</p>
                <a
                  href={record.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {record.source.publisher} · {record.source.title} ↗
                </a>
                <p className="muted small">范围：{record.scope_label}</p>
                <p className="muted small">
                  {record.source.published_at
                    ? `发布：${record.source.published_at}`
                    : "发布日期未标注"}
                  {record.source.updated_at
                    ? ` · 更新：${record.source.updated_at}`
                    : ""}
                  {` · 核对：${record.source.checked_at}`}
                </p>
                {record.source.data_period && (
                  <p className="muted small">
                    资料时期：{record.source.data_period}
                  </p>
                )}
                <p className="area-source-limit small">{record.limitation}</p>
              </article>
            ))}
          </details>
        </>
      )}
    </div>
  );
}

export default function AreaAdvice({
  report,
  onSuggest,
  disabled,
}: {
  report?: AreaAdviceReport;
  onSuggest?: (text: string) => void;
  disabled?: boolean;
}) {
  if (!report) return null;
  return (
    <section className="area-advice" aria-label="区域生活建议">
      <div className="area-advice-heading">
        <h3>找到适合你的生活圈</h3>
        <span className="muted small">
          资料覆盖 {report.coverage.covered_suburbs} /{" "}
          {report.coverage.catalog_suburbs} 个区域
        </span>
      </div>
      {report.criteria_summary && (
        <p className="small area-criteria">
          本次条件：{report.criteria_summary}
        </p>
      )}
      {report.priorities.length > 0 ? (
        <div className="area-priorities" aria-label="本次生活偏好">
          <span className="small muted">你看重</span>
          {report.priorities.map((p) => (
            <Tag color="blue" key={p.topic}>
              {p.label}
            </Tag>
          ))}
        </div>
      ) : (
        <p className="muted small">
          告诉我更看重公园、吃饭购物、图书馆还是安静，可以进一步缩小范围。
        </p>
      )}
      <p className="muted small">
        以下库存沿用本次房型条件
        {report.budget_applied
          ? "和整套每周预算"
          : "；预算尚不适合直接比较房源周租，未按金额筛除"}
        。生活资料用于参考，通勤需单独核对。
      </p>
      <div className="area-advice-grid">
        {report.areas.map((area) => (
          <article
            key={area.suburb}
            className="area-advice-card"
            aria-label={area.suburb + " 区域参考"}
          >
            <h4>{area.suburb}</h4>
            <p className="small">
              当前快照 {area.matching_count} 条符合房屋条件的房源
            </p>
            {area.min_weekly_rent != null && (
              <p className="area-inventory-rent">
                AUD {area.min_weekly_rent}
                {area.max_weekly_rent !== area.min_weekly_rent
                  ? `–${area.max_weekly_rent}`
                  : ""}
                <small>/周 · 房源标价</small>
              </p>
            )}
            <AreaEvidenceDetails area={area} />
            {onSuggest && area.matching_count > 0 && (
              <Button
                size="small"
                aria-label={`在 ${area.suburb} 找房`}
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    `保持我的预算和房型要求，按 ${area.suburb} 区域继续推荐房源，并核对到悉大主校区的通勤。`,
                  )
                }
              >
                在这个区找房
              </Button>
            )}
          </article>
        ))}
      </div>
      {!report.areas.length && (
        <p>
          当前库存没有符合这些房型和可比较预算条件的区域。可以调整条件后重新比较。
        </p>
      )}
      <details className="area-report-notes">
        <summary>本次资料的范围</summary>
        <ul>
          {report.limitations.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
