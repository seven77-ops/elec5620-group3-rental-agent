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
  prepared: "Draft prepared",
  contacted: "Contacted independently",
  resolved: "Issue resolved",
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
          <h2>Repairs</h2>
        </div>
      </div>
      <RepairComposer
        key={record.case_id}
        record={record}
        busy={busy}
        save={save}
      />
      <h3 className="living-list-title">Repair record</h3>
      {!record.repairs.length && (
        <p className="muted">No repairs recorded yet.</p>
      )}
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
              {repair.location || "Location not specified"} ·{" "}
              {repair.priority === "urgent" ? "Urgent" : "Normal"}
            </p>
            <details open>
              <summary>Email preview</summary>
              <p className="living-email-meta">
                Recipient: {recipient(repair) || "Not entered"}
                {!repair.email.to && record.profile.agent_email
                  ? "(using the current contact email)"
                  : ""}
                <br />
                Subject: {repair.email.subject}
              </p>
              <pre className="living-email-body">{repair.email.body}</pre>
            </details>
            <p className="living-unsent">Draft prepared · Not sent</p>
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
                    message.success("Email draft copied.");
                  } catch {
                    message.error(
                      "Clipboard unavailable. Copy the text manually from the email preview.",
                    );
                  } finally {
                    setCopying(null);
                  }
                }}
              >
                Copy email draft
              </Button>
              {recipient(repair) && (
                <a
                  href={`mailto:${encodeURIComponent(recipient(repair))}?subject=${encodeURIComponent(repair.email.subject)}&body=${encodeURIComponent(repair.email.body)}`}
                >
                  Open in email app
                </a>
              )}
              {record.profile.agent_phone && (
                <a href={`tel:${record.profile.agent_phone}`}>Call contact</a>
              )}
              <Select
                aria-label={`Update repair status ${repair.title}`}
                value={repair.status}
                disabled={busy}
                options={Object.entries(statusLabels).map(([value, label]) => ({
                  value,
                  label,
                }))}
                onChange={(status) => {
                  modal.confirm({
                    title: "Update repair status?",
                    content: `Record “${repair.title}” as “${statusLabels[status as RepairStatus]}”. This does not send an email or contact repair staff.`,
                    okText: "Confirm status update",
                    cancelText: "Cancel",
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
                    `Continue following up repair ${repair.repair_id}“${repair.title}”. Use this saved issue and my follow-up notes; do not create a duplicate repair.`,
                  )
                }
              >
                Discuss this repair
              </Button>
            </div>
            {Boolean(repair.updates?.length) && (
              <div className="living-repair-updates">
                <h4>My follow-up notes</h4>
                {repair.updates!.map((update, index) => (
                  <div key={`${update.at}-${index}`}>
                    <p className="living-prewrap">
                      {update.note || statusLabels[update.status]}
                    </p>
                    <small>
                      {new Date(update.at).toLocaleString("en-AU")} ·{" "}
                      {statusLabels[update.status]}
                    </small>
                  </div>
                ))}
              </div>
            )}
            <small className="muted">
              Prepared at: {new Date(repair.created_at).toLocaleString("en-AU")}
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}
