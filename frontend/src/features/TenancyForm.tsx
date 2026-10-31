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
import type { Dict } from "../api/types";
import { Failure, JsonDetails, money } from "../components/Common";
import { useAction } from "../components/useAction";
import { CommandRecovery, type CommandRecoveryProps } from "./AftercarePlan";
import { useTenancyPrefill } from "./aftercare/prefill";
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
  const prefill = useTenancyPrefill(current.case_id, current.reviews.length);
  const prefilled = prefill?.values ?? {};
  const applyPrefill = () => {
    if (!prefill) return;
    const furnished = prefilled.furnished?.value;
    form.setFieldsValue({
      ...(prefilled.address ? { address: prefilled.address.value } : {}),
      ...(prefill.source_ref ? { source_ref: prefill.source_ref } : {}),
      ...(real && typeof furnished === "boolean"
        ? { furnished: furnished ? "yes" : "no" }
        : {}),
    });
    setConfirmed(false);
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
      {!tenancy && <h2>Confirm lease details</h2>}
      <Alert
        type="info"
        showIcon
        title={
          tenancy
            ? "Check and complete current lease details"
            : real
              ? "Enter and check the actual lease details"
              : "Check each detail in this synthetic lease sample"
        }
        description={
          tenancy
            ? "Saving updates lease details in the same case and preserves existing evidence. Complete room, carpet, outdoor area, and furniture details to confirm the move-out plan."
            : real
              ? "A contract draft or review does not establish that a lease is signed. A move-out and bond case is created only after you confirm actual lease details. Unknown room and furniture details can be left blank for now."
              : "Contract review does not establish that a lease is signed. An aftercare case is created only after you confirm these details. Sample rooms, furniture, and evidence can be checked or edited."
        }
      />
      <Failure error={action.error} retry={action.retry} />
      {recovery && <CommandRecovery {...recovery} />}
      {!tenancy && prefilled.address && (
        <Alert
          className="aftercare-prefill"
          type="success"
          showIcon
          title="Import existing information (you still need to check and confirm it)"
          description={
            <>
              <ul className="plain-list">
                {(
                  [
                    ["address", "Address"],
                    ["start_date", "Lease start date"],
                    [
                      "move_out_date",
                      "Lease end date (can be used as the move-out date)",
                    ],
                    ["bond_amount", "Bond"],
                    ["furnished", "Furnished"],
                  ] as const
                ).map(([key, label]) => {
                  const item = prefilled[key];
                  if (!item) return null;
                  const shown =
                    key === "bond_amount"
                      ? money(Number(item.value))
                      : typeof item.value === "boolean"
                        ? item.value
                          ? "Yes"
                          : "No"
                        : String(item.value);
                  return (
                    <li key={key}>
                      {label}: <strong>{shown}</strong>
                      <span className="muted small">
                        {" "}
                        · {item.label}
                        {item.quote ? `“${item.quote}”` : ""}
                      </span>
                    </li>
                  );
                })}
              </ul>
              {prefill?.warnings.map((w) => (
                <p className="muted small" key={w}>
                  {w}
                </p>
              ))}
              <Button
                onClick={applyPrefill}
                disabled={busy || disabled}
                aria-label="Import existing details"
              >
                Import address and source
              </Button>
            </>
          }
        />
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
          label="Lease address"
          rules={[
            { required: true, message: "Enter the confirmed lease address" },
          ]}
        >
          <Input aria-label="Lease address" />
        </Form.Item>
        <div className="form-grid">
          <Form.Item name="jurisdiction" label="Jurisdiction">
            <Select options={[{ value: "NSW", label: "NSW" }]} />
          </Form.Item>
          <Form.Item name="tenancy_type" label="Lease type">
            <Select
              options={[
                {
                  value: "standard_residential",
                  label: "Standard residential tenancy",
                },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="source_ref"
            hidden={real}
            label="Information source reference"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_version"
            hidden={real}
            label="Source version"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} precision={0} />
          </Form.Item>
        </div>
        <div className="switch-group">
          {(
            [
              ["carpeted", "Has carpet"],
              ["outdoor", "Has outdoor area"],
              ["furnished", "Furnished"],
            ] as const
          ).map(([key, label]) =>
            real ? (
              <Form.Item key={key} name={key} label={label}>
                <Select
                  options={[
                    { value: "unknown", label: "Not entered" },
                    { value: "yes", label: "Yes" },
                    { value: "no", label: "No" },
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
            label="Furniture inventory checked"
          >
            <Switch />
          </Form.Item>
        </div>
        <h3>Rooms</h3>
        <Form.List name="rooms">
          {(fields, { add, remove }) => (
            <>
              {fields.map((f) => (
                <div className="list-form-row" key={f.key}>
                  <Form.Item
                    name={[f.name, "id"]}
                    hidden={real}
                    label="Room ID"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "name"]}
                    label="Room name"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Button
                    aria-label="Remove room"
                    icon={<MinusCircleOutlined />}
                    onClick={() => remove(f.name)}
                  />
                </div>
              ))}
              <Button
                aria-label="Add room"
                icon={<PlusOutlined aria-hidden="true" />}
                onClick={() =>
                  add({
                    id: real ? `room-${crypto.randomUUID()}` : "",
                    name: "",
                  })
                }
              >
                Add room
              </Button>
            </>
          )}
        </Form.List>
        <h3>Furniture inventory</h3>
        <Form.List name="inventory">
          {(fields, { add, remove }) => (
            <>
              {fields.map((f) => (
                <div className="list-form-row" key={f.key}>
                  <Form.Item
                    name={[f.name, "id"]}
                    hidden={real}
                    label="Furniture ID"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "name"]}
                    label="Furniture name"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "room_id"]}
                    label={real ? "Room" : "Room ID"}
                    rules={[{ required: true }]}
                  >
                    {real ? (
                      <Select
                        placeholder="Select room"
                        options={(rooms ?? []).map((room) => ({
                          value: room.id,
                          label: room.name || "Unnamed room",
                        }))}
                      />
                    ) : (
                      <Input />
                    )}
                  </Form.Item>
                  <Button
                    aria-label="Remove furniture"
                    icon={<MinusCircleOutlined />}
                    onClick={() => remove(f.name)}
                  />
                </div>
              ))}
              <Button
                aria-label="Add furniture"
                icon={<PlusOutlined aria-hidden="true" />}
                onClick={() =>
                  add({
                    id: real ? `item-${crypto.randomUUID()}` : "",
                    name: "",
                    room_id: "",
                  })
                }
              >
                Add furniture
              </Button>
            </>
          )}
        </Form.List>
        <Form.Item
          name="baseline_evidence_refs"
          hidden={real}
          label="Move-in baseline evidence references"
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
              label:
                "View evidence metadata supplied with the synthetic sample",
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
          I have checked and confirmed the lease, rooms, furniture, and sources
          above.
        </Checkbox>
        <Button
          type="primary"
          disabled={!confirmed || disabled || Boolean(recovery?.error)}
          loading={busy}
          onClick={submit}
          aria-label={
            tenancy
              ? "Confirm and save lease details"
              : "Confirm details and create aftercare case"
          }
        >
          {tenancy
            ? "Confirm and save lease details"
            : "Confirm details and create aftercare case"}
        </Button>
      </Space>
    </section>
  );
}
