import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Drawer,
  Empty,
  Form,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
} from "antd";
import { api, downloadUrl, newRequestId, post } from "../api/client";
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
import { useAction } from "../components/useAction";
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
  const { current, refresh, go } = useCase();
  const { message } = App.useApp();
  const [form] = Form.useForm<HousingFilters>();
  const [filters, setFilters] = useState<HousingFilters>({ sort: "rent_asc" });
  const filtersTouched = useRef(false);
  const [context, setContext] = useState<RecommendationContext | null>(null);
  const [contextReady, setContextReady] = useState(false);
  const [manualFilters, setManualFilters] = useState(false);
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
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [reportError, setReportError] = useState<unknown>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportRevision, setReportRevision] = useState(0);
  const latest = current.evaluations.at(-1)?.run_id;
  const action = useAction();
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
    setEvaluation(null);
    setReportLoading(true);
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
        if (usable) setEvaluation(r);
        if (!filtersTouched.current) {
          const savedFilters = usable ? r!.report.filters! : ctx.filters;
          setFilters(savedFilters);
          form.resetFields();
          form.setFieldsValue(savedFilters);
          setManualFilters(usable && r!.report.filter_source === "manual");
          setPage(1);
        }
        setContextReady(true);
      })
      .catch((e) => {
        if (valid) setReportError(e);
      })
      .finally(() => {
        if (valid) setReportLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [current.case_id, confirmed?.fingerprint, latest, reportRevision, form]);
  const report = evaluation?.report;
  const reportFilters = (report as unknown as { filters?: HousingFilters })
    ?.filters;
  const reportCurrent = Boolean(
    report &&
    confirmed &&
    !reportLoading &&
    !filterDirty &&
    report.mapping_policy === context?.mapping_policy &&
    !reportError &&
    report.profile_version === confirmed.version &&
    report.profile_fingerprint === confirmed.fingerprint &&
    report.dataset_fingerprint === result?.catalog.fingerprint &&
    filterKey(reportFilters ?? {}) === filterKey(filters),
  );
  const generate = () => {
    if (!confirmed) return;
    const body = {
      request_id: newRequestId(),
      confirmation_version: confirmed.version,
      ...(manualFilters ? { filters } : {}),
    };
    void action.run(async () => {
      const value = await post<Evaluation>(
        `/cases/${current.case_id}/evaluations`,
        body,
      );
      setEvaluation(value);
      const applied = value.report.filters!;
      setFilters(applied);
      form.resetFields();
      form.setFieldsValue(applied);
      setFilterDirty(false);
      setPage(1);
      await refresh();
      message.success("真实候选报告已保存。");
    });
  };
  const selection =
    current.selection?.data_mode === "real_listings" ? current.selection : null;
  return (
    <>
      <PageTitle
        title="真实房源推荐"
        extra={
          <Space wrap>
            <FavoritesDrawer
              commuteMode={filters.usyd_mode}
              selectionSource={{ filters }}
            />
            <Button onClick={() => go("assistant")}>用对话找房</Button>
            <Button onClick={() => go("assistant?needs=1")}>
              我的租房需求
            </Button>
          </Space>
        }
      />
      <Form
        form={form}
        disabled={action.busy}
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
          setManualFilters(true);
          setFilterDirty(false);
          setFilters({ ...clean, sort: clean.sort ?? "rent_asc" });
          setPage(1);
        }}
      >
        <Form.Item name="suburb" label="区域">
          <Select
            aria-label="房源区域"
            allowClear
            showSearch
            placeholder="全部区域"
            options={
              result?.catalog.suburbs.map((s) => ({ value: s, label: s })) ?? []
            }
          />
        </Form.Item>
        <Form.Item name="min_bedrooms" label="至少卧室数">
          <InputNumber
            aria-label="至少卧室数"
            min={0}
            max={100}
            precision={0}
          />
        </Form.Item>
        <Form.Item name="min_bathrooms" label="至少浴室数">
          <InputNumber
            aria-label="至少浴室数"
            min={0}
            max={100}
            precision={0}
          />
        </Form.Item>
        <Form.Item name="min_car_spaces" label="至少车位数">
          <InputNumber
            aria-label="至少车位数"
            min={0}
            max={100}
            precision={0}
          />
        </Form.Item>
        <Form.Item name="max_weekly_rent" label="最高周租（AUD）">
          <InputNumber
            aria-label="最高周租（AUD）"
            min={0}
            max={1000000000000}
          />
        </Form.Item>
        <Form.Item name="usyd_mode" label="到校通勤方式">
          <Select
            virtual={false}
            aria-label="到校通勤方式"
            allowClear
            placeholder="公共交通"
            options={commuteModes}
          />
        </Form.Item>
        <Form.Item name="usyd_max_minutes" label="到悉大最多（分钟）">
          <InputNumber
            aria-label="到悉大最多（分钟）"
            min={1}
            max={240}
            precision={0}
          />
        </Form.Item>

        <Form.Item name="usyd_max_transfers" hidden>
          <InputNumber min={0} max={5} precision={0} />
        </Form.Item>

        <Form.Item name="sort" label="排序">
          <Select
            aria-label="房源排序"
            options={[
              { value: "rent_asc", label: "周租从低到高" },
              { value: "rent_desc", label: "周租从高到低" },
              { value: "bedrooms_desc", label: "卧室数从多到少" },
            ]}
          />
        </Form.Item>
        <Space wrap className="real-catalog-filter-actions">
          <Button
            type="primary"
            htmlType="submit"
            aria-label="应用筛选"
            loading={loading}
          >
            应用筛选
          </Button>
          <Button
            onClick={() => {
              filtersTouched.current = true;
              form.resetFields();
              form.setFieldsValue(context?.filters ?? { sort: "rent_asc" });
              setFilters(context?.filters ?? { sort: "rent_asc" });
              setManualFilters(false);
              setFilterDirty(false);
              setPage(1);
            }}
          >
            恢复偏好筛选
          </Button>
        </Space>
      </Form>
      <Failure error={error} retry={() => setRevision((v) => v + 1)} />
      <Failure
        error={reportError}
        retry={() => setReportRevision((v) => v + 1)}
      />
      <Failure error={action.error} retry={action.retry} />
      {selection && (
        <Suspense fallback={null}>
          <CandidateFollowup />
        </Suspense>
      )}
      <div className="report-actions">
        <Space wrap>
          <Button
            type="primary"
            loading={action.busy || reportLoading}
            aria-label="生成当前筛选的候选报告"
            disabled={
              !confirmed ||
              !contextReady ||
              loading ||
              filterDirty ||
              Boolean(error)
            }
            onClick={generate}
          >
            生成当前筛选的候选报告
          </Button>
          {!confirmed && (
            <Button onClick={() => go("preferences")}>先确认租房偏好</Button>
          )}
          {report && (
            <a href={downloadUrl(`/evaluations/${evaluation!.run_id}/export`)}>
              下载真实候选报告
            </a>
          )}
          {reportCurrent && (
            <Tag color="blue">
              当前偏好 v{report!.profile_version} · 候选报告已保存
            </Tag>
          )}
        </Space>
      </div>
      {filterDirty && (
        <Alert
          type="warning"
          title="筛选条件已编辑，请先点击应用筛选。"
          showIcon
        />
      )}
      <p className="real-save-hint muted">
        可以直接选定一套开始跟进，也可以收藏多套再比较。
      </p>
      <section className="panel real-catalog-table" data-testid="real-catalog">
        <h2>
          筛选结果 ·{" "}
          {loading ? "读取中" : error ? "读取失败" : (result?.total ?? 0)} 条
        </h2>
        {filterChange?.key === filterKey(filters) && !loading && !error && (
          <p className="recommendation-change-summary" role="status">
            {filterChange.label} · 房源 {filterChange.before} →{" "}
            {result?.total ?? 0} 套
          </p>
        )}
        {!loading &&
          !error &&
          result?.total === 0 &&
          alternatives.length > 0 && (
            <div
              className="recommendation-alternatives"
              aria-label="无结果调整方案"
            >
              <p>只调整下面一项，其余条件保持不变：</p>
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
                    setManualFilters(true);
                    setFilterDirty(false);
                  }}
                >
                  {option.label} ·{" "}
                  {option.count ? `可找到 ${option.count} 套` : "仍无匹配"}
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
              <Empty description="没有符合当前条件的房源。可调整预算、房型或明确放宽到校通勤时间。" />
            ),
          }}
          pagination={{
            current: page,
            pageSize: 20,
            total: error ? 0 : (result?.total ?? 0),
            showSizeChanger: false,
            onChange: setPage,
            showTotal: (total) => `共 ${total} 条`,
          }}
          columns={[
            {
              title: "房源",
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
              title: "卧室",
              dataIndex: "bedrooms",
              width: 115,
              render: (value, row) => row.bedroom_label ?? value,
            },
            { title: "浴室", dataIndex: "bathrooms", width: 75 },
            { title: "车位", dataIndex: "car_spaces", width: 75 },
            {
              title: "周租",
              dataIndex: "weekly_rent",
              width: 140,
              render: (value) => `AUD ${Number(value).toLocaleString()}/周`,
            },
            {
              title: "到悉大",
              key: "usyd",
              width: 150,
              render: (_, row) => (
                <UsydCommuteMini listing={row} mode={filters.usyd_mode} />
              ),
            },
            {
              title: "操作",
              key: "actions",
              width: 320,
              render: (_, r) => (
                <Space wrap>
                  <Button
                    size="small"
                    aria-label="查看房源详情"
                    disabled={loading || Boolean(error)}
                    onClick={() =>
                      setDetail({
                        ...r,
                        recommendation_mode: filters.usyd_mode,
                      })
                    }
                  >
                    详情
                  </Button>
                  <ListingActions
                    listing={r}
                    onSelect={(listing) =>
                      favorites.choose(listing, { filters })
                    }
                    disabled={loading || Boolean(error) || action.busy}
                  />
                </Space>
              ),
            },
          ]}
        />
      </section>
      <p className="muted small">
        到校路线：
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
          地图纠错
        </a>{" "}
        · 公共交通：
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
        title="房源详情"
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        size="large"
      >
        {detail && <ListingDetails key={detail.listing_id} listing={detail} />}
      </Drawer>
    </>
  );
}
