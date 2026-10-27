import { useEffect, useState } from "react";
import { Alert, App, Button, Form, Input, Select, Space, Tag } from "antd";
import type {
  LivingRecord,
  LivingWrite,
  RepairStatus,
  RepairEntry,
  RepairValues,
} from "../../api/living";
import RepairFollowup from "./RepairFollowup";
const statusLabels: Record<RepairStatus, string> = {
  prepared: "草稿已准备",
  contacted: "已自行联系",
  resolved: "问题已解决",
};
export default function Repairs({
  record,
  busy,
  save,
  focusedId,
  focusVersion,
  onChat,
}: {
  record: LivingRecord;
  busy: boolean;
  save: LivingWrite;
  focusedId?: string | null;
  focusVersion?: number;
  onChat: (message: string) => void;
}) {
  useEffect(() => {
    if (!focusedId) return;
    const card = document.getElementById(`living-repair-${focusedId}`);
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusedId, focusVersion]);
  const [form] = Form.useForm<RepairValues>();
  const priority = Form.useWatch("priority", form);
  const { modal, message } = App.useApp();
  const [copying, setCopying] = useState<string | null>(null);
  const recipient = (repair: RepairEntry) =>
    repair.email.to || record.profile.agent_email;
  const prepare = async () => {
    try {
      const values = await form.validateFields();
      modal.confirm({
        title: "准备这封报修邮件？",
        content: (
          <>
            <p>
              <strong>{values.title}</strong> ·{" "}
              {values.location || "未注明位置"}
            </p>
            <p className="living-prewrap">{values.description}</p>
            <p>
              收件人：
              {record.profile.agent_email ||
                "尚未填写，可复制草稿后自行填写收件人"}
            </p>
            <p>只保存邮件草稿，之后由你核对并在自己的邮箱中发送。</p>
          </>
        ),
        okText: "确认保存报修草稿",
        cancelText: "继续编辑",
        onOk: () =>
          save(
            "/repairs",
            { ...values, location: values.location || "" },
            record.version,
            () => form.resetFields(),
          ).then(() => undefined),
      });
    } catch {
      /* Inline validation. */
    }
  };
  return (
    <section className="living-section">
      <div className="living-section-heading">
        <div>
          <h2>日常报修</h2>
        </div>
      </div>
      {!record.profile.agent_email && (
        <Alert
          type="info"
          title="未填写邮箱，可先保存报修草稿或拨打已记录电话；补充邮箱后可在邮件客户端打开。"
        />
      )}
      <Form
        name="living-repair"
        form={form}
        layout="vertical"
        initialValues={{ priority: "normal" }}
        disabled={busy}
        onFinish={() => void prepare()}
      >
        <div className="living-form-grid">
          <Form.Item
            name="title"
            label="报修标题"
            rules={[
              { required: true, whitespace: true, message: "请填写问题标题" },
            ]}
          >
            <Input aria-label="报修标题" maxLength={200} />
          </Form.Item>
          <Form.Item name="location" label="位置">
            <Input maxLength={200} />
          </Form.Item>
        </div>
        <Form.Item
          name="description"
          label="问题描述"
          rules={[
            {
              required: true,
              whitespace: true,
              message: "请描述目前观察到的问题",
            },
          ]}
        >
          <Input.TextArea
            aria-label="问题描述"
            rows={3}
            maxLength={3000}
            placeholder="发生了什么、何时发现、目前有什么影响"
          />
        </Form.Item>
        <Form.Item name="priority" label="紧急程度">
          <Select
            options={[
              { value: "normal", label: "普通" },
              { value: "urgent", label: "紧急" },
            ]}
          />
        </Form.Item>
        {priority === "urgent" && (
          <Alert
            type="warning"
            title="紧急问题请先联系紧急维修负责人；如有人身危险，请立即联系当地紧急救援。"
            description={
              <>
                {record.profile.emergency_phone ? (
                  <a href={`tel:${record.profile.emergency_phone}`}>
                    紧急维修电话：{record.profile.emergency_phone}
                  </a>
                ) : (
                  "可以在住处与联系人中保存紧急维修电话。"
                )}
                <br />
                <a
                  href="https://www.nsw.gov.au/housing-and-construction/rules/urgent-repairs-residential-rental-properties"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  NSW 紧急维修官方指引
                </a>
              </>
            }
          />
        )}
        <Button
          aria-label="准备报修邮件"
          type="primary"
          htmlType="submit"
          loading={busy}
        >
          准备报修邮件
        </Button>
      </Form>
      <h3 className="living-list-title">报修记录</h3>
      {!record.repairs.length && <p className="muted">还没有报修记录。</p>}
      <div className="living-record-list">
        {[...record.repairs].reverse().map((repair) => (
          <article
            key={repair.repair_id}
            id={`living-repair-${repair.repair_id}`}
            data-repair-id={repair.repair_id}
            tabIndex={-1}
            className={`living-repair-card ${focusedId === repair.repair_id ? "is-targeted" : ""}`}
          >
            <div className="living-card-heading">
              <h3>{repair.title}</h3>
              <Tag color={repair.status === "resolved" ? "green" : "blue"}>
                {statusLabels[repair.status]}
              </Tag>
            </div>
            <p className="muted">
              {repair.location || "位置未注明"} ·{" "}
              {repair.priority === "urgent" ? "紧急" : "普通"}
            </p>
            <details open>
              <summary>邮件预览</summary>
              <p className="living-email-meta">
                收件人：{recipient(repair) || "未填写"}
                {!repair.email.to && record.profile.agent_email
                  ? "（使用当前联系人邮箱）"
                  : ""}
                <br />
                主题：{repair.email.subject}
              </p>
              <pre className="living-email-body">{repair.email.body}</pre>
            </details>
            <p className="living-unsent">草稿已准备 · 尚未发送</p>
            <Space wrap>
              <Button
                loading={copying === repair.repair_id}
                disabled={busy}
                onClick={async () => {
                  setCopying(repair.repair_id);
                  try {
                    await navigator.clipboard.writeText(
                      `To: ${recipient(repair)}\nSubject: ${repair.email.subject}\n\n${repair.email.body}`,
                    );
                    message.success("邮件草稿已复制。");
                  } catch {
                    message.error("无法访问剪贴板，可从邮件预览中手动复制。");
                  } finally {
                    setCopying(null);
                  }
                }}
              >
                复制邮件草稿
              </Button>
              {recipient(repair) && (
                <a
                  href={`mailto:${encodeURIComponent(recipient(repair))}?subject=${encodeURIComponent(repair.email.subject)}&body=${encodeURIComponent(repair.email.body)}`}
                >
                  在邮箱中打开
                </a>
              )}
              {record.profile.agent_phone && (
                <a href={`tel:${record.profile.agent_phone}`}>拨打联系人电话</a>
              )}
              <Select
                aria-label={`更新报修状态 ${repair.title}`}
                value={repair.status}
                disabled={busy}
                options={Object.entries(statusLabels).map(([value, label]) => ({
                  value,
                  label,
                }))}
                onChange={(status) => {
                  modal.confirm({
                    title: "确认更新报修状态？",
                    content: `将「${repair.title}」记录为「${statusLabels[status as RepairStatus]}」。这不会发送邮件或联系维修人员。`,
                    okText: "确认更新状态",
                    cancelText: "取消",
                    onOk: () =>
                      save(
                        `/repairs/${encodeURIComponent(repair.repair_id)}`,
                        { status: status as RepairStatus },
                        record.version,
                      ).then(() => undefined),
                  });
                }}
              />
            </Space>
            <div className="living-repair-followup-actions">
              <RepairFollowup
                repair={repair}
                version={record.version}
                busy={busy}
                save={save}
              />
              <Button
                disabled={busy}
                onClick={() =>
                  onChat(
                    `继续跟进报修 ${repair.repair_id}「${repair.title}」。请基于这条已保存的问题和我的后续说明处理，不要重复新建报修。`,
                  )
                }
              >
                继续聊这条报修
              </Button>
            </div>
            {Boolean(repair.updates?.length) && (
              <div className="living-repair-updates">
                <h4>我记录的后续</h4>
                {repair.updates!.map((update, index) => (
                  <div key={`${update.at}-${index}`}>
                    <p className="living-prewrap">
                      {update.note || statusLabels[update.status]}
                    </p>
                    <small>
                      {new Date(update.at).toLocaleString("zh-CN")} ·{" "}
                      {statusLabels[update.status]}
                    </small>
                  </div>
                ))}
              </div>
            )}
            <small className="muted">
              准备时间：{new Date(repair.created_at).toLocaleString("zh-CN")}
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}
