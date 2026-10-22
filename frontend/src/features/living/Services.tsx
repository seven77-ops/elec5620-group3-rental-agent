import { useEffect, useState } from "react";
import {
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
} from "antd";
import type {
  BookingStatus,
  BookingValues,
  LivingProvider,
  LivingRecord,
  LivingWrite,
  ServiceBooking,
} from "../../api/living";
const statuses: Record<BookingStatus, string> = {
  considering: "考虑中",
  contacted: "已自行联系",
  booked: "已自行预约",
  completed: "已完成",
};
export default function Services({
  record,
  providers,
  busy,
  save,
  focusedId,
  focusVersion,
}: {
  record: LivingRecord;
  providers: LivingProvider[];
  busy: boolean;
  save: LivingWrite;
  focusedId?: string | null;
  focusVersion?: number;
}) {
  useEffect(() => {
    if (!focusedId) return;
    const card = document.getElementById(`living-booking-${focusedId}`);
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusedId, focusVersion]);
  const [selected, setSelected] = useState<LivingProvider | null>(null),
    [editing, setEditing] = useState<ServiceBooking | null>(null),
    [confirmed, setConfirmed] = useState(false),
    [version, setVersion] = useState(record.version);
  const [form] = Form.useForm<BookingValues>();
  const start = (
    provider: LivingProvider,
    booking: ServiceBooking | null = null,
  ) => {
    form.resetFields();
    form.setFieldsValue(
      booking || {
        service_date: null,
        quote_amount: null,
        status: "considering",
        notes: "",
      },
    );
    setSelected(provider);
    setEditing(booking);
    setConfirmed(false);
    setVersion(record.version);
  };
  const submit = async () => {
    if (!selected || !confirmed) return;
    try {
      const values = await form.validateFields();
      await save(
        "/bookings",
        {
          provider_id: selected.id,
          ...(editing ? { booking_id: editing.booking_id } : {}),
          service_date: values.service_date || null,
          quote_amount: values.quote_amount ?? null,
          status: values.status,
          notes: values.notes || "",
        },
        version,
        () => setSelected(null),
      );
    } catch {
      /* Inline validation. */
    }
  };
  return (
    <section className="living-section">
      <div className="living-section-heading">
        <div>
          <h2>搬运与清洁</h2>
          <p>查看有官方来源的服务商，记录你自己收到的报价或预约。</p>
        </div>
      </div>
      <p className="living-note">
        服务范围与档期以服务商确认为准，报价由你填写。保存记录不会提交预约。
      </p>
      <div className="living-provider-grid">
        {providers
          .filter((p) =>
            p.categories.some((c) => c === "removalist" || c === "cleaner"),
          )
          .map((provider) => (
            <article
              key={provider.id}
              data-provider-id={provider.id}
              className="living-provider-card"
            >
              <span className="living-category">
                {provider.categories
                  .filter((c) => c === "removalist" || c === "cleaner")
                  .map((c) => (c === "removalist" ? "搬运" : "清洁"))
                  .join(" · ")}
              </span>
              <h3>{provider.name}</h3>
              <p>{provider.coverage}</p>
              {provider.notes && <p className="muted">{provider.notes}</p>}
              <Space wrap>
                <a
                  href={provider.website}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  公司网站
                </a>
                <a
                  href={provider.contact_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  联系页面
                </a>
                {provider.phone && (
                  <a href={`tel:${provider.phone}`}>{provider.phone}</a>
                )}
              </Space>
              <small>
                <a
                  href={provider.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  来源
                </a>{" "}
                · 核对日期 {provider.checked_on}
              </small>
              <Button onClick={() => start(provider)} disabled={busy}>
                记录报价或预约
              </Button>
            </article>
          ))}
      </div>
      <h3 className="living-list-title">我的服务记录</h3>
      {!record.bookings.length && (
        <p className="muted">还没有报价或预约记录。</p>
      )}
      <div className="living-record-list">
        {[...record.bookings].reverse().map((booking) => {
          const provider = providers.find((p) => p.id === booking.provider_id);
          return (
            <article
              key={booking.booking_id}
              id={`living-booking-${booking.booking_id}`}
              data-booking-id={booking.booking_id}
              tabIndex={-1}
              className={`living-booking-card ${focusedId === booking.booking_id ? "is-targeted" : ""}`}
            >
              <div className="living-card-heading">
                <h3>{provider?.name || "服务商资料待重新读取"}</h3>
                <Tag>{statuses[booking.status]}</Tag>
              </div>
              <div className="living-booking-facts">
                <span>{booking.service_date || "日期未定"}</span>
                <strong>
                  {booking.quote_amount === null
                    ? "尚未记录报价"
                    : `AUD ${booking.quote_amount.toLocaleString()}`}
                </strong>
              </div>
              {booking.notes && (
                <p className="living-prewrap">{booking.notes}</p>
              )}
              <Button
                disabled={busy || !provider}
                onClick={() => provider && start(provider, booking)}
              >
                更新服务记录
              </Button>
            </article>
          );
        })}
      </div>
      <Modal
        forceRender
        title={
          selected
            ? `${editing ? "更新" : "记录"} · ${selected.name}`
            : "服务记录"
        }
        open={Boolean(selected)}
        onCancel={() => !busy && setSelected(null)}
        onOk={submit}
        okText="确认保存服务记录"
        cancelText="取消"
        confirmLoading={busy}
        okButtonProps={{
          disabled: !confirmed,
          "aria-label": "确认保存服务记录",
        }}
        cancelButtonProps={{ disabled: busy }}
        closable={!busy}
        mask={{ closable: !busy }}
      >
        <Form
          name="living-booking"
          form={form}
          layout="vertical"
          disabled={busy}
          onValuesChange={() => setConfirmed(false)}
        >
          <Form.Item name="quote_amount" label="收到的报价（AUD）">
            <InputNumber min={0} precision={2} />
          </Form.Item>
          <Form.Item name="service_date" label="服务日期">
            <Input type="date" aria-label="服务日期" />
          </Form.Item>
          <Form.Item
            name="status"
            label="服务状态"
            rules={[{ required: true }]}
          >
            <Select
              options={Object.entries(statuses).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item name="notes" label="服务备注">
            <Input.TextArea rows={3} maxLength={3000} />
          </Form.Item>
        </Form>
        <Checkbox
          checked={confirmed}
          disabled={busy}
          onChange={(e) => setConfirmed(e.target.checked)}
        >
          我确认仅保存记录，不会向服务商提交预约。
        </Checkbox>
        {record.version !== version && (
          <p role="alert">资料已更新，请关闭窗口后重新核对最新记录。</p>
        )}
      </Modal>
    </section>
  );
}
