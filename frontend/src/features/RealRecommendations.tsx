import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Empty,
  Form,
  InputNumber,
  Select,
  Space,
  Table,
} from "antd";
import { api, post } from "../api/client";
import type { Evaluation } from "../api/types";
import type {
  HousingAd,
  HousingFilters,
  HousingPage,
  RecommendationContext,
} from "../api/catalog";
import { filterKey } from "../api/catalog";
import { currentConfirmation, useCase } from "../app/context";
import { Failure, PageTitle } from "../components/Common";
import { ListingThumbnail } from "./real-data/ListingPhotos";

import { UsydCommuteMini, commuteModes } from "./real-data/UsydCommute";
import ListingDetails from "./real-data/ListingDetails";
import ListingActions from "./favorites/ListingActions";
import { useFavorites } from "./favorites/FavoritesContext";
import FavoritesDrawer from "./favorites/FavoritesDrawer";
import ListingReasons from "./assistant/ListingReasons";
import type { RecommendationAlternative } from "../api/assistant";
const CandidateFollowup = lazy(() => import("./candidate/CandidateFollowup"));

export default function RealRecommendations() {
  const { current, go } = useCase();
  const [form] = Form.useForm<HousingFilters>();
  const [filters, setFilters] = useState<HousingFilters>({ sort: "rent_asc" });
  const filtersTouched = useRef(false);
  const [context, setContext] = useState<RecommendationContext | null>(null);
  const [contextReady, setContextReady] = useState(false);
  const [filterDirty, setFilterDirty] = useState(false);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<HousingPage | null>(null);
  const [alternatives, setAlternatives] = useState<RecommendationAlternative[]>(
    [],
  );
  const [filterChange, setFilterChange] = useState<{
    key: string;
    label: string;
    before: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [revision, setRevision] = useState(0);
  const [detail, setDetail] = useState<HousingAd | null>(null);
  const [reportError, setReportError] = useState<unknown>(null);
  const [reportRevision, setReportRevision] = useState(0);
  const latest = current.evaluations.at(-1)?.run_id;
  const favorites = useFavorites();
  const confirmed = currentConfirmation(current);
  useEffect(() => {
    if (!contextReady) return;
    let valid = true;
    setLoading(true);
    setError(null);
    setDetail(null);
    const query = new URLSearchParams({ page: String(page), page_size: "20" });
    Object.entries(filters).forEach(([k, v]) => {
      if (v != null) query.set(k, String(v));
    });
    api<HousingPage>(
      `/listings?case_id=${encodeURIComponent(current.case_id)}&${query}`,
    )
      .then((value) => {
        if (valid) setResult(value);
      })
      .catch((e) => {
        if (valid) setError(e);
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [filters, page, revision, contextReady]);
  useEffect(() => {
    let valid = true;
    setAlternatives([]);
    if (loading || error || !result || result.total !== 0) return;
    post<{ alternatives: RecommendationAlternative[] }>(
      `/cases/${encodeURIComponent(current.case_id)}/assistant/recommendation-preview`,
      { filters },
    )
      .then((value) => {
        if (valid) setAlternatives(value.alternatives);
      })
      .catch(() => {
        if (valid) setAlternatives([]);
      });
    return () => {
      valid = false;
    };
  }, [current.case_id, result, filters, loading, error]);
  useEffect(() => {
    let valid = true;
    setReportError(null);
    setContextReady(false);
    Promise.all([
      api<RecommendationContext>(
        `/cases/${current.case_id}/recommendation-context`,
      ),
      latest
        ? api<Evaluation>(`/evaluations/${latest}`)
        : Promise.resolve(null),
    ])
      .then(([ctx, r]) => {
        if (!valid) return;
        setContext(ctx);
        const usable =
          r?.report.data_mode === "real_listings" &&
          r.report.mapping_policy === ctx.mapping_policy &&
          r.report.profile_fingerprint === ctx.profile_fingerprint;
        if (!filtersTouched.current) {
          const savedFilters = usable ? r!.report.filters! : ctx.filters;
          setFilters(savedFilters);
          form.resetFields();
          form.setFieldsValue(savedFilters);
          setPage(1);
        }
        setContextReady(true);
      })
      .catch((e) => {
        if (valid) setReportError(e);
      });
    return () => {
      valid = false;
    };
  }, [current.case_id, confirmed?.fingerprint, latest, reportRevision, form]);
  const selection =
    current.selection?.data_mode === "real_listings" ? current.selection : null;
  return (
    <>
      <PageTitle
        title="Housing recommendations"
        extra={
          <Space wrap>
            <FavoritesDrawer
              commuteMode={filters.usyd_mode}
              selectionSource={{ filters }}
            />
            <Button onClick={() => go("assistant")}>
              Find a home through chat
            </Button>
            <Button onClick={() => go("assistant?needs=1")}>
              My rental needs
            </Button>
          </Space>
        }
      />
      <Form
        form={form}
        onValuesChange={() => {
          filtersTouched.current = true;
          setFilterDirty(true);
        }}
        layout="vertical"
        initialValues={{ sort: "rent_asc" }}
        className="panel real-catalog-filters"
        onFinish={(values) => {
          const clean = Object.fromEntries(
            Object.entries(values).filter(([, v]) => v != null && v !== ""),
          ) as HousingFilters;
          filtersTouched.current = true;
          setFilterDirty(false);
          setFilters({ ...clean, sort: clean.sort ?? "rent_asc" });
          setPage(1);
        }}
      >
        <Form.Item name="suburb" label="Area">
          <Select
            aria-label="Listing area"
            allowClear
            showSearch
            placeholder="All areas"
            options={
              result?.catalog.suburbs.map((s) => ({ value: s, label: s })) ?? []
            }
          />
        </Form.Item>
        <Form.Item name="min_bedrooms" label="Minimum bedrooms">
          <InputNumber
            aria-label="Minimum bedrooms"
            min={0}
            max={100}
            precision={0}
          />
        </Form.Item>
        <Form.Item name="min_bathrooms" label="Minimum bathrooms">
          <InputNumber
            aria-label="Minimum bathrooms"
            min={0}
            max={100}
            precision={0}
          />
        </Form.Item>
        <Form.Item name="min_car_spaces" label="Minimum car spaces">
          <InputNumber
            aria-label="Minimum car spaces"
            min={0}
            max={100}
            precision={0}
          />
        </Form.Item>
        <Form.Item name="max_weekly_rent" label="Maximum weekly rent (AUD)">
          <InputNumber
            aria-label="Maximum weekly rent (AUD)"
            min={0}
            max={1000000000000}
          />
        </Form.Item>
        <Form.Item name="usyd_mode" label="Commute mode to campus">
          <Select
            virtual={false}
            aria-label="Commute mode to campus"
            allowClear
            placeholder="Public transport"
            options={commuteModes}
          />
        </Form.Item>
        <Form.Item
          name="usyd_max_minutes"
          label="Maximum commute to USYD (minutes)"
        >
          <InputNumber
            aria-label="Maximum commute to USYD (minutes)"
            min={1}
            max={240}
            precision={0}
          />
        </Form.Item>

        <Form.Item name="usyd_max_transfers" hidden>
          <InputNumber min={0} max={5} precision={0} />
        </Form.Item>

        <Form.Item name="sort" label="Sort">
          <Select
            aria-label="Listing sort order"
            options={[
              { value: "rent_asc", label: "Weekly rent: low to high" },
              { value: "rent_desc", label: "Weekly rent: high to low" },
              { value: "bedrooms_desc", label: "Bedrooms: most first" },
            ]}
          />
        </Form.Item>
        <Space wrap className="real-catalog-filter-actions">
          <Button
            type="primary"
            htmlType="submit"
            aria-label="Apply filters"
            loading={loading}
          >
            Apply filters
          </Button>
          <Button
            onClick={() => {
              filtersTouched.current = true;
              form.resetFields();
              form.setFieldsValue(context?.filters ?? { sort: "rent_asc" });
              setFilters(context?.filters ?? { sort: "rent_asc" });
              setFilterDirty(false);
              setPage(1);
            }}
          >
            Restore preference filters
          </Button>
        </Space>
      </Form>
      <Failure error={error} retry={() => setRevision((v) => v + 1)} />
      <Failure
        error={reportError}
        retry={() => setReportRevision((v) => v + 1)}
      />
      {selection && (
        <Suspense fallback={null}>
          <CandidateFollowup />
        </Suspense>
      )}
      {filterDirty && (
        <Alert
          type="warning"
          title="Filters have been edited. Apply the filters first."
          showIcon
        />
      )}
      <p className="real-save-hint muted">
        Select a property to start follow-up, or save several listings and
        compare them.
      </p>
      <section className="panel real-catalog-table" data-testid="real-catalog">
        <h2>
          Filtered results ·{" "}
          {loading
            ? "Loading"
            : error
              ? "Could not load"
              : (result?.total ?? 0)}{" "}
          records
        </h2>
        {filterChange?.key === filterKey(filters) && !loading && !error && (
          <p className="recommendation-change-summary" role="status">
            {filterChange.label} · Listings {filterChange.before} →{" "}
            {result?.total ?? 0} properties
          </p>
        )}
        {!loading &&
          !error &&
          result?.total === 0 &&
          alternatives.length > 0 && (
            <div
              className="recommendation-alternatives"
              aria-label="Options when there are no matches"
            >
              <p>Adjust one item below and keep the other criteria:</p>
              {alternatives.map((option) => (
                <Button
                  key={option.id}
                  disabled={option.count === 0}
                  onClick={() => {
                    const next = { ...filters };
                    if (option.patch.budget_amount != null)
                      next.max_weekly_rent = option.patch.budget_amount;
                    if (option.patch.commute_max_minutes != null)
                      next.usyd_max_minutes = option.patch.commute_max_minutes;
                    if (option.patch.suburb === null) delete next.suburb;
                    setFilterChange({
                      key: filterKey(next),
                      label: option.label,
                      before: 0,
                    });
                    filtersTouched.current = true;
                    form.resetFields();
                    form.setFieldsValue(next);
                    setFilters(next);
                    setPage(1);
                    setFilterDirty(false);
                  }}
                >
                  {option.label} ·{" "}
                  {option.count
                    ? `Matches available: ${option.count} properties`
                    : "Still no matches"}
                </Button>
              ))}
            </div>
          )}
        <Table<HousingAd>
          rowKey="listing_id"
          loading={loading}
          dataSource={error ? [] : (result?.items ?? [])}
          scroll={{ x: 980 }}
          locale={{
            emptyText: (
              <Empty description="No listings match these criteria. Adjust budget or housing needs, or explicitly increase the campus commute limit." />
            ),
          }}
          pagination={{
            current: page,
            pageSize: 20,
            total: error ? 0 : (result?.total ?? 0),
            showSizeChanger: false,
            onChange: setPage,
            showTotal: (total) => `Total ${total} records`,
          }}
          columns={[
            {
              title: "Listings",
              dataIndex: "address",
              key: "address",
              width: 300,
              render: (_, r) => (
                <div className="listing-photo-address">
                  <ListingThumbnail
                    key={`${r.listing_id}:${r.photos?.[0]?.url ?? "none"}`}
                    listing={r}
                    onOpen={() =>
                      setDetail({
                        ...r,
                        recommendation_mode: filters.usyd_mode,
                      })
                    }
                  />
                  <div>
                    <strong>{r.address}</strong>
                    <div className="muted">
                      {r.suburb} · {r.postcode}
                    </div>
                    <ListingReasons listing={r} filters={filters} />
                  </div>
                </div>
              ),
            },
            {
              title: "Bedrooms",
              dataIndex: "bedrooms",
              width: 115,
              render: (value, row) => row.bedroom_label ?? value,
            },
            { title: "Bathrooms", dataIndex: "bathrooms", width: 75 },
            { title: "car spaces", dataIndex: "car_spaces", width: 75 },
            {
              title: "Weekly rent",
              dataIndex: "weekly_rent",
              width: 140,
              render: (value) => `AUD ${Number(value).toLocaleString()}/week`,
            },
            {
              title: "To USYD",
              key: "usyd",
              width: 150,
              render: (_, row) => (
                <UsydCommuteMini listing={row} mode={filters.usyd_mode} />
              ),
            },
            {
              title: "Actions",
              key: "actions",
              width: 320,
              render: (_, r) => (
                <Space wrap>
                  <Button
                    size="small"
                    aria-label="View listing details"
                    disabled={loading || Boolean(error)}
                    onClick={() =>
                      setDetail({
                        ...r,
                        recommendation_mode: filters.usyd_mode,
                      })
                    }
                  >
                    Details
                  </Button>
                  <ListingActions
                    listing={r}
                    onSelect={(listing) =>
                      favorites.choose(listing, { filters })
                    }
                    disabled={loading || Boolean(error)}
                  />
                </Space>
              ),
            },
          ]}
        />
      </section>
      <p className="muted small">
        Route to campus:
        <a
          href="https://routing.openstreetmap.de/about.html"
          target="_blank"
          rel="noopener noreferrer"
        >
          © OpenStreetMap contributors · FOSSGIS
        </a>{" "}
        ·{" "}
        <a
          href="https://www.openstreetmap.org/fixthemap"
          target="_blank"
          rel="noopener noreferrer"
        >
          Correct map location
        </a>{" "}
        · Public transport:
        <a
          href="https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis"
          target="_blank"
          rel="noopener noreferrer"
        >
          Transport for NSW
        </a>
      </p>
      <Drawer
        rootClassName="usyd-listing-drawer"
        title="Listing details"
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        size="large"
      >
        {detail && <ListingDetails key={detail.listing_id} listing={detail} />}
      </Drawer>
    </>
  );
}
