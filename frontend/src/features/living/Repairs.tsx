import { useEffect, useState } from "react";
import { App, Button, Select, Space, Tag } from "antd";
import type {
  LivingRecord,
  LivingWrite,
  RepairStatus,
  RepairEntry,
} from "../../api/living";
import RepairFollowup from "./RepairFollowup";
import RepairComposer from "./RepairComposer";
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
  const { modal, message } = App.useApp();
  const [copying, setCopying] = useState<string | null>(null);
  const recipient = (repair: RepairEntry) =>
    repair.email.to || record.profile.agent_email;
  return (
    <section className="living-section">
      <div className="living-section-heading">
        <div>
          <h2>日常报修</h2>
        </div>
      </div>
      <RepairComposer
        key={record.case_id}
        record={record}
        busy={busy}
        save={save}
      />
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
