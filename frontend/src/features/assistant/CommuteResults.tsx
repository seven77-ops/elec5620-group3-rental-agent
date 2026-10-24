import { Alert, Button, Tag } from "antd";
import type { AssistantMessage } from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import { housingCopy } from "../real-data/listingPresentation";
import "./commuteResults.css";
import { AreaEvidenceDetails } from "./AreaAdvice";
const sydneyTime = (value: string) =>
  new Date(value).toLocaleTimeString("zh-CN", {
    timeZone: "Australia/Sydney",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

export default function CommuteResults({
  message,
  onSuggest,
  onView,
  onSave,
  disabled,
}: {
  message: AssistantMessage;
  onSuggest?: (text: string) => void;
  onView?: (listing: HousingAd) => void;
  onSave?: (listing: HousingAd) => void;
  disabled?: boolean;
}) {
  const result = message.commute_recommendation;
  if (!message.destination_options?.length && !result) return null;
  return (
    <section className="commute-results" aria-label="通勤与区域建议">
      {message.destination_options?.length ? (
        <div className="commute-destinations">
          <h3>确认通勤目的地</h3>
          {message.destination_options.map((option) => (
            <article key={option.id}>
              <strong>{option.label}</strong>
              <div className="commute-actions">
                <Button
                  disabled={disabled || !onSuggest}
                  aria-label={"选择 " + option.label}
                  onClick={() =>
                    onSuggest?.(
                      "我的通勤目的地选择：" +
                        option.label +
                        "（地点编号 " +
                        option.id +
                        "）",
                    )
                  }
                >
                  选择这个地点
                </Button>
                <a
                  href={option.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  位置来源 ↗
                </a>
              </div>
            </article>
          ))}
        </div>
      ) : null}
      {result ? (
        <>
          <div className="commute-heading">
            <h3>按通勤选区域</h3>
            <Tag color={result.status === "ready" ? "blue" : "orange"}>
              {result.status === "ready"
                ? "已查询路线"
                : result.status === "partial"
                  ? "部分路线可用"
                  : "通勤待查询"}
            </Tag>
          </div>
          <p className="commute-destination">前往 {result.destination.label}</p>
          <p className="muted small">
            {result.date} · {result.arrival_time} 前到达 · 单程
            {result.criteria.commute_max_minutes
              ? `目标 ${result.criteria.commute_max_minutes} 分钟`
              : ""}
            {result.criteria.commute_hard_limit ? "（硬条件）" : ""}
          </p>
          <p className="muted small">
            {result.total_matching} 条符合房屋筛选，已查询{" "}
            {result.evaluated_count} 条 · 每次最多查询 {result.query_limit} 条
          </p>
          <div className="commute-area-grid">
            {result.areas.map((area) => (
              <article key={area.suburb} className="commute-area">
                <h4>{area.suburb}</h4>
                <p className="commute-price">
                  AUD {area.min_weekly_rent}–{area.max_weekly_rent}
                  <small>/周 · 房源标价</small>
                </p>
                <p className="small">
                  {area.count} 条房屋候选 · {area.verified_route_count}{" "}
                  条已查询可用路线
                </p>
                {area.verified_route_count === 0 ? <Tag>通勤待查询</Tag> : null}
                <details className="commute-area-notes">
                  <summary>依据与取舍</summary>
                  <ul>
                    {area.reasons.map((reason) => (
                      <li key={reason}>{housingCopy(reason)}</li>
                    ))}
                  </ul>
                  <ul className="commute-tradeoffs">
                    {area.tradeoffs.map((reason) => (
                      <li key={reason}>{housingCopy(reason)}</li>
                    ))}
                  </ul>
                </details>
                {area.area_context ? (
                  <AreaEvidenceDetails area={area.area_context} />
                ) : null}
              </article>
            ))}
          </div>
          {result.area_knowledge_coverage ? (
            <p className="muted small">
              区域生活资料覆盖 {result.area_knowledge_coverage.covered_suburbs}{" "}
              / {result.area_knowledge_coverage.catalog_suburbs}{" "}
              个区域；资料缺口不代表区域条件较差。生活主题只在相同租金与通勤排序内辅助比较。
            </p>
          ) : null}
          <div className="commute-homes">
            {message.listings.map((listing) => {
              const route = result.routes.find(
                (row) => row.listing_id === listing.listing_id,
              );
              const good = route?.status === "ok";
              return (
                <article key={listing.listing_id} className="commute-home">
                  <div>
                    <h4>{listing.address}</h4>
                    <p className="small muted">
                      {listing.bedroom_label} 卧 · {listing.bathrooms} 卫 ·{" "}
                      {listing.car_spaces} 车位
                    </p>
                    <strong className="commute-price">
                      AUD {listing.weekly_rent}
                      <small>/周</small>
                    </strong>
                  </div>
                  <div className="commute-route">
                    <strong className={good ? "commute-time" : ""}>
                      {route?.duration_minutes != null
                        ? `${Math.ceil(route.duration_minutes)} 分钟`
                        : "通勤待查询"}
                    </strong>
                    {route?.duration_minutes != null ? (
                      <p className="small">
                        {route.walking_minutes != null
                          ? `步行 ${Math.ceil(route.walking_minutes)} 分钟`
                          : "步行待核实"}{" "}
                        ·{" "}
                        {route.transfers != null
                          ? `换乘 ${route.transfers} 次`
                          : "换乘待核实"}
                      </p>
                    ) : null}
                    {route?.reason ? (
                      <p className="small muted">{housingCopy(route.reason)}</p>
                    ) : null}
                    {route?.departure_at && route?.arrival_at ? (
                      <p className="small muted">
                        {sydneyTime(route.departure_at)} 出发 →{" "}
                        {sydneyTime(route.arrival_at)} 到达
                      </p>
                    ) : null}
                    {route?.status === "over_limit" ? (
                      <Tag color="orange">超出通勤条件</Tag>
                    ) : null}
                  </div>
                  <div className="commute-actions">
                    {onView ? (
                      <Button size="small" onClick={() => onView(listing)}>
                        房源详情
                      </Button>
                    ) : null}
                    {onSave ? (
                      <Button
                        size="small"
                        disabled={disabled}
                        onClick={() => onSave(listing)}
                      >
                        保存为候选
                      </Button>
                    ) : null}
                    <a
                      href={listing.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      原始房源 ↗
                    </a>
                    {route?.route_url ? (
                      <a
                        href={route.route_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        查看路线 ↗
                      </a>
                    ) : null}
                    {route?.source_url ? (
                      <a
                        href={route.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        通勤数据来源 ↗
                      </a>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
          {result.pending_listings?.length ? (
            <details className="commute-pending">
              <summary>
                待核对房源 · {result.pending_listings.length}{" "}
                条（未列为满足通勤条件）
              </summary>
              <p className="small muted">
                这些房源的通勤尚未查明或超出条件，可先查看资料与路线。
              </p>
              {result.pending_listings.map((listing) => {
                const route = result.routes.find(
                  (row) => row.listing_id === listing.listing_id,
                );
                return (
                  <article key={listing.listing_id} className="commute-home">
                    <div>
                      <h4>{listing.address}</h4>
                      <p className="small">
                        AUD {listing.weekly_rent}/周 · {listing.bedroom_label}{" "}
                        卧 · {listing.bathrooms} 卫
                      </p>
                    </div>
                    <div>
                      <Tag color="orange">
                        {route?.status === "over_limit"
                          ? "超出通勤条件"
                          : "通勤待查询"}
                      </Tag>
                      <p className="small muted">
                        {route?.reason ? housingCopy(route.reason) : ""}
                      </p>
                    </div>
                    <div className="commute-actions">
                      {onView ? (
                        <Button size="small" onClick={() => onView(listing)}>
                          房源详情
                        </Button>
                      ) : null}
                      <a
                        href={listing.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        原始房源 ↗
                      </a>
                      {route?.route_url ? (
                        <a
                          href={route.route_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          查看路线 ↗
                        </a>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </details>
          ) : null}
          {result.limitations.length ? (
            <Alert
              type="info"
              showIcon
              title="本次推荐的依据与范围"
              description={
                <ul>
                  {result.limitations.map((note) => (
                    <li key={note}>{housingCopy(note)}</li>
                  ))}
                </ul>
              }
            />
          ) : null}
          <p className="muted small">
            查询于 {new Date(result.queried_at).toLocaleString("zh-CN")} ·
            路线来源：Transport for NSW；完整路线可另行打开地图核对。
          </p>
          {onSuggest ? (
            <div className="commute-actions">
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest("保持刚才的户型和目的地，优先推荐租金更低的房源。")
                }
              >
                更看重租金
              </Button>
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest("保持刚才的预算和户型，优先推荐通勤更短的房源。")
                }
              >
                更看重通勤
              </Button>
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    "保持其他需求，单程最多可接受" +
                      Math.min(
                        240,
                        (result.criteria.commute_max_minutes ?? 40) + 10,
                      ) +
                      "分钟，请重新推荐。",
                  )
                }
              >
                通勤放宽10分钟
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
