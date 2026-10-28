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
import { commuteModes } from "../real-data/UsydCommute";
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
    const brief = { ...seed, ...briefFrom(fields) };
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
      message.success("找房条件已保存。");
    });
  };
  const required = [{ required: true, message: "请填写或选择这一项" }];
  return (
    <Drawer
      rootClassName="rental-needs-drawer"
      title="我的租房需求"
      open={open}
      onClose={onClose}
      size={500}
      destroyOnHidden={false}
    >
      <div className="assistant-needs-intro">
        <Tag color={synced ? "blue" : "orange"}>
          {synced ? `已保存 v${confirmed?.version}` : "当前找房条件"}
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
                  重试原操作
                </Button>
              )}
              <Button
                size="small"
                onClick={() => void reload()}
                disabled={busy}
              >
                重新读取
              </Button>
            </Space>
          }
        />
      )}
      {stale && (
        <Alert
          type="warning"
          showIcon
          title="对话或需求已更新，请重新读取后确认。"
          action={<Button onClick={() => void reload()}>读取最新需求</Button>}
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
        <Form.Item name="suburb" label="偏好区域" rules={required}>
          <Select
            virtual={false}
            showSearch
            optionFilterProp="label"
            placeholder="选择区域或不限"
            options={[
              { value: "__all__", label: "不限区域" },
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
            label="最高预算（AUD）"
            rules={required}
          >
            <InputNumber min={1} max={1000000000000} />
          </Form.Item>
          <Form.Item
            name="budget_period"
            label="预算周期"
            rules={[
              ...required,
              {
                validator: (_, value) =>
                  value === "week"
                    ? Promise.resolve()
                    : Promise.reject(new Error("请填写按周计算的预算")),
              },
            ]}
          >
            <Select
              virtual={false}
              placeholder="确认预算周期"
              options={[
                { value: "week", label: "每周" },
                {
                  value: "month",
                  label: "每月（请换算为周预算）",
                  disabled: true,
                },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="budget_scope"
            label="计价对象"
            rules={[
              ...required,
              {
                validator: (_, value) =>
                  value !== "unknown"
                    ? Promise.resolve()
                    : Promise.reject(new Error("请选择计价对象")),
              },
            ]}
          >
            <Select
              virtual={false}
              placeholder="整套还是每人"
              options={[
                { value: "whole_property", label: "整套" },
                { value: "per_room", label: "每个房间" },
                { value: "per_person", label: "每人" },
              ]}
            />
          </Form.Item>
          <Form.Item name="rental_mode" label="租赁方式" rules={required}>
            <Select
              virtual={false}
              placeholder="选择租住方式"
              options={[
                { value: "whole_property", label: "整租" },
                { value: "private_room", label: "独立单间" },
                { value: "shared_room", label: "共享房间" },
                { value: "student_accommodation", label: "学生公寓" },
              ]}
            />
          </Form.Item>
          <Form.Item name="occupants" label="居住人数" rules={required}>
            <InputNumber min={1} max={100} precision={0} />
          </Form.Item>
        </div>
        <div className="assistant-needs-counts">
          {(
            [
              ["min_bedrooms", "至少卧室"],
              ["min_bathrooms", "至少浴室"],
              ["min_car_spaces", "至少车位"],
            ] as const
          ).map(([name, label]) => (
            <Form.Item key={name} name={name} label={label} rules={required}>
              <InputNumber min={0} max={100} precision={0} />
            </Form.Item>
          ))}
        </div>
        <h3>到悉大主校区</h3>
        <p className="muted small">Camperdown / Darlington · Fisher Library</p>
        <div className="form-grid">
          <Form.Item name="commute_mode" label="通勤方式">
            <Select
              allowClear
              placeholder="可选，也可以在对话里说"
              options={commuteModes}
            />
          </Form.Item>
          <Form.Item name="commute_max_minutes" label="单程最多（分钟）">
            <InputNumber min={1} max={240} precision={0} />
          </Form.Item>
        </div>
        <div className="form-grid">
          <Form.Item name="max_transfers" label="最多换乘（可选）">
            <InputNumber min={0} max={5} precision={0} />
          </Form.Item>
        </div>
        <Form.Item name="lifestyle_priorities" label="生活偏好（用于区域参考）">
          <Select
            mode="multiple"
            allowClear
            placeholder="可选，也可以直接在聊天里说"
            options={Object.entries(lifestyleTopics).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </Form.Item>
        <Button
          aria-label="保存找房条件"
          type="primary"
          htmlType="submit"
          block
          loading={busy}
          disabled={stale || canRetry || (synced && !dirty)}
        >
          保存找房条件
        </Button>
      </Form>
    </Drawer>
  );
}
