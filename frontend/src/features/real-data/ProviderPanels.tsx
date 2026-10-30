import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Select,
} from "antd";
import { post } from "../../api/client";
import {
  mapUrl,
  postcodeOptions,
  type DomainResult,
  type Point,
  type ProviderConfig,
  type TripResult,
} from "../../api/realData";
import { Failure } from "../../components/Common";
import { useQueryResult } from "./useQueryResult";

export function DomainPanel({
  config,
  onPoint,
}: {
  config: ProviderConfig;
  onPoint: (point: Point) => void;
}) {
  const query = useQueryResult<DomainResult>();
  const [consent, setConsent] = useState(false);
  return (
    <section className="panel real-panel">
      <h2>Search Domain for whole-property rentals</h2>
      {!config.configured && (
        <Alert
          type="info"
          showIcon
          title={
            config.key_present
              ? "Domain Usage approval required"
              : "Domain Credentials not configured"
          }
          description="Configure DOMAIN_API_KEY on the backend. Once the provider approves this application use, set DOMAIN_USE_APPROVED=1 and restart the service."
        />
      )}
      <p>
        Search the first 20 rental listings across four postcodes near USYD.
        Listing details need verification and do not automatically become formal
        recommendations.
      </p>
      <Form
        layout="vertical"
        initialValues={{ postcode: "2050", maximum_weekly_rent: 900 }}
        onValuesChange={query.clear}
        onFinish={(values) =>
          void query.run(() =>
            post("/real-data/domain-search", {
              ...values,
              allow_external: consent,
            }),
          )
        }
      >
        <div className="real-form-grid">
          <Form.Item
            label="Domain Search postcode"
            name="postcode"
            rules={[{ required: true }]}
          >
            <Select options={postcodeOptions} />
          </Form.Item>
          <Form.Item
            label="Maximum weekly rent for whole property (AUD)"
            name="maximum_weekly_rent"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={100000} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Checkbox
          checked={consent}
          disabled={query.busy}
          onChange={(e) => {
            setConsent(e.target.checked);
            query.clear();
          }}
        >
          I agree to send these area and price criteria to Domain.
        </Checkbox>
        <div>
          <Button
            type="primary"
            htmlType="submit"
            disabled={!config.configured || !consent}
            loading={query.busy}
          >
            Search Domain listings
          </Button>
        </div>
      </Form>
      <Failure error={query.error} />
      {query.result && (
        <>
          <p className="muted">Queried at: {query.result.queried_at}</p>
          {!query.result.items.length && (
            <p>No listings returned. Adjust the criteria and try again.</p>
          )}
          {query.result.items.map((item) => (
            <article className="real-record" key={item.listing_id}>
              <h3>{item.address ?? `Listings ${item.listing_id}`}</h3>
              <p>
                {item.advertised_price ?? "Price not provided"} · Bedrooms:
                {item.bedrooms ?? "Unknown"} · Not assessed
              </p>
              {item.source_url && (
                <details>
                  <summary>Listing details</summary>
                  <a href={item.source_url} target="_blank" rel="noreferrer">
                    View original listing
                  </a>
                </details>
              )}
              {item.latitude != null && item.longitude != null && (
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
              )}
            </article>
          ))}
        </>
      )}
      <a href={config.documentation} target="_blank" rel="noreferrer">
        Domain Official API and access information
      </a>
    </section>
  );
}

export function TripPanel({
  config,
  origin,
}: {
  config: ProviderConfig;
  origin: Point | null;
}) {
  const query = useQueryResult<TripResult>();
  const [consent, setConsent] = useState(false);
  const [form] = Form.useForm();
  useEffect(() => {
    if (origin) form.setFieldsValue({ origin });
  }, [origin, form]);
  return (
    <section className="panel real-panel">
      <h2>Check public transport to campus</h2>
      {!config.configured && (
        <Alert
          type="info"
          showIcon
          title="TfNSW Credentials not configured"
          description="On the backend, .env Configure TFNSW_API_KEY and restart to run live route queries. No simulated successful results are shown."
        />
      )}
      <p>
        Enter the property coordinates as the origin and the actual teaching
        building or entrance as the destination. Choose an arrival time within
        the next 30 days; the provider timetable may cover a shorter period.
      </p>
      <Form
        form={form}
        layout="vertical"
        onValuesChange={query.clear}
        onFinish={(values) => {
          void query.run(() =>
            post("/real-data/trips", {
              ...values,
              arrival_at: new Date(values.arrival_at).toISOString(),
              allow_external: consent,
            }),
          );
        }}
      >
        <div className="real-form-grid">
          <Form.Item
            label="Property latitude"
            name={["origin", "latitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-90} max={90} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="Property longitude"
            name={["origin", "longitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-180} max={180} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="Building entrance latitude"
            name={["destination", "latitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-90} max={90} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="Building entrance longitude"
            name={["destination", "longitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-180} max={180} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="Arrival time (browser local timezone)"
            name="arrival_at"
            rules={[{ required: true }]}
            extra="The server converts the date and time to Australia/Sydney."
          >
            <Input type="datetime-local" />
          </Form.Item>
        </div>
        <Checkbox
          checked={consent}
          disabled={query.busy}
          onChange={(e) => {
            setConsent(e.target.checked);
            query.clear();
          }}
        >
          I agree to send the origin, destination and arrival time to TfNSW.
        </Checkbox>
        <div>
          <Button
            type="primary"
            htmlType="submit"
            disabled={!config.configured || !consent}
            loading={query.busy}
          >
            Check actual commute
          </Button>
        </div>
      </Form>
      <Failure error={query.error} />
      {query.result && (
        <>
          <p>
            Queried at: {query.result.queried_at} · Requested arrival:
            {query.result.query.arrival_at}
          </p>
          <a
            href={mapUrl(query.result.query.destination)}
            target="_blank"
            rel="noreferrer"
          >
            View destination on map
          </a>
          {!query.result.journeys.length && (
            <Alert
              type="info"
              title="No routes available"
              description="Check the coordinates, arrival date and time, then try again."
            />
          )}
          {query.result.journeys.map((trip, i) => (
            <article className="real-record" key={i}>
              <h3>
                Route {i + 1} ·{" "}
                {trip.duration_minutes == null
                  ? "Check total duration"
                  : `${trip.duration_minutes} minutes (including waiting)`}
              </h3>
              <p>
                Walking{" "}
                {trip.walking_minutes == null
                  ? "Duration unknown"
                  : `${trip.walking_minutes} minutes`}{" "}
                · Transfers {trip.transfers ?? "Unknown"} transfers
              </p>
              <p>{trip.services.join(" → ")}</p>
              <p>
                Planned departure {trip.departure_at ?? "Unknown"} · Arrival{" "}
                {trip.arrival_at ?? "Unknown"}
              </p>
            </article>
          ))}
          {query.result.limitations.map((text) => (
            <p className="muted" key={text}>
              {text}
            </p>
          ))}
        </>
      )}
      <a href={config.documentation} target="_blank" rel="noreferrer">
        TfNSW Official API and application portal
      </a>
    </section>
  );
}
