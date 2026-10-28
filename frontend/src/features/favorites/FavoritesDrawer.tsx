import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Drawer,
  Empty,
  Input,
  Space,
  Spin,
} from "antd";
import { HeartOutlined } from "@ant-design/icons";
import type { HousingAd } from "../../api/catalog";
import ListingDetails from "../real-data/ListingDetails";
import { UsydCommuteMini } from "../real-data/UsydCommute";
import ListingActions from "./ListingActions";
import { useFavorites } from "./FavoritesContext";
import "./favorites.css";
import type { SelectionSource, SelectionResult } from "./FollowupDialog";

const comparisonFacts: {
  label: string;
  render: (row: HousingAd) => string | number;
}[] = [
  { label: "周租", render: (row) => `AUD ${row.weekly_rent}/周` },
  { label: "卧室", render: (row) => row.bedroom_label || row.bedrooms },
  { label: "浴室", render: (row) => row.bathrooms },
  { label: "车位", render: (row) => row.car_spaces },
];

export default function FavoritesDrawer({
  commuteMode,
  selectionSource,
  onSelected,
}: {
  commuteMode?: string;
  selectionSource?: SelectionSource;
  onSelected?: (value: SelectionResult) => void;
} = {}) {
  const favorites = useFavorites();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [detail, setDetail] = useState<HousingAd | null>(null);
  const compare = favorites.items.filter((item) =>
    selected.includes(item.listing.listing_id),
  );
  const query = filter.trim().toLocaleLowerCase();
  const shown = favorites.items.filter(({ listing }) =>
    `${listing.address} ${listing.suburb}`.toLocaleLowerCase().includes(query),
  );
  return (
    <>
      <Button
        icon={<HeartOutlined />}
        aria-label={`我的收藏（${favorites.items.length}）`}
        onClick={() => {
          favorites.reload();
          setOpen(true);
        }}
      >
        我的收藏（{favorites.items.length}）
      </Button>
      <Drawer
        title="我的收藏"
        open={open}
        onClose={() => {
          setOpen(false);
          setDetail(null);
        }}
        size={900}
        rootClassName="favorites-drawer"
      >
        <p className="muted">
          收藏多套，慢慢比较；确定房源后，点击“选定并跟进”准备看房和合同。
        </p>
        {favorites.error && (
          <Alert
            type="error"
            title={favorites.error}
            action={<Button onClick={favorites.reload}>重新读取收藏</Button>}
          />
        )}
        <Input.Search
          aria-label="筛选收藏房源"
          placeholder="按地址或区域筛选收藏"
          value={filter}
          allowClear
          onChange={(e) => setFilter(e.target.value)}
        />
        <p className="muted small">勾选 2–4 套房源，即可并排比较。</p>
        {compare.length >= 2 && (
          <section className="favorites-compare" aria-label="比较已收藏房源">
            <div className="favorites-compare-heading">
              <h3>已选 {compare.length} 套，比较房源</h3>
              <Button size="small" onClick={() => setSelected([])}>
                清空比较
              </Button>
            </div>
            <div className="favorites-table-scroll">
              <table aria-label="收藏房源比较">
                <thead>
                  <tr>
                    <th>条件</th>
                    {compare.map(({ listing }) => (
                      <th key={listing.listing_id}>{listing.address}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparisonFacts.map(({ label, render }) => (
                    <tr key={label}>
                      <th>{label}</th>
                      {compare.map(({ listing }) => (
                        <td key={listing.listing_id}>{render(listing)}</td>
                      ))}
                    </tr>
                  ))}
                  <tr>
                    <th>到悉大</th>
                    {compare.map(({ listing }) => (
                      <td key={listing.listing_id}>
                        <UsydCommuteMini listing={listing} mode={commuteMode} />
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        )}
        {favorites.loading ? (
          <Spin />
        ) : shown.length === 0 ? (
          <Empty
            description={
              query
                ? "没有匹配的收藏房源"
                : "还没有收藏房源，看到喜欢的房源可以先收藏。"
            }
          />
        ) : (
          <div className="favorite-homes">
            {shown.map(({ listing, in_catalog }) => (
              <article
                key={listing.listing_id}
                className="favorite-home"
                data-testid="favorite-home"
              >
                <Checkbox
                  aria-label={`比较收藏 ${listing.address}`}
                  checked={selected.includes(listing.listing_id)}
                  disabled={
                    compare.length >= 4 &&
                    !selected.includes(listing.listing_id)
                  }
                  onChange={(e) =>
                    setSelected((ids) =>
                      e.target.checked
                        ? [...new Set([...ids, listing.listing_id])]
                        : ids.filter((id) => id !== listing.listing_id),
                    )
                  }
                >
                  比较
                </Checkbox>
                <h3>{listing.address}</h3>
                <p className="muted">
                  {listing.suburb} · {listing.bedroom_label} 卧 ·{" "}
                  {listing.bathrooms} 卫 · {listing.car_spaces} 车位
                </p>
                <strong>AUD {listing.weekly_rent.toLocaleString()}/周</strong>
                <Space wrap className="favorite-home-actions">
                  <Button
                    size="small"
                    onClick={() =>
                      setDetail({
                        ...listing,
                        recommendation_mode: commuteMode,
                      })
                    }
                  >
                    房源详情
                  </Button>
                  <ListingActions
                    listing={listing}
                    selectDisabled={!in_catalog}
                    onSelect={(listing) =>
                      favorites.choose(listing, selectionSource, (value) => {
                        setOpen(false);
                        onSelected?.(value);
                      })
                    }
                  />
                </Space>
                {!in_catalog && (
                  <p className="muted small">
                    此房源已不在当前房源库，收藏记录保留。
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </Drawer>
      <Drawer
        title="真实房源详情"
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        size={1000}
        rootClassName="favorites-detail-drawer"
      >
        {detail && <ListingDetails listing={detail} />}
      </Drawer>
    </>
  );
}
