import { App, Button, Space } from "antd";
import type { AssistantMessage } from "../../api/assistant";
import "./repairDraft.css";

export default function RepairDraftCard({
  draft,
  onSuggest,
  disabled,
}: {
  draft: NonNullable<AssistantMessage["repair_email"]>;
  onSuggest: (message: string) => void;
  disabled: boolean;
}) {
  const { message } = App.useApp();
  return (
    <section className="repair-email-preview" aria-label="Repair email draft">
      <p className="muted small">English email draft · Not sent</p>
      {draft.to ? (
        <p className="small">To: {draft.to}</p>
      ) : (
        <p className="muted small">
          Copy the body now and add a recipient later.
        </p>
      )}
      <strong className="repair-email-subject">{draft.subject}</strong>
      <div className="repair-email-body">{draft.body}</div>
      <Space wrap>
        <Button
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(
                `Subject: ${draft.subject}\n\n${draft.body}`,
              );
              message.success("Email draft copied.");
            } catch {
              message.error("Could not copy. Select and copy the body above.");
            }
          }}
        >
          Copy email draft
        </Button>
        <Button
          disabled={disabled}
          onClick={() =>
            onSuggest(
              "Make this repair email more polite in English, keep the original facts and do not send it.",
            )
          }
        >
          More polite
        </Button>
        <Button
          disabled={disabled}
          onClick={() =>
            onSuggest(
              "Make this repair email more concise in English, keep the original facts and do not send it.",
            )
          }
        >
          More concise
        </Button>
        <Button
          disabled={disabled}
          onClick={() =>
            onSuggest(
              "Regenerate this repair email in English, keep the original facts and do not send it.",
            )
          }
        >
          Regenerate in English
        </Button>
      </Space>
      <p className="muted small">
        The suggestion goes into the input box. Send it to generate a new
        version; aftercare records change only when saved.
      </p>
    </section>
  );
}
