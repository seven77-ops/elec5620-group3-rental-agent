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
import {
  applyAssistantProposal,
  createConversation,
  prepareAssistantNeeds,
} from "../../api/assistant";
import type { Conversation, RentalBrief } from "../../api/assistant";
import { newRequestId } from "../../api/client";
import { conversationNeeds, needsMatch, pendingNeeds } from "./needs";
import { lifestyleTopics } from "../../api/areas";

type Fields = Omit<RentalBrief, "suburb"> & { suburb?: string };
const fieldsFrom = (brief: RentalBrief): Fields => ({
  ...brief,
  suburb: brief.suburb === null ? "__all__" : brief.suburb,
});
const briefFrom = (values: Fields): RentalBrief => ({
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
  const { current, config, refresh, go } = useCase();
  const { modal, message } = App.useApp();
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
  const seed = conversationNeeds(conversation, confirmed?.profile);
  const values = Form.useWatch([], form);
  const synced =
    !pendingNeeds(conversation) &&
    needsMatch(values ? briefFrom(values) : seed, confirmed?.profile);
  const stale =
    dirty &&
    (baseline.id !== (conversation?.conversation_id ?? null) ||
      baseline.revision !== (conversation?.revision ?? 0) ||
      baseline.fingerprint !== current.draft.fingerprint);
  useEffect(() => {
    if (!open || dirty) return;
    form.resetFields();
    form.setFieldsValue(
      fieldsFrom(conversationNeeds(conversation, confirmed?.profile)),
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
      const proposal = await prepareAssistantNeeds(
        current.case_id,
        target.conversation_id,
        {
          request_id: requestId,
          expected_revision: baseline.revision,
          expected_profile_fingerprint: baseline.fingerprint,
          brief,
        },
      );
      if (!alive.current) return;
      onConversation(proposal.conversation);
      setDirty(false);
      const applyId = newRequestId();
      modal.confirm({
        title: "确认同步租房需求？",
        content: (
          <>
            <p>确认后保存新的偏好版本，并按同一份条件更新房源推荐。</p>
            <ul className="assistant-proposal-summary">
              {proposal.summary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </>
        ),
        okText: "确认同步并生成推荐",
        cancelText: "继续修改",
        onOk: () =>
          execute(async () => {
            if (
              !alive.current ||
              !isCurrent(proposal.conversation.conversation_id)
            )
              return;
            const result = await applyAssistantProposal(
              current.case_id,
              proposal.proposal_id,
              applyId,
            );
            if (!alive.current) return;
            onConversation(result.conversation);
            await refresh();
            onClose();
            message.success("租房需求和房源推荐已同步。");
          }),
      });
    });
  };
  const required = [{ required: true, message: "请填写或选择这一项" }];
  return (
    <Drawer
      title="我的租房需求"
      open={open}
      onClose={onClose}
      size={500}
      destroyOnHidden={false}
    >
      <div className="assistant-needs-intro">
        <Tag color={synced ? "blue" : "orange"}>
          {synced ? `已同步 v${confirmed?.version}` : "待确认同步"}
        </Tag>
        <p>AI 整理的条件可以在这里修改。确认后，房源推荐使用同一份需求。</p>
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
        <p className="muted small">
          数量填 0 表示不限。房源的账单、在租状态和计价对象仍需核实。
        </p>
        <Form.Item
          name="lifestyle_priorities"
          label="生活偏好（用于区域参考）"
          extra="记录你看重什么；安静和安全等要求仍需核实具体房源。"
        >
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
          aria-label="确认并同步需求"
          type="primary"
          htmlType="submit"
          block
          loading={busy}
          disabled={stale || canRetry || (synced && !dirty)}
        >
          确认并同步需求
        </Button>
      </Form>
      <div className="assistant-needs-links">
        <Button
          type="link"
          onClick={() => go("recommendations")}
          disabled={busy}
        >
          查看房源推荐
        </Button>
        <Button type="link" onClick={() => go("preferences")} disabled={busy}>
          其他偏好与完整设置
        </Button>
      </div>
    </Drawer>
  );
}
