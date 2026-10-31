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
  { label: "Weekly rent", render: (row) => `AUD ${row.weekly_rent}/week` },
  { label: "Bedrooms", render: (row) => row.bedroom_label || row.bedrooms },
  { label: "Bathrooms", render: (row) => row.bathrooms },
  { label: "Car spaces", render: (row) => row.car_spaces },
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
        aria-label={`My favorites (${favorites.items.length})`}
        onClick={() => {
          favorites.reload();
          setOpen(true);
        }}
      >
        My favorites ({favorites.items.length})
      </Button>
      <Drawer
        title="My favorites"
        open={open}
        onClose={() => {
          setOpen(false);
          setDetail(null);
        }}
        size={900}
        rootClassName="favorites-drawer"
      >
        <p className="muted">
          Save several listings and compare them. When ready, choose “Select and
          follow up” to prepare inspections and contracts.
        </p>
        {favorites.error && (
          <Alert
            type="error"
            title={favorites.error}
            action={
              <Button onClick={favorites.reload}>Reload favorites</Button>
            }
          />
        )}
        <Input.Search
          aria-label="Filter saved listings"
          placeholder="Filter favorites by address or area"
          value={filter}
          allowClear
          onChange={(e) => setFilter(e.target.value)}
        />
        <p className="muted small">
          Select 2–4 listings to compare side by side.
        </p>
        {compare.length >= 2 && (
          <section
            className="favorites-compare"
            aria-label="Compare saved listings"
          >
            <div className="favorites-compare-heading">
              <h3>Compare {compare.length} selected listings</h3>
              <Button size="small" onClick={() => setSelected([])}>
                Clear comparison
              </Button>
            </div>
            <div className="favorites-table-scroll">
              <table aria-label="Saved listing comparison">
                <thead>
                  <tr>
                    <th>Criteria</th>
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
                    <th>Commute to USYD</th>
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
                ? "No matching saved listings"
                : "No saved listings yet. Save a listing when you find one you like."
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
                  aria-label={`Compare favorites ${listing.address}`}
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
                  Compare
                </Checkbox>
                <h3>{listing.address}</h3>
                <p className="muted">
                  {listing.suburb} · {listing.bedroom_label} bed ·{" "}
                  {listing.bathrooms} bath · {listing.car_spaces} car spaces
                </p>
                <strong>AUD {listing.weekly_rent.toLocaleString()}/week</strong>
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
                    Listing details
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
                    This property is no longer in the current catalogue. Its
                    saved record is retained.
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </Drawer>
      <Drawer
        title="Real listing details"
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
