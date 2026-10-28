import { useEffect, useState } from "react";
import {
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
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
import { serviceCompanyIntro } from "./serviceCompanyInfo";
const statuses: Record<BookingStatus, string> = {
  considering: "考虑中",
  contacted: "已自行联系",
  booked: "已自行预约",
  completed: "已完成",
};
const serviceGroups = [
  { category: "removalist", title: "搬运公司", label: "搬运" },
  { category: "cleaner", title: "清洁公司", label: "清洁" },
] as const;
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
  const [mode, setMode] = useState<"details" | "record">("record");
  const start = (
    provider: LivingProvider,
    booking: ServiceBooking | null = null,
    view: "details" | "record" = "record",
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
    setMode(view);
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
        </div>
      </div>
      <p className="living-note">
        服务范围与档期以服务商确认为准，报价由你填写。保存记录不会提交预约。
      </p>
      {serviceGroups.map((group) => {
        const companies = providers.filter((p) =>
          p.categories.includes(group.category),
        );
        return (
          <section
            className="living-service-group"
            aria-label={group.title}
            key={group.category}
          >
            <div className="living-service-group-heading">
              <h3>{group.title}</h3>
              <span className="muted">{companies.length} 家</span>
            </div>
            <div className="living-provider-grid">
              {companies.map((provider) => (
                <button
                  type="button"
                  className="living-provider-card living-provider-trigger"
                  key={provider.id}
                  data-provider-id={provider.id}
                  aria-label={`${provider.name}，查看服务商详情`}
                  aria-haspopup="dialog"
                  onClick={() => start(provider, null, "details")}
                >
                  <span className="living-category">{group.label}</span>
                  <strong className="living-provider-name">
                    {provider.name}
                  </strong>
                  <span className="living-provider-coverage">
                    {serviceCompanyIntro(provider)}
                  </span>
                  <span className="living-provider-card-action">
                    <span className="muted">公司介绍与官网</span>
                    <span>查看详情 →</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
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
            ? mode === "details"
              ? `${selected.name} · 服务商详情`
              : `${editing ? "更新" : "记录"} · ${selected.name}`
            : "服务记录"
        }
        open={Boolean(selected)}
        onCancel={() => !busy && setSelected(null)}
        onOk={() => {
          if (mode === "details") {
            if (selected) start(selected);
          } else void submit();
        }}
        okText={mode === "details" ? "记录报价或预约" : "确认保存服务记录"}
        cancelText={mode === "details" ? "关闭详情" : "取消"}
        confirmLoading={mode === "record" && busy}
        width={680}
        styles={{
          body: {
            maxHeight: "65vh",
            overflowY: "auto",
            overflowWrap: "anywhere",
          },
        }}
        okButtonProps={{
          disabled: busy || (mode === "record" && !confirmed),
          "aria-label":
            mode === "details" ? "记录报价或预约" : "确认保存服务记录",
        }}
        cancelButtonProps={{
          disabled: busy,
          "aria-label": mode === "details" ? "关闭详情" : "取消",
        }}
        closable={!busy}
        mask={{ closable: !busy }}
      >
        {selected && (
          <div className="living-provider-details" hidden={mode !== "details"}>
            <span className="living-category">
              {selected.categories
                .filter((c) => c === "removalist" || c === "cleaner")
                .map((c) => (c === "removalist" ? "搬运" : "清洁"))
                .join(" · ")}
            </span>
            <p>{serviceCompanyIntro(selected)}</p>
            <a
              href={selected.website}
              target="_blank"
              rel="noopener noreferrer"
            >
              公司网站
            </a>
          </div>
        )}
        <div hidden={mode !== "record"}>
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
        </div>
      </Modal>
    </section>
  );
}
