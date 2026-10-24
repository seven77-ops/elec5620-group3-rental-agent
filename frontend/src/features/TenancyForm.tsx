import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
} from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { useCase } from "../app/context";
import { api } from "../api/client";
import type { Dict, Review } from "../api/types";
import { Failure, JsonDetails } from "../components/Common";
import { useAction } from "../components/useAction";
import { CommandRecovery, type CommandRecoveryProps } from "./AftercarePlan";
export default function TenancyForm({
  create,
  busy,
  tenancy,
  disabled = false,
  recovery,
}: {
  create: (payload: Dict) => void | Promise<boolean>;
  busy: boolean;
  tenancy?: Dict;
  disabled?: boolean;
  recovery?: CommandRecoveryProps;
}) {
  const { current, config } = useCase();
  const [form] = Form.useForm();
  const [confirmed, setConfirmed] = useState(false);
  const action = useAction();
  const real = config.mode === "real_listings";
  const [realTemplate] = useState(() => ({
    tenancy_id: `tenancy-${crypto.randomUUID()}`,
    tenant_id: `tenant-${crypto.randomUUID()}`,
    address: "",
    jurisdiction: "NSW",
    tenancy_type: "standard_residential",
    confirmed: false,
    source_ref: "user-entered:tenant-confirmation",
    source_version: 1,
    rooms: [],
    carpeted: "unknown",
    outdoor: "unknown",
    furnished: "unknown",
    inventory: [],
    inventory_confirmed: false,
    baseline_evidence_refs: [],
  }));
  const template = tenancy ?? (real ? realTemplate : config.tenancy_template);
  const initialValues: Dict = {
    ...template,
    rooms: template.rooms ?? [],
    inventory: template.inventory ?? [],
  };
  if (real && tenancy)
    for (const key of ["carpeted", "outdoor", "furnished"])
      initialValues[key] =
        tenancy[key] == null ? "unknown" : tenancy[key] ? "yes" : "no";
  useEffect(() => {
    setConfirmed(false);
  }, [tenancy?.source_version]);
  const rooms = Form.useWatch("rooms", form) as
    { id: string; name: string }[] | undefined;
  const capabilities = config.capabilities as Dict;
  const prefill = () => {
    const id = current.reviews.at(-1)?.review_id;
    if (!id) return;
    void action.run(async () => {
      const r = await api<Review>(`/contract-reviews/${id}`);
      form.setFieldsValue({
        address: r.fields.address?.value,
        source_ref: `review:${r.review_id}@${r.version}#fields.address`,
        source_version: r.version,
      });
      setConfirmed(false);
    });
  };
  const submit = async () => {
    try {
      const values = await form.validateFields();
      if (real)
        for (const key of ["carpeted", "outdoor", "furnished"])
          values[key] =
            values[key] === "unknown" || values[key] == null
              ? null
              : values[key] === "yes";
      await create({
        tenancy: {
          ...template,
          ...values,
          ...(real
            ? {
                rooms: values.rooms?.length ? values.rooms : null,
                inventory: values.inventory?.length ? values.inventory : null,
              }
            : {}),
          confirmed: true,
          ...(tenancy
            ? { source_version: Number(tenancy.source_version) + 1 }
            : {}),
        },
        ...(!tenancy
          ? {
              evidence: real
                ? []
                : (capabilities.aftercare_evidence_template ?? []),
            }
          : {}),
      });
    } catch {
      /* Inline errors. */
    }
  };
  return (
    <section className="panel tenancy-form">
      {!tenancy && <h2>确认租约资料</h2>}
      <Alert
        type="info"
        showIcon
        title={
          tenancy
            ? "核对并补齐当前租约资料"
            : real
              ? "请填写并核对实际租约资料"
              : "以下为合成租约样例，请逐项核对"
        }
        description={
          tenancy
            ? "保存后更新同一案件的租约资料，已有证据保留。房间、地毯、室外区域与家具情况补齐后，可继续确认退租计划。"
            : real
              ? "合同草稿或复核结果不代表租约已签订。只有你明确确认实际租约资料后，才创建退租与押金案件。未知的房间与家具可暂不填写。"
              : "合同复核不代表租约已签订。只有你明确确认这些资料后，才创建租后服务案件。示例房间、家具和证据均可核对或编辑。"
        }
      />
      <Failure error={action.error} retry={action.retry} />
      {recovery && <CommandRecovery {...recovery} />}
      {!tenancy && current.reviews.length > 0 && (
        <Button
          onClick={prefill}
          loading={action.busy}
          aria-label="从最近合同复核预填地址与来源"
        >
          从最近合同复核预填地址与来源
        </Button>
      )}
      <Form
        form={form}
        initialValues={initialValues}
        disabled={busy || disabled}
        layout="vertical"
        onValuesChange={() => setConfirmed(false)}
      >
        <Form.Item
          name="address"
          label="租约地址"
          rules={[{ required: true, message: "填写确认的租约地址" }]}
        >
          <Input aria-label="租约地址" />
        </Form.Item>
        <div className="form-grid">
          <Form.Item name="jurisdiction" label="管辖地区">
            <Select options={[{ value: "NSW", label: "NSW" }]} />
          </Form.Item>
          <Form.Item name="tenancy_type" label="租约类型">
            <Select
              options={[
                { value: "standard_residential", label: "标准住宅租约" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="source_ref"
            hidden={real}
            label="资料来源引用"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_version"
            hidden={real}
            label="来源版本"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} precision={0} />
          </Form.Item>
        </div>
        <div className="switch-group">
          {(
            [
              ["carpeted", "有地毯"],
              ["outdoor", "有室外区域"],
              ["furnished", "带家具"],
            ] as const
          ).map(([key, label]) =>
            real ? (
              <Form.Item key={key} name={key} label={label}>
                <Select
                  options={[
                    { value: "unknown", label: "尚未填写" },
                    { value: "yes", label: "是" },
                    { value: "no", label: "否" },
                  ]}
                />
              </Form.Item>
            ) : (
              <Form.Item
                key={key}
                name={key}
                valuePropName="checked"
                label={label}
              >
                <Switch />
              </Form.Item>
            ),
          )}
          <Form.Item
            name="inventory_confirmed"
            valuePropName="checked"
            label="家具清单已核对"
          >
            <Switch />
          </Form.Item>
        </div>
        <h3>房间</h3>
        <Form.List name="rooms">
          {(fields, { add, remove }) => (
            <>
              {fields.map((f) => (
                <div className="list-form-row" key={f.key}>
                  <Form.Item
                    name={[f.name, "id"]}
                    hidden={real}
                    label="房间标识"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "name"]}
                    label="房间名称"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Button
                    aria-label="移除此房间"
                    icon={<MinusCircleOutlined />}
                    onClick={() => remove(f.name)}
                  />
                </div>
              ))}
              <Button
                aria-label="添加房间"
                icon={<PlusOutlined aria-hidden="true" />}
                onClick={() =>
                  add({
                    id: real ? `room-${crypto.randomUUID()}` : "",
                    name: "",
                  })
                }
              >
                添加房间
              </Button>
            </>
          )}
        </Form.List>
        <h3>家具清单</h3>
        <Form.List name="inventory">
          {(fields, { add, remove }) => (
            <>
              {fields.map((f) => (
                <div className="list-form-row" key={f.key}>
                  <Form.Item
                    name={[f.name, "id"]}
                    hidden={real}
                    label="家具标识"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "name"]}
                    label="家具名称"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "room_id"]}
                    label={real ? "所属房间" : "所属房间标识"}
                    rules={[{ required: true }]}
                  >
                    {real ? (
                      <Select
                        placeholder="选择房间"
                        options={(rooms ?? []).map((room) => ({
                          value: room.id,
                          label: room.name || "尚未命名房间",
                        }))}
                      />
                    ) : (
                      <Input />
                    )}
                  </Form.Item>
                  <Button
                    aria-label="移除此家具"
                    icon={<MinusCircleOutlined />}
                    onClick={() => remove(f.name)}
                  />
                </div>
              ))}
              <Button
                aria-label="添加家具"
                icon={<PlusOutlined aria-hidden="true" />}
                onClick={() =>
                  add({
                    id: real ? `item-${crypto.randomUUID()}` : "",
                    name: "",
                    room_id: "",
                  })
                }
              >
                添加家具
              </Button>
            </>
          )}
        </Form.List>
        <Form.Item
          name="baseline_evidence_refs"
          hidden={real}
          label="入住基线证据引用"
        >
          <Select
            mode="multiple"
            options={(
              (capabilities.aftercare_evidence_template ?? []) as Dict[]
            ).map((e) => ({
              value: String(e.evidence_id),
              label: String(e.evidence_id),
            }))}
          />
        </Form.Item>
      </Form>
      {!real && (
        <Collapse
          ghost
          items={[
            {
              key: "evidence",
              label: "查看随合成样例提供的证据元数据",
              children: (
                <JsonDetails value={capabilities.aftercare_evidence_template} />
              ),
            },
          ]}
        />
      )}
      <Space orientation="vertical">
        <Checkbox
          checked={confirmed}
          disabled={busy || disabled}
          onChange={(e) => setConfirmed(e.target.checked)}
        >
          我已核对并确认上述租约、房间、家具及资料来源。
        </Checkbox>
        <Button
          type="primary"
          disabled={!confirmed || disabled || Boolean(recovery?.error)}
          loading={busy}
          onClick={submit}
          aria-label={tenancy ? "确认并保存租约资料" : "确认资料并创建租后案件"}
        >
          {tenancy ? "确认并保存租约资料" : "确认资料并创建租后案件"}
        </Button>
      </Space>
    </section>
  );
}
