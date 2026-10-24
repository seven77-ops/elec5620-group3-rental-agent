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
      <h2>从 Domain 查询整租房源</h2>
      {!config.configured && (
        <Alert
          type="info"
          showIcon
          title={
            config.key_present ? "Domain 用途授权待配置" : "Domain 凭据未配置"
          }
          description="在后端 .env 配置 DOMAIN_API_KEY，并在供应商确认本应用用途后设置 DOMAIN_USE_APPROVED=1，再重启服务。"
        />
      )}
      <p>
        查询悉大周边四个邮区的前 20
        条租赁房源。房源信息还需要核对，不会自动成为正式推荐。
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
            label="Domain 搜索邮区"
            name="postcode"
            rules={[{ required: true }]}
          >
            <Select options={postcodeOptions} />
          </Form.Item>
          <Form.Item
            label="整套最高周租（AUD）"
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
          我同意将本次区域和价格条件发送给 Domain。
        </Checkbox>
        <div>
          <Button
            type="primary"
            htmlType="submit"
            disabled={!config.configured || !consent}
            loading={query.busy}
          >
            查询 Domain 房源
          </Button>
        </div>
      </Form>
      <Failure error={query.error} />
      {query.result && (
        <>
          <p className="muted">查询时间：{query.result.queried_at}</p>
          {!query.result.items.length && (
            <p>本次未返回房源。可调整条件后再查询。</p>
          )}
          {query.result.items.map((item) => (
            <article className="real-record" key={item.listing_id}>
              <h3>{item.address ?? `房源 ${item.listing_id}`}</h3>
              <p>
                {item.advertised_price ?? "价格未提供"} · 卧室数：
                {item.bedrooms ?? "未知"} · 尚未评估
              </p>
              {item.source_url && (
                <a href={item.source_url} target="_blank" rel="noreferrer">
                  查看原始房源
                </a>
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
                  用此坐标查通勤
                </Button>
              )}
            </article>
          ))}
        </>
      )}
      <a href={config.documentation} target="_blank" rel="noreferrer">
        Domain 官方接口与访问说明
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
      <h2>查询到校公共交通</h2>
      {!config.configured && (
        <Alert
          type="info"
          showIcon
          title="TfNSW 凭据未配置"
          description="在后端 .env 填写 TFNSW_API_KEY 并重启后，即可发出真实路线查询。当前没有模拟的查询成功结果。"
        />
      )}
      <p>
        起点填写房源坐标；终点填写实际教学楼或入口坐标。请选择未来 30
        天内的到达时间，供应商实际时刻表范围可能更短。
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
            label="房源纬度"
            name={["origin", "latitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-90} max={90} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="房源经度"
            name={["origin", "longitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-180} max={180} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="教学楼入口纬度"
            name={["destination", "latitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-90} max={90} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="教学楼入口经度"
            name={["destination", "longitude"]}
            rules={[{ required: true }]}
          >
            <InputNumber min={-180} max={180} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            label="到达时间（浏览器本地时区）"
            name="arrival_at"
            rules={[{ required: true }]}
            extra="服务端按 Australia/Sydney 转换日期和时间。"
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
          我同意将起终点坐标和到达时间发送给 TfNSW。
        </Checkbox>
        <div>
          <Button
            type="primary"
            htmlType="submit"
            disabled={!config.configured || !consent}
            loading={query.busy}
          >
            查询实际通勤
          </Button>
        </div>
      </Form>
      <Failure error={query.error} />
      {query.result && (
        <>
          <p>
            查询时间：{query.result.queried_at} · 请求到达时间：
            {query.result.query.arrival_at}
          </p>
          <a
            href={mapUrl(query.result.query.destination)}
            target="_blank"
            rel="noreferrer"
          >
            在地图查看终点位置
          </a>
          {!query.result.journeys.length && (
            <Alert
              type="info"
              title="本次没有可用路线"
              description="核对坐标、到达日期和时间后再查询。"
            />
          )}
          {query.result.journeys.map((trip, i) => (
            <article className="real-record" key={i}>
              <h3>
                路线 {i + 1} ·{" "}
                {trip.duration_minutes == null
                  ? "总时长待核对"
                  : `${trip.duration_minutes} 分钟（含候车）`}
              </h3>
              <p>
                步行{" "}
                {trip.walking_minutes == null
                  ? "时长未知"
                  : `${trip.walking_minutes} 分钟`}{" "}
                · 换乘 {trip.transfers ?? "未知"} 次
              </p>
              <p>{trip.services.join(" → ")}</p>
              <p>
                计划出发 {trip.departure_at ?? "未知"} · 到达{" "}
                {trip.arrival_at ?? "未知"}
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
        TfNSW 官方接口与申请入口
      </a>
    </section>
  );
}
