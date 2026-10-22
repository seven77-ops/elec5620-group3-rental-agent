import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Collapse,
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
import { Failure, PageTitle, Loading } from "../components/Common";
import { useAction } from "../components/useAction";
import { ListingThumbnail } from "./real-data/ListingPhotos";

import ListingDetails from "./real-data/ListingDetails";
import { housingCopy } from "./real-data/listingPresentation";

const CandidateFollowup = lazy(() => import("./candidate/CandidateFollowup"));

const RecommendationTools = lazy(
  () => import("./real-data/RecommendationTools"),
);

export default function RealRecommendations() {
  const { current, refresh, go } = useCase();
  const { modal, message } = App.useApp();
  const [form] = Form.useForm<HousingFilters>();
  const [filters, setFilters] = useState<HousingFilters>({ sort: "rent_asc" });
  const filtersTouched = useRef(false);
  const [context, setContext] = useState<RecommendationContext | null>(null);
  const [contextReady, setContextReady] = useState(false);
  const [manualFilters, setManualFilters] = useState(false);
  const [filterDirty, setFilterDirty] = useState(false);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<HousingPage | null>(null);
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
    api<HousingPage>(`/listings?${query}`)
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
  const allowed = new Set(
    report?.pending_confirmation.map((r) => r.listing_id) ?? [],
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
  const choose = (item: HousingAd) => {
    const body = {
      request_id: newRequestId(),
      run_id: evaluation!.run_id,
      listing_id: item.listing_id,
      confirmed: true,
    };
    return modal.confirm({
      title: "保存这条真实房源候选？",
      content: (
        <>
          <p>
            {item.address} · AUD {item.weekly_rent}/周（房源标价）
          </p>
          <p>
            保存后可准备看房询问、记录中介回复，或上传已有合同复核。房源中的在租状态、计价对象和租期仍待确认。
          </p>
        </>
      ),
      okText: "确认保存候选",
      cancelText: "继续查看",
      onOk: () =>
        action.run(async () => {
          await post(`/cases/${current.case_id}/selections`, body);
          await refresh();
          message.success("真实房源候选已保存。");
        }),
    });
  };
  const selection =
    current.selection?.data_mode === "real_listings" ? current.selection : null;
  return (
    <>
      <PageTitle
        title="真实房源推荐"
        description="按预算与房屋条件，找到适合你的住处。"
        extra={
          <Space wrap>
            <Button onClick={() => go("assistant")}>用对话找房</Button>
            <Button onClick={() => go("assistant?needs=1")}>
              我的租房需求
            </Button>
          </Space>
        }
      />
      <section className="real-catalog-status" data-testid="catalog-summary">
        <strong>
          {result?.catalog.total ?? "—"} 条真实房源 ·{" "}
          {result?.catalog.suburb_count ?? "—"} 个区域
        </strong>
        <span className="muted">房源资料 · 在租状态待确认</span>
        <span
          data-testid="preference-linkage"
          className="real-preference-status"
        >
          {confirmed ? `已确认偏好 v${confirmed.version}` : "尚未确认偏好"}
          {confirmed && (manualFilters ? " · 手动筛选" : " · 已带入偏好")}
        </span>
      </section>
      <details className="real-catalog-notes">
        <summary>来源与筛选说明</summary>
        <p>
          卧室、浴室、车位和周租来自公开房源。Studio
          原始房源为0卧时，计为1个开放式睡眠空间，并非独立卧室。标价的计价对象、账单、在租状态和通勤均待核实。
        </p>
        <p>
          {confirmed
            ? manualFilters
              ? "手动条件可能与已确认偏好不同，可恢复偏好筛选。"
              : "已自动带入偏好的区域、卧室、浴室、车位和预算筛选方式。"
            : "可先浏览房源，确认偏好后生成候选报告。"}
        </p>
        <p>
          采集时间：
          {result
            ? new Date(result.catalog.captured_at).toLocaleString("zh-CN")
            : "读取中"}
        </p>
        {context?.unverified_preferences.length ? (
          <ul>
            {context.unverified_preferences.map((note) => (
              <li key={note}>{housingCopy(note)}</li>
            ))}
          </ul>
        ) : null}
      </details>
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
            Object.entries(values).filter(([, v]) => v != null),
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
      <p className="real-save-hint muted">生成当前筛选报告后可保存候选。</p>
      <section className="panel real-catalog-table" data-testid="real-catalog">
        <h2>
          筛选结果 ·{" "}
          {loading ? "读取中" : error ? "读取失败" : (result?.total ?? 0)} 条
        </h2>
        <Table<HousingAd>
          rowKey="listing_id"
          loading={loading}
          dataSource={error ? [] : (result?.items ?? [])}
          scroll={{ x: 980 }}
          locale={{
            emptyText: (
              <Empty description="没有符合当前筛选的真实房源，可调整区域、户型或周租。" />
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
                    onOpen={() => setDetail(r)}
                  />
                  <div>
                    <strong>{r.address}</strong>
                    <div className="muted">
                      {r.suburb} · {r.postcode}
                    </div>
                    <small>
                      {r.source_observation.detail_read
                        ? "房源资料"
                        : "房源资料"}{" "}
                      · 在租待核实
                    </small>
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
              title: "操作",
              key: "actions",
              width: 245,
              render: (_, r) => (
                <Space wrap>
                  <Button
                    size="small"
                    aria-label="查看房源详情"
                    disabled={loading || Boolean(error)}
                    onClick={() => setDetail(r)}
                  >
                    详情
                  </Button>
                  <a
                    href={r.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看房源
                  </a>
                  <Button
                    size="small"
                    disabled={
                      !reportCurrent ||
                      !allowed.has(r.listing_id) ||
                      loading ||
                      Boolean(error) ||
                      action.busy
                    }
                    onClick={() => choose(r)}
                  >
                    保存候选
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </section>
      <Collapse
        items={[
          {
            key: "tools",
            label: "房源补充工具",
            children: (
              <Suspense fallback={<Loading />}>
                <RecommendationTools />
              </Suspense>
            ),
          },
        ]}
      />
      <Drawer
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
