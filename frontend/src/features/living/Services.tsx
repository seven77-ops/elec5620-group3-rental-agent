import EnglishDateInput from "../../components/EnglishDateInput";
import { useEffect, useRef, useState } from "react";
import {
  Button,
  App,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Tag,
  Space,
} from "antd";
import type {
  BookingStatus,
  BookingValues,
  LivingProvider,
  LivingRecord,
  LivingWrite,
  ServiceBooking,
} from "../../api/living";
import { newRequestId } from "../../api/client";
import { serviceCompanyIntro } from "./serviceCompanyInfo";
const statuses: Record<BookingStatus, string> = {
  considering: "Considering",
  contacted: "Contacted independently",
  booked: "Booked independently",
  completed: "Completed",
};
const serviceGroups = [
  { category: "removalist", title: "Removalists", label: "Moving" },
  { category: "cleaner", title: "Cleaning companies", label: "Cleaning" },
] as const;
export default function Services({
  record,
  providers,
  busy,
  save,
  focusedId,
  focusVersion,
  onViewHome,
}: {
  record: LivingRecord;
  providers: LivingProvider[];
  busy: boolean;
  save: LivingWrite;
  focusedId?: string | null;
  focusVersion?: number;
  onViewHome: () => void;
}) {
  const { modal, message } = App.useApp();
  const choiceDialog = useRef<ReturnType<typeof modal.confirm> | null>(null);
  useEffect(
    () => () => {
      choiceDialog.current?.destroy();
      choiceDialog.current = null;
    },
    [record.case_id],
  );
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
        () => {
          setSelected(null);
          void message.success("Service record saved to My home.");
        },
      );
    } catch {
      /* Inline validation. */
    }
  };
  const chooseService = () => {
    if (!selected || busy) return;
    const provider = selected;
    const expectedVersion = record.version;
    const requestId = newRequestId();
    choiceDialog.current?.destroy();
    choiceDialog.current = modal.confirm({
      title: "Save this service to My home?",
      content: (
        <>
          <p>{provider.name}</p>
          <p>
            This saves your choice only. Contact the company to arrange a
            service.
          </p>
        </>
      ),
      okText: "Confirm and save",
      cancelText: "Cancel",
      onOk: async () => {
        const saved = await save(
          "/bookings",
          {
            provider_id: provider.id,
            service_date: null,
            quote_amount: null,
            status: "considering",
            notes: "",
          },
          expectedVersion,
          () => {
            setSelected(null);
            void message.success("Service saved to My home.");
          },
          requestId,
        );
        if (!saved) {
          void message.error(
            "Unable to save the service. Retry, or cancel and load the latest information.",
          );
          throw new Error(
            "The service was not saved. Close details to reload or retry.",
          );
        }
      },
    });
  };
  return (
    <section className="living-section">
      <div className="living-section-heading">
        <div>
          <h2>Moving and cleaning</h2>
        </div>
        <Button onClick={onViewHome} disabled={busy}>
          View in My home
        </Button>
      </div>
      <p className="living-note">
        Confirm coverage and availability with the provider. Enter quotes you
        receive. Saving a record does not make a booking.
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
              <span className="muted">{companies.length} providers</span>
            </div>
            <div className="living-provider-grid">
              {companies.map((provider) => (
                <button
                  type="button"
                  className="living-provider-card living-provider-trigger"
                  key={provider.id}
                  data-provider-id={provider.id}
                  aria-label={`${provider.name}, view provider details`}
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
                    <span className="muted">
                      Company information and website
                    </span>
                    <span>View details →</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
      <h3 className="living-list-title">My service records</h3>
      {!record.bookings.length && (
        <p className="muted">No quote or booking records yet.</p>
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
                <h3>{provider?.name || "Reload provider information"}</h3>
                <Tag>{statuses[booking.status]}</Tag>
              </div>
              <div className="living-booking-facts">
                <span>{booking.service_date || "Date not set"}</span>
                <strong>
                  {booking.quote_amount === null
                    ? "No quote recorded"
                    : `AUD ${booking.quote_amount.toLocaleString("en-AU")}`}
                </strong>
              </div>
              {booking.notes && (
                <p className="living-prewrap">{booking.notes}</p>
              )}
              <Button
                disabled={busy || !provider}
                onClick={() => provider && start(provider, booking)}
              >
                Update service record
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
              ? `${selected.name} · Provider details`
              : `${editing ? "Update" : "Record"} · ${selected.name}`
            : "Service record"
        }
        open={Boolean(selected)}
        onCancel={() => !busy && setSelected(null)}
        onOk={() => {
          if (mode === "details") {
            if (selected) start(selected);
          } else void submit();
        }}
        okText={
          mode === "details"
            ? "Record quote or booking"
            : "Confirm service record"
        }
        cancelText={mode === "details" ? "Close details" : "Cancel"}
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
            mode === "details"
              ? "Record quote or booking"
              : "Confirm service record",
        }}
        cancelButtonProps={{
          disabled: busy,
          "aria-label": mode === "details" ? "Close details" : "Cancel",
        }}
        closable={!busy}
        mask={{ closable: !busy }}
        footer={
          mode === "details" ? (
            <Space wrap>
              <Button disabled={busy} onClick={() => setSelected(null)}>
                Close details
              </Button>
              <Button
                disabled={busy}
                onClick={() => selected && start(selected)}
              >
                Record quote or booking
              </Button>
              {selected &&
              record.bookings.some((b) => b.provider_id === selected.id) ? (
                <Button
                  type="primary"
                  disabled={busy}
                  onClick={() => {
                    setSelected(null);
                    onViewHome();
                  }}
                >
                  View in My home
                </Button>
              ) : (
                <Button type="primary" disabled={busy} onClick={chooseService}>
                  Save to My home
                </Button>
              )}
            </Space>
          ) : undefined
        }
      >
        {selected && (
          <div className="living-provider-details" hidden={mode !== "details"}>
            <span className="living-category">
              {selected.categories
                .filter((c) => c === "removalist" || c === "cleaner")
                .map((c) => (c === "removalist" ? "Moving" : "Cleaning"))
                .join(" · ")}
            </span>
            <p>{serviceCompanyIntro(selected)}</p>
            <a
              href={selected.website}
              target="_blank"
              rel="noopener noreferrer"
            >
              Company website
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
            <Form.Item name="quote_amount" label="Quote received (AUD)">
              <InputNumber min={0} precision={2} />
            </Form.Item>
            <Form.Item name="service_date" label="Service date">
              <EnglishDateInput aria-label="Service date" />
            </Form.Item>
            <Form.Item
              name="status"
              label="Service status"
              rules={[{ required: true }]}
            >
              <Select
                options={Object.entries(statuses).map(([value, label]) => ({
                  value,
                  label,
                }))}
              />
            </Form.Item>
            <Form.Item name="notes" label="Service notes">
              <Input.TextArea rows={3} maxLength={3000} />
            </Form.Item>
          </Form>
          <Checkbox
            checked={confirmed}
            disabled={busy}
            onChange={(e) => setConfirmed(e.target.checked)}
          >
            I confirm this only saves a record and does not submit a booking to
            the provider.
          </Checkbox>
          {record.version !== version && (
            <p role="alert">
              Information has changed. Close this window and check the latest
              record again.
            </p>
          )}
        </div>
      </Modal>
    </section>
  );
}
