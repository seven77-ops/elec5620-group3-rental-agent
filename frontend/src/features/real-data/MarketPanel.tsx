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
      <h2>同邮区、同户型的历史租金</h2>
      <p>
        已接入 NSW 政府真实数据。选择一卧或两卧公寓，查看样本量、中位数和中间
        50% 的租金范围。
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
            label="参考邮区"
            rules={[{ required: true }]}
          >
            <Select options={postcodeOptions} />
          </Form.Item>
          <Form.Item
            name="bedrooms"
            label="公寓卧室数"
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { value: 1, label: "一卧公寓" },
                { value: 2, label: "两卧公寓" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="rent_scope"
            label="租金计价对象"
            rules={[{ required: true }]}
          >
            <Select options={scopeOptions} />
          </Form.Item>
          <Form.Item
            name="weekly_rent"
            label="房源基础周租（AUD，可留空）"
            extra="填写房源租金，不填写个人预算或加上账单后的总费用。"
          >
            <InputNumber min={0} max={100000} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Button
          type="primary"
          htmlType="submit"
          aria-label="查询租金参考"
          loading={query.busy}
        >
          查询租金参考
        </Button>
      </Form>
      <Failure error={query.error} />
      {query.result?.status === "scope_mismatch" && (
        <Alert
          type="info"
          showIcon
          title="单间和按人报价暂不提供市场比较"
          description="当前数据按一卧/两卧公寓统计，不能代表合租单间。需要同类单间样本后才能比较。"
        />
      )}
      {query.result?.status === "unavailable" && (
        <Alert type="info" title="当前区域或户型尚无接入数据" />
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
                ? "2026 年 9 月 · 登记样本"
                : "2026 年第二季度 · 官方统计"}
            </h3>
            <span className="muted">
              {b.official_statistic
                ? "政府公布的统计值"
                : "根据政府原始数据计算"}
            </span>
          </div>
          <div className="real-stat-grid">
            <div>
              <span>周租中位数</span>
              <strong>A${b.median.toLocaleString()}</strong>
            </div>
            <div>
              <span>中间 50% 租金范围</span>
              <strong>
                A${b.q25.toLocaleString()}–{b.q75.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>新增押金登记样本</span>
              <strong>{b.sample_size} 条</strong>
            </div>
          </div>
          {b.difference_aud != null && (
            <p>
              {b.difference_aud === 0
                ? "所填周租与该样本中位数相同。"
                : `所填周租比该样本中位数${b.difference_aud > 0 ? "高" : "低"} A$${Math.abs(b.difference_aud)}（${Math.abs(b.difference_percent ?? 0).toFixed(1)}%）。`}{" "}
              这一差值不代表房源是否合理或安全。
            </p>
          )}
          <a href={b.source_url} target="_blank" rel="noreferrer">
            查看政府数据来源
          </a>
        </article>
      ))}
      <p className="muted">
        统计期间不是今天。邮区可能包含多个
        suburb；未控制面积、家具、楼层和账单。这里的参考值独立于个人偏好匹配分，不用于保证未来租金。
      </p>
    </section>
  );
}
