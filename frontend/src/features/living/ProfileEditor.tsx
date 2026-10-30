import { useState } from "react";
import {
  Button,
  Checkbox,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
} from "antd";
import type {
  LivingProfile,
  LivingRecord,
  LivingWrite,
} from "../../api/living";
const yesNo = [
  { value: "unknown", label: "Not entered" },
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];
export default function ProfileEditor({
  record,
  busy,
  save,
}: {
  record: LivingRecord;
  busy: boolean;
  save: LivingWrite;
}) {
  const [open, setOpen] = useState(false),
    [confirmed, setConfirmed] = useState(false);
  const [snapshot, setSnapshot] = useState(record);
  const [form] = Form.useForm();
  const profile = record.profile;
  const start = () => {
    setSnapshot(record);
    setConfirmed(false);
    form.setFieldsValue({
      ...profile,
      lease_start_date: profile.lease_start_date ?? null,
      lease_end_date: profile.lease_end_date ?? null,
      ...Object.fromEntries(
        ["carpeted", "has_pets", "has_elevator"].map((key) => [
          key,
          profile[key as keyof LivingProfile] === null
            ? "unknown"
            : profile[key as keyof LivingProfile]
              ? "yes"
              : "no",
        ]),
      ),
    });
    setOpen(true);
  };
  const submit = async () => {
    if (!confirmed) return;
    try {
      const input = await form.validateFields();
      const values = {
        ...snapshot.profile,
        ...input,
        move_out_date: input.move_out_date || null,
        lease_start_date: input.lease_start_date || null,
        lease_end_date: input.lease_end_date || null,
      };
      for (const key of ["carpeted", "has_pets", "has_elevator"])
        values[key] = input[key] === "unknown" ? null : input[key] === "yes";
      for (const key of ["bedrooms", "bathrooms"])
        values[key] = input[key] ?? null;
      await save("/profile", values, snapshot.version, () => setOpen(false));
    } catch {
      /* Form field errors remain visible. */
    }
  };
  return (
    <>
      <section className="living-contact-strip">
        <div>
          <strong>{profile.address || "Home and contacts"}</strong>
          <Descriptions
            size="small"
            column={1}
            items={[
              {
                key: "agent",
                label: "Agent / landlord",
                children: profile.agent_name || "Not entered",
              },
              {
                key: "email",
                label: "Contact email",
                children: profile.agent_email || "Not entered",
              },
            ]}
          />
        </div>
        <Button id="living-contact-editor" onClick={start} disabled={busy}>
          Edit home and contacts
        </Button>
      </section>
      <Modal
        forceRender
        title="Home and contacts"
        open={open}
        onCancel={() => !busy && setOpen(false)}
        onOk={submit}
        okText="Confirm and save details"
        cancelText="Cancel"
        confirmLoading={busy}
        okButtonProps={{
          disabled: !confirmed,
          "aria-label": "Confirm and save details",
        }}
        cancelButtonProps={{ disabled: busy }}
        mask={{ closable: !busy }}
        closable={!busy}
        width={700}
      >
        <p className="muted">
          Enter actual details you have confirmed. Unspecified conditions remain
          unknown.
        </p>
        <Form
          name="living-profile"
          form={form}
          disabled={busy}
          layout="vertical"
          onValuesChange={() => setConfirmed(false)}
        >
          <Form.Item name="address" label="Home address">
            <Input maxLength={1000} />
          </Form.Item>
          <div className="living-form-grid">
            <Form.Item name="suburb" label="Suburb">
              <Input />
            </Form.Item>
            <Form.Item name="postcode" label="Postcode">
              <Input maxLength={10} />
            </Form.Item>
            <Form.Item name="agent_name" label="Agent or landlord name">
              <Input />
            </Form.Item>
            <Form.Item
              name="agent_email"
              label="Contact email"
              rules={[
                { type: "email", message: "Enter a valid email address" },
              ]}
            >
              <Input type="email" />
            </Form.Item>
            <Form.Item name="agent_phone" label="Contact phone">
              <Input type="tel" />
            </Form.Item>
            <Form.Item name="emergency_phone" label="Emergency repair phone">
              <Input type="tel" />
            </Form.Item>
            <Form.Item name="lease_start_date" label="Lease start date">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="lease_end_date" label="Lease end date">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="move_out_date" label="Expected move-out date">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="moving_to" label="Moving destination">
              <Input />
            </Form.Item>
            <Form.Item name="bedrooms" label="Bedrooms">
              <InputNumber min={0} max={100} precision={0} />
            </Form.Item>
            <Form.Item name="bathrooms" label="Bathrooms">
              <InputNumber min={0} max={100} precision={0} />
            </Form.Item>
            <Form.Item name="carpeted" label="Does the property have carpet?">
              <Select options={yesNo} />
            </Form.Item>
            <Form.Item name="has_pets" label="Pets">
              <Select options={yesNo} />
            </Form.Item>
            <Form.Item name="has_elevator" label="Lift available">
              <Select options={yesNo} />
            </Form.Item>
          </div>
          <Form.Item name="own_furniture" label="My furniture">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="landlord_furniture"
            label="Landlord-provided furniture"
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="notes" label="Other notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
        <Checkbox
          checked={confirmed}
          disabled={busy}
          onChange={(e) => setConfirmed(e.target.checked)}
        >
          I confirm saving these home and contact details.
        </Checkbox>
        {record.version !== snapshot.version && (
          <p role="alert">
            Information has changed. Close this window and check the latest
            details again.
          </p>
        )}
      </Modal>
    </>
  );
}
