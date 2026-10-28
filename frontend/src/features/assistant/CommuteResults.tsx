import { Alert, Button, Pagination, Tag } from "antd";
import { useRef, useState } from "react";
import type { AssistantMessage } from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import "./commuteResults.css";
import ListingActions from "../favorites/ListingActions";
import { commuteModes, UsydCommuteMini } from "../real-data/UsydCommute";
import { usydDirections } from "../real-data/directions";
import ListingReasons from "./ListingReasons";

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
  const [suburb, setSuburb] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const homes = useRef<HTMLDivElement>(null);
  const suburbs = [
    ...new Set(message.listings.map((listing) => listing.suburb)),
  ];
  const filtered = message.listings.filter(
    (listing) => !suburb || listing.suburb === suburb,
  );
  const pageSize = 12;
  const currentPage = Math.min(
    page,
    Math.max(1, Math.ceil(filtered.length / pageSize)),
  );
  const shown = filtered.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );
  const chooseSuburb = (value: string | null) => {
    setSuburb(value);
    setPage(1);
  };
  if (!message.destination_options?.length && !result) return null;
  if (!result && message.destination_options?.length)
    return (
      <Alert
        type="info"
        title="到校地点已统一为悉大主校区"
        description="Camperdown / Darlington · Fisher Library。旧地点选项已停用。"
        action={
          <Button
            disabled={disabled || !onSuggest}
            onClick={() =>
              onSuggest?.("保留我的预算和房型，按悉大主校区继续推荐通勤房源。")
            }
          >
            按主校区继续
          </Button>
        }
      />
    );
  if (
    result &&
    result.destination.id !== "usyd:camperdown-darlington:fisher-library"
  )
    return (
      <Alert
        type="info"
        showIcon
        title="这份结果使用了旧校区"
        description="现在只按悉大 Camperdown / Darlington 主校区找房，请重新生成通勤推荐。"
        action={
          <Button
            disabled={disabled || !onSuggest}
            onClick={() =>
              onSuggest?.(
                "保留我的预算和房型，重新按悉大主校区及原来的通勤上限推荐。",
              )
            }
          >
            重新推荐
          </Button>
        }
      />
    );
  return (
    <section className="commute-results" aria-label="通勤与区域建议">
      {result ? (
        <>
          <div className="commute-heading">
            <h3>到悉大主校区找房</h3>
            <Tag color="blue">已筛选</Tag>
          </div>
          <p className="commute-destination">前往 {result.destination.label}</p>
          <div className="commute-filter-tags" aria-label="本次通勤条件">
            <Tag color="blue">
              {commuteModes.find(
                (m) => m.value === result.criteria.commute_mode,
              )?.label ?? "公共交通"}
              {result.criteria.commute_max_minutes
                ? ` ≤${result.criteria.commute_max_minutes}分钟`
                : ""}
            </Tag>
          </div>
          <p className="muted small">
            本次找到 {result.matching_count ?? message.listings.length}{" "}
            套符合通勤条件的房源
          </p>
          {!message.listings.length && (
            <Alert
              type="info"
              showIcon
              title="当前条件下没有匹配房源"
              description="可以调整预算或房型，或明确放宽通勤时间。"
            />
          )}
          <div
            className="commute-area-buttons"
            role="group"
            aria-label="按区域查看房源"
          >
            <Button
              aria-label="全部"
              autoInsertSpace={false}
              type={suburb === null ? "primary" : "default"}
              aria-pressed={suburb === null}
              onClick={() => chooseSuburb(null)}
            >
              全部
            </Button>
            {suburbs.map((name) => (
              <Button
                key={name}
                type={suburb === name ? "primary" : "default"}
                aria-pressed={suburb === name}
                onClick={() => chooseSuburb(name)}
              >
                {name}
              </Button>
            ))}
          </div>
          {suburb && !filtered.length && (
            <p className="muted small">本次结果暂无该区房源。</p>
          )}
          <div className="commute-homes" ref={homes}>
            {shown.map((listing) => {
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
                    <UsydCommuteMini
                      listing={listing}
                      mode={result.criteria.commute_mode}
                    />
                  </div>
                  <ListingReasons
                    listing={listing}
                    criteria={result.criteria}
                    filters={message.recommendation_filters}
                  />
                  <div className="commute-actions">
                    {onView ? (
                      <Button size="small" onClick={() => onView(listing)}>
                        房源详情
                      </Button>
                    ) : null}
                    <ListingActions
                      listing={listing}
                      onSelect={onSave}
                      disabled={disabled}
                    />
                    <a
                      href={usydDirections(
                        listing,
                        result.criteria.commute_mode ?? "public_transport",
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Google 地图 ↗
                    </a>
                  </div>
                </article>
              );
            })}
          </div>
          {filtered.length > pageSize && (
            <nav aria-label="房源分页" className="commute-pagination">
              <Pagination
                current={currentPage}
                total={filtered.length}
                pageSize={pageSize}
                showSizeChanger={false}
                responsive
                onChange={(next) => {
                  setPage(next);
                  homes.current?.scrollIntoView({
                    block: "start",
                    behavior: "smooth",
                  });
                }}
              />
            </nav>
          )}
          {onSuggest && message.listings.length > 0 ? (
            <div className="commute-actions">
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    "保持全部已确认的预算、房型和通勤条件，换一批推荐，优先展示之前没看过的房源。",
                  )
                }
              >
                换一批
              </Button>
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
