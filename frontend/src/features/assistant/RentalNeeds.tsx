import { useEffect, useState, useRef } from "react";
import {
  Alert,
  App,
  Button,
  Drawer,
  Form,
  InputNumber,
  Select,
  Space,
  Tag,
} from "antd";
import { useCase, currentConfirmation } from "../../app/context";
import { createConversation, saveAssistantNeeds } from "../../api/assistant";
import type { Conversation, RentalBrief } from "../../api/assistant";
import { newRequestId } from "../../api/client";
import {
  conversationNeeds,
  needsMatch,
  pendingNeeds,
  approximateNeeds,
} from "./needs";
import { commuteChoices } from "../real-data/UsydCommute";
import { lifestyleTopics } from "../../api/areas";

type Fields = Omit<RentalBrief, "suburb"> & { suburb?: string };
const fieldsFrom = (brief: RentalBrief): Fields => ({
  ...brief,
  suburb: brief.suburb === null ? "__all__" : brief.suburb,
});
const briefFrom = (values: Fields): RentalBrief =>
  approximateNeeds({
    ...values,
    suburb: values.suburb === "__all__" ? null : values.suburb,
  });

export default function RentalNeeds({
  open,
  onClose,
  conversation,
  onConversation,
  busy,
  execute,
  error,
  canRetry,
  onRetry,
  onReload,
  isCurrent,
}: {
  open: boolean;
  onClose: () => void;
  conversation: Conversation | null;
  onConversation: (value: Conversation) => void;
  busy: boolean;
  execute: (operation: () => Promise<void>) => Promise<void>;
  error: string | null;
  canRetry: boolean;
  onRetry: () => void;
  onReload: () => Promise<void>;
  isCurrent: (id: string) => boolean;
}) {
  const { current, config, refresh } = useCase();
  const { message } = App.useApp();
  const [form] = Form.useForm<Fields>();
  const [dirty, setDirty] = useState(false);
  const [baseline, setBaseline] = useState({
    id: conversation?.conversation_id ?? null,
    revision: conversation?.revision ?? 0,
    fingerprint: current.draft.fingerprint,
  });
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const confirmed = currentConfirmation(current);
  const confirmedProfile = confirmed
    ? (current.requirements_profile ?? confirmed.profile)
    : undefined;
  const seed = conversationNeeds(conversation, confirmedProfile);
  const values = Form.useWatch([], form);
  const synced =
    !pendingNeeds(conversation) &&
    needsMatch(values ? briefFrom(values) : seed, confirmedProfile);
  const stale =
    dirty &&
    (baseline.id !== (conversation?.conversation_id ?? null) ||
      baseline.revision !== (conversation?.revision ?? 0) ||
      baseline.fingerprint !== current.draft.fingerprint);
  useEffect(() => {
    if (!open || dirty) return;
    form.resetFields();
    form.setFieldsValue(
      fieldsFrom(conversationNeeds(conversation, confirmedProfile)),
    );
    setBaseline({
      id: conversation?.conversation_id ?? null,
      revision: conversation?.revision ?? 0,
      fingerprint: current.draft.fingerprint,
    });
  }, [
    open,
    conversation?.conversation_id,
    conversation?.revision,
    current.draft.fingerprint,
    dirty,
    form,
  ]);
  const reload = async () => {
    setDirty(false);
    await onReload();
  };
  const submit = (fields: Fields) => {
    const commute_preference =
      fields.commute_mode ||
      fields.commute_max_minutes ||
      fields.max_transfers != null
        ? "include"
        : seed.commute_mode ||
            seed.commute_max_minutes ||
            seed.commute_preference === "skip"
          ? "skip"
          : seed.commute_preference;
    const brief = approximateNeeds({
      ...seed,
      ...briefFrom({ ...fields, commute_preference }),
      commute_preference,
    });
    const requestId = newRequestId();
    let target = conversation;
    void execute(async () => {
      if (!target) {
        target = await createConversation(current.case_id);
        if (!alive.current) return;
        onConversation(target);
      }
      const result = await saveAssistantNeeds(
        current.case_id,
        target.conversation_id,
        {
          request_id: requestId,
          expected_revision: baseline.revision,
          expected_profile_fingerprint: baseline.fingerprint,
          brief,
          confirmed: true,
        },
      );
      if (!alive.current || !isCurrent(result.conversation.conversation_id))
        return;
      onConversation(result.conversation);
      await refresh();
      setDirty(false);
      onClose();
      message.success("Rental needs saved.");
    });
  };
  const required = [
    { required: true, message: "Please complete or select this field" },
  ];
  return (
    <Drawer
      rootClassName="rental-needs-drawer"
      title="My rental needs"
      open={open}
      onClose={onClose}
      size={500}
      destroyOnHidden={false}
    >
      <div className="assistant-needs-intro">
        <Tag color={synced ? "blue" : "orange"}>
          {synced ? `Saved v${confirmed?.version}` : "Current rental needs"}
        </Tag>
      </div>
      {error && (
        <Alert
          type="error"
          showIcon
          title={error}
          action={
            <Space>
              {canRetry && (
                <Button size="small" onClick={onRetry} disabled={busy}>
                  Retry original action
                </Button>
              )}
              <Button
                size="small"
                onClick={() => void reload()}
                disabled={busy}
              >
                Reload
              </Button>
            </Space>
          }
        />
      )}
      {stale && (
        <Alert
          type="warning"
          showIcon
          title="The conversation or requirements have changed. Reload before confirming."
          action={
            <Button onClick={() => void reload()}>Load latest needs</Button>
          }
        />
      )}
      <Form
        form={form}
        name="chat-rental-needs"
        requiredMark={false}
        layout="vertical"
        onValuesChange={() => setDirty(true)}
        onFinish={submit}
        disabled={busy || canRetry}
      >
        <Form.Item name="suburb" label="Preferred area" rules={required}>
          <Select
            virtual={false}
            showSearch
            optionFilterProp="label"
            placeholder="Choose an area or any area"
            options={[
              { value: "__all__", label: "Any area" },
              ...(config.catalog?.suburbs ?? []).map((value) => ({
                value,
                label: value,
              })),
            ]}
          />
        </Form.Item>
        <div className="assistant-needs-grid">
          <Form.Item
            name="budget_amount"
            label="Maximum budget (AUD)"
            rules={required}
          >
            <InputNumber min={1} max={1000000000000} />
          </Form.Item>
          <Form.Item
            name="budget_period"
            label="Budget period"
            rules={[
              ...required,
              {
                validator: (_, value) =>
                  value === "week"
                    ? Promise.resolve()
                    : Promise.reject(new Error("Please enter a weekly budget")),
              },
            ]}
          >
            <Select
              virtual={false}
              placeholder="Confirm budget period"
              options={[
                { value: "week", label: "Weekly" },
                {
                  value: "month",
                  label: "Monthly (convert to a weekly budget)",
                  disabled: true,
                },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="budget_scope"
            label="Pricing basis"
            rules={[
              ...required,
              {
                validator: (_, value) =>
                  value !== "unknown"
                    ? Promise.resolve()
                    : Promise.reject(
                        new Error("Please select a pricing basis"),
                      ),
              },
            ]}
          >
            <Select
              virtual={false}
              placeholder="Whole property or per person"
              options={[
                { value: "whole_property", label: "Whole property" },
                { value: "per_room", label: "Per room" },
                { value: "per_person", label: "Per person" },
              ]}
            />
          </Form.Item>
          <Form.Item name="rental_mode" label="Rental type" rules={required}>
            <Select
              virtual={false}
              placeholder="Choose a rental type"
              options={[
                { value: "whole_property", label: "Whole property" },
                { value: "private_room", label: "Private room" },
                { value: "shared_room", label: "Shared room" },
                {
                  value: "student_accommodation",
                  label: "Student accommodation",
                },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="occupants"
            label="Number of occupants"
            rules={required}
          >
            <InputNumber min={1} max={100} precision={0} />
          </Form.Item>
        </div>
        <div className="assistant-needs-counts">
          {(
            [
              ["min_bedrooms", "Min. beds", "Minimum bedrooms"],
              ["min_bathrooms", "Min. baths", "Minimum bathrooms"],
              ["min_car_spaces", "Min. parking", "Minimum car spaces"],
            ] as const
          ).map(([name, label, accessibleLabel]) => (
            <Form.Item key={name} name={name} label={label} rules={required}>
              <InputNumber
                aria-label={accessibleLabel}
                min={0}
                max={100}
                precision={0}
              />
            </Form.Item>
          ))}
        </div>
        <h3>Commute to USYD main campus (optional)</h3>
        <p className="muted small">
          Add a commute limit if it helps you choose a home. Otherwise, leave
          these fields blank.
        </p>
        <div className="assistant-needs-grid">
          <Form.Item name="commute_mode" label="Commute mode">
            <Select
              allowClear
              placeholder="Optional; you can also mention it in chat"
              options={commuteChoices(
                values?.commute_mode ?? seed.commute_mode,
              )}
            />
          </Form.Item>
          <Form.Item name="commute_max_minutes" label="Max. one-way (min)">
            <InputNumber
              aria-label="Maximum one-way commute (minutes)"
              min={1}
              max={240}
              precision={0}
            />
          </Form.Item>
        </div>
        <div className="assistant-needs-grid">
          <Form.Item name="max_transfers" label="Maximum transfers (optional)">
            <InputNumber min={0} max={5} precision={0} />
          </Form.Item>
        </div>
        <Form.Item
          name="lifestyle_priorities"
          label="Lifestyle preferences (for area suggestions)"
        >
          <Select
            mode="multiple"
            allowClear
            placeholder="Optional; you can also tell us in chat"
            options={Object.entries(lifestyleTopics).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </Form.Item>
        <Button
          aria-label="Save rental needs"
          type="primary"
          htmlType="submit"
          block
          loading={busy}
          disabled={stale || canRetry || (synced && !dirty)}
        >
          Save rental needs
        </Button>
      </Form>
    </Drawer>
  );
}
