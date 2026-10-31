import { useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
} from "antd";
import type { Dict } from "../api/types";
import { Status, text } from "../components/Common";
import AftercareFailure from "./aftercare/AftercareFailure";
import {
  planNotes,
  sydneyTime,
  sydneyToday,
  taskTitle,
} from "./aftercare/presentation";
export type SendCommand = (
  operation: string,
  payload: Dict,
) => Promise<boolean>;
export interface CommandRecoveryProps {
  error: unknown;
  busy: boolean;
  refreshing: boolean;
  retry: () => Promise<boolean>;
  refreshCurrent: () => Promise<void>;
  abandon: () => void;
}
export function CommandRecovery({
  error,
  busy,
  refreshing,
  retry,
  refreshCurrent,
}: CommandRecoveryProps) {
  if (!error) return null;
  return (
    <>
      <AftercareFailure error={error} />
      <Space wrap>
        <Button
          aria-label="Retry original action"
          loading={busy}
          disabled={refreshing}
          onClick={() => void retry()}
        >
          Retry original action
        </Button>
        <Button
          aria-label="Load latest state and preserve input"
          loading={refreshing}
          disabled={busy}
          onClick={() => void refreshCurrent()}
        >
          Load latest state and preserve input
        </Button>
      </Space>
      <p className="muted small">
        Retry uses the original request. Loading the latest state preserves your
        input. Check it before saving again.
      </p>
    </>
  );
}
export default function AftercarePlan({
  plan,
  initialDate,
  evidence,
  send,
  busy,
  recovery,
  missingDetails = [],
  onCompleteTenancy,
}: {
  missingDetails?: string[];
  onCompleteTenancy?: () => void;
  plan: Dict | null;
  initialDate?: string;
  evidence: Dict[];
  send: SendCommand;
  busy: boolean;
  recovery: CommandRecoveryProps;
}) {
  const [date, setDate] = useState(initialDate ?? "2026-10-31");
  const [editing, setEditing] = useState<Dict | null>(null);
  const [form] = Form.useForm();
  const { modal } = App.useApp();
  // Show tasks in the order they fall due; IDs keep their original positions in the plan.
  const tasks = [...((plan?.tasks ?? []) as Dict[])].sort((a, b) =>
    String(a.due_at).localeCompare(String(b.due_at)),
  );
  const save = async () => {
    try {
      const v = await form.validateFields();
      const saved = await send("edit_task", {
        task_id: editing!.task_id,
        status: v.status,
        // Keep the generated title unless the tenant actually rewrote it.
        ...(v.title !== taskTitle(editing!.title) ? { title: v.title } : {}),
        evidence_refs: v.evidence_refs ?? [],
        ...(v.flag_review && v.review_reason?.trim()
          ? { review_reason: v.review_reason.trim() }
          : {}),
        ...(!plan?.pending_schedule &&
        v.due_date &&
        v.due_date !== String(editing!.due_at).slice(0, 10)
          ? { due_date: v.due_date }
          : {}),
      });
      if (saved) setEditing(null);
    } catch {
      /* Inline errors. */
    }
  };
  return (
    <section className="panel" aria-label="Move-out plan">
      <div className="section-heading">
        <h2>Move-out plan</h2>
        {plan && <Status value={String(plan.state)} />}
      </div>
      <p className="muted">
        Plan dates are practical arrangements, not legal deadlines. You maintain
        task completion and evidence.
      </p>
      {!plan && missingDetails.length > 0 && (
        <Alert
          className="aftercare-plan-guidance"
          type="info"
          showIcon
          title="Complete property details first"
          description={
            <>
              Still needed: {missingDetails.join(", ")}. Once complete, plan
              cleaning, packing, and key return.
            </>
          }
        />
      )}
      <div className="date-actions">
        <label htmlFor="move-out-date">
          {plan ? "Propose a new move-out date" : "Planned move-out date"}
        </label>
        <Input
          id="move-out-date"
          type="date"
          min={sydneyToday()}
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <Button
          type="primary"
          loading={busy}
          disabled={
            !date || (!plan && missingDetails.length > 0 && !onCompleteTenancy)
          }
          onClick={() => {
            if (!plan && missingDetails.length > 0) {
              onCompleteTenancy?.();
              return;
            }
            modal.confirm({
              title: plan
                ? "Submit date change proposal"
                : "Confirm move-out plan generation",
              content: plan
                ? "The original plan, completion status, and evidence remain until the proposal is confirmed."
                : `Use ${date}  to generate and confirm practical arrangements.`,
              okText: plan ? "Submit proposal" : "Confirm plan",
              cancelText: "Cancel",
              onOk: () =>
                send(
                  plan ? "propose_date" : "create_plan",
                  plan
                    ? { move_out_date: date }
                    : { move_out_date: date, schedule_confirmed: true },
                ),
            });
          }}
          aria-label={
            plan
              ? "Submit date change proposal"
              : missingDetails.length
                ? "Complete details before generating a plan"
                : "Generate and confirm plan"
          }
        >
          {plan
            ? "Submit date change proposal"
            : missingDetails.length
              ? "Complete details before generating a plan"
              : "Generate and confirm plan"}
        </Button>
      </div>
      {plan && (
        <>
          <p>
            Current move-out date:<strong>{text(plan.move_out_date)}</strong>
            <span className="muted small">
              {" "}
              · All times are Sydney local time (AEST/AEDT)
            </span>
          </p>
          {plan.pending_schedule && (
            <Alert
              showIcon
              type="warning"
              title="A date change awaits confirmation"
              description={
                <>
                  <p>
                    Proposed date:
                    <strong>
                      {text((plan.pending_schedule as Dict).move_out_date)}
                    </strong>
                    . Confirming will update these task times:
                  </p>
                  <ul className="plain-list">
                    {(
                      ((plan.pending_schedule as Dict).changes as
                        Dict[] | undefined) ?? []
                    ).map((c) => {
                      const task = tasks.find((t) => t.task_id === c.task_id);
                      return (
                        <li key={String(c.task_id)}>
                          {taskTitle(task?.title)}: {sydneyTime(c.old_due_at)} →{" "}
                          {sydneyTime(c.new_due_at)}
                        </li>
                      );
                    })}
                  </ul>
                  <Space>
                    <Button
                      loading={busy}
                      onClick={() =>
                        modal.confirm({
                          title: "Use the new date?",
                          content:
                            "Task dates will update under the existing rules. Completion and evidence records are preserved.",
                          okText: "Confirm date change",
                          cancelText: "Cancel",
                          onOk: () => send("confirm_date", { accepted: true }),
                        })
                      }
                      aria-label="Confirm date change"
                    >
                      Confirm date change
                    </Button>
                    <Button
                      disabled={busy}
                      onClick={() => send("confirm_date", { accepted: false })}
                    >
                      Keep original date
                    </Button>
                  </Space>
                </>
              }
            />
          )}
          <Table
            rowKey="task_id"
            dataSource={tasks}
            pagination={false}
            scroll={{ x: 650 }}
            columns={[
              {
                title: "Task",
                dataIndex: "title",
                render: (v) => <span>{taskTitle(v)}</span>,
              },
              {
                title: "Planned time",
                dataIndex: "due_at",
                render: (v) => <span className="small">{sydneyTime(v)}</span>,
              },
              {
                title: "Status",
                dataIndex: "status",
                render: (v) => <Status value={String(v)} />,
              },
              {
                title: "Evidence",
                dataIndex: "evidence_refs",
                render: (v) =>
                  text((v as string[]).join(", ") || "Not attached"),
              },
              {
                title: "Action",
                render: (_, row) => (
                  <Button
                    size="small"
                    disabled={busy}
                    onClick={() => {
                      setEditing(row);
                      form.resetFields();
                      form.setFieldsValue({
                        title: taskTitle(row.title),
                        status: row.status,
                        evidence_refs: row.evidence_refs,
                        due_date: String(row.due_at).slice(0, 10),
                      });
                    }}
                  >
                    Edit task
                  </Button>
                ),
              },
            ]}
          />
          {planNotes(plan).length > 0 && (
            <Alert
              type="warning"
              title="More information needs checking"
              description={
                <ul className="plain-list">
                  {planNotes(plan).map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              }
            />
          )}
          <div className="consent-actions">
            <Button
              danger
              disabled={busy}
              onClick={() =>
                modal.confirm({
                  title: "Cancel the move-out plan?",
                  content:
                    "The plan will be cancelled under existing rules. History is preserved.",
                  okText: "Confirm cancellation",
                  cancelText: "Back",
                  onOk: () =>
                    send("cancel_plan", {
                      tenant_confirmed: true,
                      reason:
                        "Tenant explicitly cancelled the plan in the local demo",
                    }),
                })
              }
            >
              Cancel move-out plan
            </Button>
          </div>
        </>
      )}
      <Modal
        title="Edit task and evidence"
        open={Boolean(editing)}
        onCancel={() => {
          if (busy || recovery.refreshing) return;
          if (recovery.error) recovery.abandon();
          setEditing(null);
        }}
        confirmLoading={busy}
        okButtonProps={{
          "aria-label": "Save task",
          disabled: recovery.refreshing,
        }}
        cancelButtonProps={{ disabled: busy || recovery.refreshing }}
        closable={!busy && !recovery.refreshing}
        mask={{ closable: !busy && !recovery.refreshing }}
        onOk={save}
        okText="Save task"
        cancelText={recovery.error ? "Cancel this edit" : "Cancel"}
      >
        <CommandRecovery
          {...recovery}
          retry={async () => {
            const saved = await recovery.retry();
            if (saved) setEditing(null);
            return saved;
          }}
        />
        {editing && (
          <p className="muted small">
            Currently saved: {taskTitle(editing.title)} ·{" "}
            {sydneyTime(editing.due_at)}
          </p>
        )}
        <Form
          form={form}
          layout="vertical"
          disabled={busy || recovery.refreshing}
        >
          <Form.Item
            name="title"
            label="Task details"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="status" label="Task status">
            <Select
              options={[
                { value: "todo", label: "To do" },
                { value: "done", label: "Completed" },
                { value: "cancelled", label: "Cancelled" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="due_date"
            label="Planned date"
            extra={
              plan?.pending_schedule
                ? "Task dates cannot be edited until the date proposal is confirmed. Status and evidence can still be edited."
                : undefined
            }
          >
            <Input type="date" disabled={Boolean(plan?.pending_schedule)} />
          </Form.Item>
          <Form.Item name="evidence_refs" label="Evidence references">
            <Select
              mode="multiple"
              options={evidence.map((e) => ({
                value: String(e.evidence_id),
                label: `${e.summary ?? e.evidence_id} · ${e.kind}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="flag_review" valuePropName="checked">
            <Checkbox>
              Human review needed (for example, pre-existing damage or a
              mismatch with the move-in record)
            </Checkbox>
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(a, b) => a.flag_review !== b.flag_review}
          >
            {({ getFieldValue }) =>
              getFieldValue("flag_review") ? (
                <Form.Item
                  name="review_reason"
                  label="Reason for review"
                  extra="Submission refers this to human review. Bond follow-up drafts are paused until release."
                  rules={[
                    { required: true, message: "Describe what needs checking" },
                  ]}
                >
                  <Input.TextArea rows={2} maxLength={2000} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
}
