import { Alert, Button, Form, InputNumber, Select } from "antd";
import { api } from "../../api/client";
import {
  postcodeOptions,
  scopeOptions,
  type MarketResult,
} from "../../api/realData";
import { Failure } from "../../components/Common";
import { useQueryResult } from "./useQueryResult";

export default function MarketPanel() {
  const query = useQueryResult<MarketResult>();
  const submit = (values: {
    postcode: string;
    bedrooms: number;
    rent_scope: string;
    weekly_rent?: number | null;
  }) => {
    const params = new URLSearchParams({
      postcode: values.postcode,
      bedrooms: String(values.bedrooms),
      rent_scope: values.rent_scope,
    });
    if (values.weekly_rent != null)
      params.set("weekly_rent", String(values.weekly_rent));
    void query.run(() => api<MarketResult>(`/real-data/market?${params}`));
  };
  return (
    <section className="panel real-panel">
      <h2>Historical rent for the same postcode and layout</h2>
      <p>
        Uses real NSW Government data. Choose a one- or two-bedroom apartment to
        see the sample size, median and middle 50% rent range.
      </p>
      <Form
        layout="vertical"
        initialValues={{
          postcode: "2050",
          bedrooms: 1,
          rent_scope: "whole_property",
        }}
        onFinish={submit}
        onValuesChange={query.clear}
      >
        <div className="real-form-grid">
          <Form.Item
            name="postcode"
            label="Reference postcode"
            rules={[{ required: true }]}
          >
            <Select options={postcodeOptions} />
          </Form.Item>
          <Form.Item
            name="bedrooms"
            label="Apartment bedrooms"
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { value: 1, label: "One-bedroom apartment" },
                { value: 2, label: "Two-bedroom apartment" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="rent_scope"
            label="Rent pricing basis"
            rules={[{ required: true }]}
          >
            <Select options={scopeOptions} />
          </Form.Item>
          <Form.Item
            name="weekly_rent"
            label="Base weekly rent (AUD, optional)"
            extra="Enter the listing rent, without personal budgets or additional bills."
          >
            <InputNumber min={0} max={100000} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Button
          type="primary"
          htmlType="submit"
          aria-label="Look up rent reference"
          loading={query.busy}
        >
          Look up rent reference
        </Button>
      </Form>
      <Failure error={query.error} />
      {query.result?.status === "scope_mismatch" && (
        <Alert
          type="info"
          showIcon
          title="Market comparisons are unavailable for rooms and per-person prices"
          description="The data covers one- and two-bedroom apartments and does not represent shared rooms. Comparable room samples are needed."
        />
      )}
      {query.result?.status === "unavailable" && (
        <Alert type="info" title="No connected data for this area or layout" />
      )}
      {query.result?.benchmarks.map((b) => (
        <article
          className="real-benchmark"
          data-testid={`market-${b.period}`}
          key={b.period}
        >
          <div className="real-result-title">
            <h3>
              {b.period === "2026-09"
                ? "September 2026 · registered samples"
                : "2026 Q2 · official statistics"}
            </h3>
            <span className="muted">
              {b.official_statistic
                ? "Government-published statistics"
                : "Calculated from government source data"}
            </span>
          </div>
          <div className="real-stat-grid">
            <div>
              <span>Median weekly rent</span>
              <strong>A${b.median.toLocaleString()}</strong>
            </div>
            <div>
              <span>Middle 50% rent range</span>
              <strong>
                A${b.q25.toLocaleString()}–{b.q75.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>New bond registrations</span>
              <strong>{b.sample_size} records</strong>
            </div>
          </div>
          {b.difference_aud != null && (
            <p>
              {b.difference_aud === 0
                ? "The entered rent matches the sample median."
                : `The entered rent is A$${Math.abs(b.difference_aud)} (${Math.abs(b.difference_percent ?? 0).toFixed(1)}%) ${b.difference_aud > 0 ? "higher" : "lower"} than the sample median.`}{" "}
              This difference does not establish whether a listing is fairly
              priced or safe.
            </p>
          )}
          <a href={b.source_url} target="_blank" rel="noreferrer">
            View government data source
          </a>
        </article>
      ))}
      <p className="muted">
        The statistics cover an earlier period. A postcode may include multiple
        suburbs; floor area, furnishings, floor level and bills are not
        controlled. These references are separate from personal preference
        scores and do not guarantee future rent.
      </p>
    </section>
  );
}
