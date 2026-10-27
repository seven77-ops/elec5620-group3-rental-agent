import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Form, Input, InputNumber, Select } from "antd";
import { useCase } from "../../app/context";
import { api, downloadUrl, newRequestId, post } from "../../api/client";
import {
  mapUrl,
  postcodeOptions,
  scopeOptions,
  type Point,
  type RealListing,
} from "../../api/realData";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";

const scopeLabel: Record<string, string> = {
  whole_property: "整套",
  per_room: "单间",
  per_person: "按人",
};
export default function ListingPanel({
  onPoint,
}: {
  onPoint: (p: Point) => void;
}) {
  const { current } = useCase();
  const path = `/cases/${current.case_id}/real-listings`;
  const [items, setItems] = useState<RealListing[]>([]);
  const [error, setError] = useState<unknown>(null);
  const mounted = useRef(true);
  const readRevision = useRef(0);
  const action = useAction();
  const reload = useCallback(async () => {
    const revision = ++readRevision.current;
    try {
      const result = await api<{ items: RealListing[] }>(path);
      if (mounted.current && revision === readRevision.current) {
        setItems(result.items);
        setError(null);
      }
    } catch (e) {
      if (mounted.current && revision === readRevision.current) setError(e);
    }
  }, [path]);
  useEffect(() => {
    mounted.current = true;
    void reload();
    return () => {
      mounted.current = false;
    };
  }, [reload]);
  const [observed] = useState(() =>
    new Date(Date.now() - 60_000).toISOString(),
  );
  return (
    <section className="panel real-panel">
      <div className="real-result-title">
        <h2>记录已找到的真实房源</h2>
        <a href={downloadUrl(`${path}/export`)}>下载真实房源记录</a>
      </div>
      <p>
        填入你实际看到的信息，并保留来源与观察时间。只保存观察记录；缺少的事实保持未知，尚不进入推荐、选房或合同流程。
      </p>
      <Form
        layout="vertical"
        initialValues={{
          postcode: "2050",
          rent_scope: "whole_property",
          observed_at: observed,
        }}
        onFinish={(values) => {
          const body = {
            request_id: newRequestId(),
            listing: {
              ...values,
              bills_included:
                values.bills_included === "yes"
                  ? true
                  : values.bills_included === "no"
                    ? false
                    : null,
            },
          };
          void action.run(async () => {
            await post(path, body);
            await reload();
          });
        }}
      >
        <div className="real-form-grid">
          <Form.Item
            name="address"
            label="房源地址或位置说明"
            rules={[{ required: true, whitespace: true, max: 300 }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_url"
            label="原始房源链接"
            rules={[{ required: true, type: "url" }]}
          >
            <Input placeholder="https://…" />
          </Form.Item>
          <Form.Item
            name="postcode"
            label="房源邮区"
            rules={[{ required: true }]}
          >
            <Select options={postcodeOptions} />
          </Form.Item>
          <Form.Item
            name="weekly_rent"
            label="周租（AUD）"
            rules={[{ required: true }]}
          >
            <InputNumber min={0} max={100000} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="rent_scope"
            label="房源计价对象"
            rules={[{ required: true }]}
          >
            <Select options={scopeOptions} />
          </Form.Item>
          <Form.Item name="bedrooms" label="卧室数（未知留空）">
            <InputNumber
              min={0}
              max={20}
              precision={0}
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Form.Item name="bills_included" label="是否含账单">
            <Select
              allowClear
              placeholder="未知"
              options={[
                { value: "yes", label: "含账单" },
                { value: "no", label: "不含账单" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="observed_at"
            label="实际观察时间（带时区）"
            rules={[{ required: true }]}
            extra="默认是本次打开表单的时间。录入旧房源时，请改为实际观察时间。"
          >
            <Input />
          </Form.Item>
          <Form.Item name="latitude" label="房源纬度（可留空）">
            <InputNumber min={-90} max={90} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="longitude" label="房源经度（可留空）">
            <InputNumber min={-180} max={180} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Button
          type="primary"
          htmlType="submit"
          loading={action.busy}
          disabled={items.length >= 30}
        >
          保存真实房源记录
        </Button>
      </Form>
      <Failure error={action.error} retry={action.retry} />
      <Failure error={error} retry={() => void reload()} />
      <div data-testid="saved-real-listings">
        <h3>已保存 {items.length} / 30 条</h3>
        {!items.length && <p className="muted">还没有真实房源观察记录。</p>}
        {items.map((item) => (
          <article className="real-record" key={item.record_id}>
            <div className="real-result-title">
              <h3>{item.address}</h3>
              <span className="muted">
                尚未评估 ·{" "}
                {item.freshness === "within_24h"
                  ? "观察记录在24小时内"
                  : "观察记录已超过24小时"}
              </span>
            </div>
            <p>
              A${item.weekly_rent}/周 · {scopeLabel[item.rent_scope]} ·{" "}
              {item.bills_included == null
                ? "账单范围未知"
                : item.bills_included
                  ? "含账单"
                  : "不含账单"}
            </p>
            <p className="muted">观察时间 {item.observed_at}</p>
              <details>
                <summary>房源详情</summary>
                <a href={item.source_url} target="_blank" rel="noreferrer">查看原始来源</a>
              </details>
            {item.latitude != null && item.longitude != null && (
              <>
                <a
                  href={mapUrl({
                    latitude: item.latitude,
                    longitude: item.longitude,
                  })}
                  target="_blank"
                  rel="noreferrer"
                >
                  在地图查看位置
                </a>
                <Button
                  onClick={() =>
                    onPoint({
                      latitude: item.latitude!,
                      longitude: item.longitude!,
                    })
                  }
                >
                  用此坐标查通勤
                </Button>
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
