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
  whole_property: "Whole property",
  per_room: "Room",
  per_person: "Per person",
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
        <h2>Record a real listing you found</h2>
        <a href={downloadUrl(`${path}/export`)}>
          Download real listing records
        </a>
      </div>
      <p>
        Enter what you observed, including the source and observation time. This
        saves an observation only. Missing facts stay unknown; it does not enter
        recommendations, selection or contract workflows yet.
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
            label="Property address or location description"
            rules={[{ required: true, whitespace: true, max: 300 }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_url"
            label="Original listing link"
            rules={[{ required: true, type: "url" }]}
          >
            <Input placeholder="https://…" />
          </Form.Item>
          <Form.Item
            name="postcode"
            label="Property postcode"
            rules={[{ required: true }]}
          >
            <Select options={postcodeOptions} />
          </Form.Item>
          <Form.Item
            name="weekly_rent"
            label="Weekly rent (AUD)"
            rules={[{ required: true }]}
          >
            <InputNumber min={0} max={100000} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="rent_scope"
            label="Listing pricing basis"
            rules={[{ required: true }]}
          >
            <Select options={scopeOptions} />
          </Form.Item>
          <Form.Item name="bedrooms" label="Bedrooms (leave blank if unknown)">
            <InputNumber
              min={0}
              max={20}
              precision={0}
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Form.Item name="bills_included" label="Bills included?">
            <Select
              allowClear
              placeholder="Unknown"
              options={[
                { value: "yes", label: "Bills included" },
                { value: "no", label: "Bills excluded" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="observed_at"
            label="Actual observation time (with timezone)"
            rules={[{ required: true }]}
            extra="Defaults to when you opened this form. For an older listing, enter the actual observation time."
          >
            <Input />
          </Form.Item>
          <Form.Item name="latitude" label="Property latitude (optional)">
            <InputNumber min={-90} max={90} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="longitude" label="Property longitude (optional)">
            <InputNumber min={-180} max={180} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Button
          type="primary"
          htmlType="submit"
          loading={action.busy}
          disabled={items.length >= 30}
        >
          Save real listing record
        </Button>
      </Form>
      <Failure error={action.error} retry={action.retry} />
      <Failure error={error} retry={() => void reload()} />
      <div data-testid="saved-real-listings">
        <h3>Saved {items.length} / 30 records</h3>
        {!items.length && (
          <p className="muted">No real listing observations yet.</p>
        )}
        {items.map((item) => (
          <article className="real-record" key={item.record_id}>
            <div className="real-result-title">
              <h3>{item.address}</h3>
              <span className="muted">
                Not assessed ·{" "}
                {item.freshness === "within_24h"
                  ? "Observed within 24 hours"
                  : "Observed more than 24 hours ago"}
              </span>
            </div>
            <p>
              A${item.weekly_rent}/week · {scopeLabel[item.rent_scope]} ·{" "}
              {item.bills_included == null
                ? "Bills unknown"
                : item.bills_included
                  ? "Bills included"
                  : "Bills excluded"}
            </p>
            <p className="muted">Observed at {item.observed_at}</p>
            <details>
              <summary>Listing details</summary>
              <a href={item.source_url} target="_blank" rel="noreferrer">
                View original source
              </a>
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
                  View location on map
                </a>
                <Button
                  onClick={() =>
                    onPoint({
                      latitude: item.latitude!,
                      longitude: item.longitude!,
                    })
                  }
                >
                  Check commute from these coordinates
                </Button>
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
