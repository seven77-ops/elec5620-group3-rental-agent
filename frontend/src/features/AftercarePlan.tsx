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
          aria-label="重试原操作"
          loading={busy}
          disabled={refreshing}
          onClick={() => void retry()}
        >
          重试原操作
        </Button>
        <Button
          aria-label="读取最新状态并保留输入"
          loading={refreshing}
          disabled={busy}
          onClick={() => void refreshCurrent()}
        >
          读取最新状态并保留输入
        </Button>
      </Space>
      <p className="muted small">
        重试会使用原请求。读取最新状态后，当前输入保留；请核对后重新保存。
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
    <section className="panel" aria-label="退租计划">
      <div className="section-heading">
        <h2>退租计划</h2>
        {plan && <Status value={String(plan.state)} />}
      </div>
      <p className="muted">
        计划日期是实用安排，不是法定期限。任务完成情况与证据由你维护。
      </p>
      {!plan && missingDetails.length > 0 && (
        <Alert
          className="aftercare-plan-guidance"
          type="info"
          showIcon
          title="先补齐房屋资料"
          description={
            <>
              还需要：{missingDetails.join("、")}
              。补齐后，就能安排清洁、物品整理和钥匙交还。
            </>
          }
        />
      )}
      <div className="date-actions">
        <label htmlFor="move-out-date">
          {plan ? "提议新的退租日期" : "计划退租日期"}
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
              title: plan ? "提交改期提案" : "确认生成退租计划",
              content: plan
                ? "提案确认前保留原计划、完成状态和证据。"
                : `按 ${date} 生成并确认实际安排。`,
              okText: plan ? "提交提案" : "确认计划",
              cancelText: "取消",
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
              ? "提交改期提案"
              : missingDetails.length
                ? "补齐资料后生成计划"
                : "生成并确认计划"
          }
        >
          {plan
            ? "提交改期提案"
            : missingDetails.length
              ? "补齐资料后生成计划"
              : "生成并确认计划"}
        </Button>
      </div>
      {plan && (
        <>
          <p>
            当前退租日期：<strong>{text(plan.move_out_date)}</strong>
            <span className="muted small">
              {" "}
              · 时间均为悉尼当地时间（AEST/AEDT）
            </span>
          </p>
          {plan.pending_schedule && (
            <Alert
              showIcon
              type="warning"
              title="有待确认的日期变更"
              description={
                <>
                  <p>
                    提议新日期：
                    <strong>{text((plan.pending_schedule as Dict).move_out_date)}</strong>
                    。确认后以下任务时间会更新：
                  </p>
                  <ul className="plain-list">
                    {(
                      ((plan.pending_schedule as Dict).changes as Dict[] | undefined) ??
                      []
                    ).map((c) => {
                      const task = tasks.find((t) => t.task_id === c.task_id);
                      return (
                        <li key={String(c.task_id)}>
                          {taskTitle(task?.title)}：{sydneyTime(c.old_due_at)} →{" "}
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
                          title: "确认采用新日期？",
                          content:
                            "将按原模块规则更新任务日期并保留完成与证据记录。",
                          okText: "确认改期",
                          cancelText: "取消",
                          onOk: () => send("confirm_date", { accepted: true }),
                        })
                      }
                      aria-label="确认改期"
                    >
                      确认改期
                    </Button>
                    <Button
                      disabled={busy}
                      onClick={() => send("confirm_date", { accepted: false })}
                    >
                      保留原日期
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
                title: "任务",
                dataIndex: "title",
                render: (v) => <span>{taskTitle(v)}</span>,
              },
              {
                title: "计划时间",
                dataIndex: "due_at",
                render: (v) => <span className="small">{sydneyTime(v)}</span>,
              },
              {
                title: "状态",
                dataIndex: "status",
                render: (v) => <Status value={String(v)} />,
              },
              {
                title: "证据",
                dataIndex: "evidence_refs",
                render: (v) => text((v as string[]).join("、") || "尚未附加"),
              },
              {
                title: "操作",
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
                    编辑任务
                  </Button>
                ),
              },
            ]}
          />
          {planNotes(plan).length > 0 && (
            <Alert
              type="warning"
              title="还有资料需要核对"
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
                  title: "确认取消退租计划？",
                  content: "计划将按现有业务规则取消，历史记录保留。",
                  okText: "确认取消",
                  cancelText: "返回",
                  onOk: () =>
                    send("cancel_plan", {
                      tenant_confirmed: true,
                      reason: "租客在本地演示界面明确取消计划",
                    }),
                })
              }
            >
              取消退租计划
            </Button>
          </div>
        </>
      )}
      <Modal
        title="编辑任务与证据"
        open={Boolean(editing)}
        onCancel={() => {
          if (busy || recovery.refreshing) return;
          if (recovery.error) recovery.abandon();
          setEditing(null);
        }}
        confirmLoading={busy}
        okButtonProps={{
          "aria-label": "保存任务",
          disabled: recovery.refreshing,
        }}
        cancelButtonProps={{ disabled: busy || recovery.refreshing }}
        closable={!busy && !recovery.refreshing}
        mask={{ closable: !busy && !recovery.refreshing }}
        onOk={save}
        okText="保存任务"
        cancelText={recovery.error ? "取消本次编辑" : "取消"}
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
            当前已保存：{taskTitle(editing.title)} · {sydneyTime(editing.due_at)}
          </p>
        )}
        <Form
          form={form}
          layout="vertical"
          disabled={busy || recovery.refreshing}
        >
          <Form.Item name="title" label="任务内容" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="status" label="任务状态">
            <Select
              options={[
                { value: "todo", label: "待完成" },
                { value: "done", label: "已完成" },
                { value: "cancelled", label: "已取消" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="due_date"
            label="计划日期"
            extra={
              plan?.pending_schedule
                ? "改期提案确认前不能修改任务日期，仍可编辑状态与证据。"
                : undefined
            }
          >
            <Input type="date" disabled={Boolean(plan?.pending_schedule)} />
          </Form.Item>
          <Form.Item name="evidence_refs" label="证据引用">
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
              需要人工核对（例如发现入住前已有的损坏，或与入住记录不符）
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
                  label="需要核对的原因"
                  extra="提交后转给人工审核；在放行前，押金跟进草稿会暂停生成。"
                  rules={[{ required: true, message: "请说明需要核对的情况" }]}
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
