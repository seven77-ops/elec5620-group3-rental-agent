import { Button, Tag } from "antd";
import { ExportOutlined } from "@ant-design/icons";
import type { HousingAd } from "../../api/catalog";
import { ListingGallery } from "./ListingPhotos";
import {
  displayDate,
  knownLabel,
  furnishingTypes,
  propertyFeatures,
  propertyTypes,
} from "./listingPresentation";
import "./listingDetails.css";

export default function ListingDetails({ listing }: { listing: HousingAd }) {
  const type = knownLabel(propertyTypes, listing.property_type);
  const furniture = knownLabel(furnishingTypes, listing.furnishing);
  const date =
    displayDate(listing.available_from) ??
    (listing.available_from_raw === "Available Now"
      ? "采集时标注可入住"
      : listing.available_from_raw);
  const bond =
    typeof listing.bond === "number" &&
    Number.isFinite(listing.bond) &&
    listing.bond >= 0
      ? `AUD ${listing.bond.toLocaleString("en-AU")}`
      : null;
  const amenities = propertyFeatures(listing.features);
  const facts = [
    { label: "房屋类型", value: type },
    { label: "可入住日期", value: date },
    { label: "押金", value: bond },
    { label: "家具", value: furniture },
  ].filter((fact) => fact.value);
  const pending = [
    "当前是否可租",
    "租金按整套 / 每人计算",
    "账单与额外费用",
    "租期",
    "实际通勤时间",
  ];
  if (!date) pending.push("可入住日期");
  if (!bond) pending.push("押金");
  if (!furniture) pending.push("家具");
  return (
    <article className="listing-detail" data-testid="listing-details">
      <header className="listing-detail-heading">
        <div className="listing-detail-location">
          {listing.suburb} · NSW {listing.postcode}
        </div>
        <h2>{listing.address}</h2>
        <div className="listing-detail-heading-bottom">
          <div
            className="listing-detail-rent"
            data-testid="listing-detail-rent"
          >
            <span>AUD</span> {listing.weekly_rent.toLocaleString("en-AU")}
            <small>/ 周</small>
          </div>
          <Tag variant="filled">在租状态待确认</Tag>
        </div>
      </header>
      <ListingGallery key={listing.listing_id} listing={listing} />
      <dl
        className="listing-detail-summary"
        data-testid="listing-detail-summary"
      >
        <div>
          <dt>卧室</dt>
          <dd>
            {listing.bedrooms}
            <small>
              {listing.bedroom_count_basis === "open_plan_as_one"
                ? "开放式"
                : "间"}
            </small>
          </dd>
        </div>
        <div>
          <dt>浴室</dt>
          <dd>
            {listing.bathrooms}
            <small>间</small>
          </dd>
        </div>
        <div>
          <dt>车位</dt>
          <dd>
            {listing.car_spaces}
            <small>个</small>
          </dd>
        </div>
      </dl>
      {listing.bedroom_count_basis === "open_plan_as_one" && (
        <p className="listing-detail-studio">
          Studio · 来源标注为 0 卧，按 1 个开放式睡眠空间展示，并非独立卧室。
        </p>
      )}
      {listing.property_type === "studio" &&
        listing.bedroom_count_basis !== "open_plan_as_one" && (
          <p className="listing-detail-studio">
            Studio 为开放式户型，独立卧室情况请看房确认。
          </p>
        )}
      {facts.length > 0 && (
        <section className="listing-detail-section">
          <h3>房屋资料</h3>
          <dl
            className="listing-detail-facts"
            data-testid="listing-detail-facts"
          >
            {facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {amenities.length > 0 && (
        <section className="listing-detail-section">
          <h3>房屋配置</h3>
          <div
            className="listing-detail-features"
            data-testid="listing-detail-features"
          >
            {amenities.map((value) => (
              <span key={value}>{value}</span>
            ))}
          </div>
        </section>
      )}
      <section
        className="listing-detail-pending listing-detail-section"
        data-testid="listing-detail-pending"
      >
        <h3>待确认事项</h3>
        <p>看房或联系中介时，一并核对这些信息。</p>
        <ul>
          {pending.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      </section>
      <footer className="listing-detail-source">
      <Button
        aria-label="查看 Domain 房源"
        href={listing.source_url}
          target="_blank"
          rel="noopener noreferrer"
          icon={<ExportOutlined />}
        >
          查看 Domain 房源
        </Button>
        <p>
          房源资料采集于 {displayDate(listing.captured_at) ?? "未记录日期"}
          ，实际情况以看房及中介确认为准。
        </p>
      </footer>
    </article>
  );
}
