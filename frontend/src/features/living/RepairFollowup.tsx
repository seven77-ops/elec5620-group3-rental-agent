import { useState } from "react";
import { Alert, App, Button, Form, Input, Modal, Select, Space } from "antd";
import type {
  LivingWrite,
  RepairEntry,
  RepairStatus,
  RepairTone,
  RepairUpdateValues,
} from "../../api/living";
const statuses: Record<RepairStatus, string> = {
  prepared: "Draft prepared",
  contacted: "Contacted independently",
  resolved: "Issue resolved",
};
const tones: Record<RepairTone, string> = {
  standard: "Standard",
  polite: "More polite",
  concise: "More concise",
};
export default function RepairFollowup({
  repair,
  version,
  busy,
  save,
}: {
  repair: RepairEntry;
  version: number;
  busy: boolean;
  save: LivingWrite;
}) {
  const [open, setOpen] = useState(false),
    [snapshot, setSnapshot] = useState({ repair, version }),
    [failed, setFailed] = useState(false);
  const [form] = Form.useForm<{
    status: RepairStatus;
    note: string;
    email_tone: RepairTone;
  }>();
  const { modal, message } = App.useApp();
  const start = () => {
    setSnapshot({ repair, version });
    setFailed(false);
    form.setFieldsValue({
      status: repair.status,
      note: "",
      email_tone: repair.email_tone || "standard",
    });
    setOpen(true);
  };
  const confirm = async () => {
    try {
      const input = await form.validateFields();
      const values: RepairUpdateValues = {};
      if (input.status !== snapshot.repair.status) values.status = input.status;
      if (input.note?.trim()) values.note = input.note;
      if (input.email_tone !== (snapshot.repair.email_tone || "standard"))
        values.email_tone = input.email_tone;
      if (!Object.keys(values).length) {
        message.info(
          "Enter a follow-up note, change the status, or select a different tone.",
        );
        return;
      }
      modal.confirm({
        title: "Save follow-up for this repair?",
        content: (
          <>
            <p>{snapshot.repair.title}</p>
            {values.note && <p className="living-prewrap">{values.note}</p>}
            {values.status && <p>Status: {statuses[values.status]}</p>}
            {values.email_tone && <p>Draft tone: {tones[values.email_tone]}</p>}
            <p>
              Only this repair is updated. No new issue is created and no email
              is sent.
            </p>
          </>
        ),
        okText: "Confirm repair follow-up",
        cancelText: "Continue editing",
        onOk: async () => {
          const saved = await save(
            `/repairs/${encodeURIComponent(snapshot.repair.repair_id)}`,
            values,
            snapshot.version,
            () => setOpen(false),
          );
          if (!saved) setFailed(true);
        },
      });
    } catch {
      /* Inline form validation. */
    }
  };
  return (
    <>
      <Space wrap>
        <Button disabled={busy} onClick={start}>
          Record follow-up
        </Button>
        {!repair.email_draft && (
          <Button disabled={busy} onClick={start}>
            Adjust email tone
          </Button>
        )}
      </Space>
      <Modal
        forceRender
        title="Record repair follow-up"
        open={open}
        onCancel={() => !busy && setOpen(false)}
        onOk={() => void confirm()}
        okText="Check and save follow-up"
        cancelText="Cancel"
        confirmLoading={busy}
        okButtonProps={{ "aria-label": "Check and save follow-up" }}
        cancelButtonProps={{ disabled: busy }}
        closable={!busy}
        mask={{ closable: !busy }}
      >
        <p>
          <strong>{snapshot.repair.title}</strong>
        </p>
        {failed && (
          <Alert
            type="error"
            title="Not saved yet. Your input is preserved. Close this window to check the page error. Load the latest information and check again if needed."
          />
        )}
        <Form
          name={`repair-followup-${repair.repair_id}`}
          form={form}
          layout="vertical"
          disabled={busy}
        >
          <Form.Item name="note" label="Reply or my notes">
            <Input.TextArea
              aria-label="Reply or my notes"
              rows={3}
              maxLength={3000}
            />
          </Form.Item>
          <Form.Item name="status" label="Repair status">
            <Select
              options={Object.entries(statuses).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          {!snapshot.repair.email_draft && (
            <Form.Item name="email_tone" label="Email tone">
              <Select
                options={Object.entries(tones).map(([value, label]) => ({
                  value,
                  label,
                }))}
              />
            </Form.Item>
          )}
        </Form>
        <p className="living-note">
          {snapshot.repair.email_draft
            ? "Recording progress preserves the email text you have checked."
            : "Only the email wording changes. The original issue and recipient remain. State explicitly when an appointment time is not confirmed."}
        </p>
      </Modal>
    </>
  );
}
