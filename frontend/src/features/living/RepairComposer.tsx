import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Form, Input, Select, Space } from "antd";
import { newRequestId } from "../../api/client";
import { polishRepairEmail } from "../../api/living";
import type {
  LivingRecord,
  LivingWrite,
  RepairEmailDraft,
  RepairPolishInput,
  RepairValues,
} from "../../api/living";

type ComposerValues = RepairValues &
  Pick<RepairPolishInput, "language" | "tone">;

export default function RepairComposer({
  record,
  busy,
  save,
}: {
  record: LivingRecord;
  busy: boolean;
  save: LivingWrite;
}) {
  const [form] = Form.useForm<ComposerValues>();
  const priority = Form.useWatch("priority", form);
  const { modal, message } = App.useApp();
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState<RepairEmailDraft | null>(null);
  const [sourceChanged, setSourceChanged] = useState(false);
  const pending = useRef(false);
  const generation = useRef(0);
  const request = useRef<{ fingerprint: string; id: string } | null>(null);
  const preview = useRef<HTMLDivElement>(null);
  const locked = busy || generating;
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );

  const polish = async () => {
    if (pending.current || busy) return;
    try {
      await form.validateFields(["description"]);
    } catch {
      return;
    }
    const values = form.getFieldsValue(true);
    const input: RepairPolishInput = {
      draft: values.description,
      recipient_name: values.recipient_name || "",
      language: "en",
      tone: values.tone,
      title: values.title || "",
      location: values.location || "",
      priority: values.priority,
    };
    const fingerprint = JSON.stringify(input);
    if (request.current?.fingerprint !== fingerprint)
      request.current = { fingerprint, id: newRequestId() };
    const token = ++generation.current;
    pending.current = true;
    setGenerating(true);
    setError("");
    try {
      const output = await polishRepairEmail(
        record.case_id,
        input,
        request.current.id,
      );
      if (generation.current !== token) return;
      setEmail({ subject: output.subject, body: output.body });
      setSourceChanged(false);
      // A deliberate subsequent generation may produce another wording; only retries
      // after errors reuse the same idempotency key.
      request.current = null;
      requestAnimationFrame(() =>
        preview.current?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        }),
      );
    } catch (e) {
      if (generation.current === token)
        setError(
          e instanceof Error
            ? e.message
            : "Polishing could not be completed. Your original draft is preserved. Please retry.",
        );
    } finally {
      pending.current = false;
      if (generation.current === token) setGenerating(false);
    }
  };

  const prepare = async () => {
    if (locked) return;
    try {
      // An AI subject can serve as the repair title when the user left it blank.
      if (!form.getFieldValue("title")?.trim() && email?.subject.trim())
        form.setFieldValue("title", email.subject);
      const fields = await form.validateFields();
      if (email && (!email.subject.trim() || !email.body.trim())) {
        setError("Complete the email subject and body before saving.");
        return;
      }
      const values: RepairValues = {
        title: fields.title,
        description: fields.description,
        location: fields.location || "",
        priority: fields.priority,
        recipient_name: fields.recipient_name || "",
        ...(email ? { email_draft: { ...email } } : {}),
      };
      modal.confirm({
        title: "Prepare this repair email?",
        content: (
          <>
            <p>
              <strong>{email?.subject || values.title}</strong> ·{" "}
              {values.location || "Location not specified"}
            </p>
            <p className="living-prewrap">
              {email?.body || values.description}
            </p>
            <p>
              Recipient: {values.recipient_name || "Name not entered"} ·{" "}
              {record.profile.agent_email ||
                "No email address entered. Copy the draft and add it yourself"}
            </p>
            <p>
              Only an email draft is saved. Check and send it from your own
              email application.
            </p>
          </>
        ),
        okText: "Confirm repair draft",
        cancelText: "Continue editing",
        onOk: async () => {
          const saved = await save("/repairs", values, record.version, () => {
            form.resetFields();
            setEmail(null);
            setSourceChanged(false);
            setError("");
            request.current = null;
          });
          if (!saved)
            throw new Error(
              "Saving could not be completed. Check the page message and retry.",
            );
        },
      });
    } catch {
      /* Form validation stays beside the inputs. */
    }
  };

  return (
    <>
      <p className="muted">
        Write your repair draft and provide the agent or landlord name. AI will
        organise it into an editable email.
      </p>
      {!record.profile.agent_email && (
        <Alert
          type="info"
          title="No email address entered. You can save a repair draft or call the recorded number. Add an email to open it in your email app."
        />
      )}
      <Form
        name="living-repair"
        form={form}
        layout="vertical"
        initialValues={{
          priority: "normal",
          language: "en",
          tone: "polite",
          recipient_name: record.profile.agent_name,
        }}
        disabled={locked}
        onValuesChange={() => {
          if (email) setSourceChanged(true);
        }}
        onFinish={() => void prepare()}
      >
        <div className="living-form-grid">
          <Form.Item
            name="recipient_name"
            label="Agent or landlord name (email greeting)"
          >
            <Input
              aria-label="Repair email recipient name"
              maxLength={200}
              placeholder="For example, Alex; leave blank if unknown"
            />
          </Form.Item>
          <Form.Item
            name="title"
            label="Repair title"
            rules={[
              {
                required: !email,
                whitespace: true,
                message:
                  "Enter a repair title or let AI generate the email first.",
              },
            ]}
          >
            <Input
              aria-label="Repair title"
              maxLength={200}
              placeholder="Optional; AI can generate the subject"
            />
          </Form.Item>
        </div>
        <Form.Item
          name="description"
          label="Repair draft / issue description"
          rules={[
            {
              required: true,
              whitespace: true,
              message: "Describe the issue that needs repair.",
            },
          ]}
        >
          <Input.TextArea
            aria-label="Issue description"
            rows={4}
            maxLength={5000}
            showCount
            placeholder="For example: Water has been leaking under the kitchen sink since last night. Please arrange an inspection."
          />
        </Form.Item>
        <div className="living-form-grid">
          <Form.Item name="location" label="Location">
            <Input
              aria-label="Location"
              maxLength={500}
              placeholder="For example, kitchen or bathroom (optional)"
            />
          </Form.Item>
          <Form.Item name="priority" label="Urgency">
            <Select
              aria-label="Repair urgency"
              options={[
                { value: "normal", label: "Normal" },
                { value: "urgent", label: "Urgent" },
              ]}
            />
          </Form.Item>
          <Form.Item name="language" label="Email language">
            <Select
              aria-label="Email language"
              options={[{ value: "en", label: "English" }]}
            />
          </Form.Item>
          <Form.Item name="tone" label="Email tone">
            <Select
              aria-label="Email tone"
              options={[
                { value: "polite", label: "Polite" },
                { value: "standard", label: "Formal" },
                { value: "concise", label: "Concise" },
              ]}
            />
          </Form.Item>
        </div>
        {priority === "urgent" && (
          <Alert
            type="warning"
            title="For urgent repairs, contact the emergency repair contact first. If anyone is in danger, contact local emergency services immediately."
            description={
              <>
                {record.profile.emergency_phone ? (
                  <a href={`tel:${record.profile.emergency_phone}`}>
                    Emergency repair phone: {record.profile.emergency_phone}
                  </a>
                ) : (
                  "Save an emergency repair phone in Home and contacts."
                )}
                <br />
                <a
                  href="https://www.nsw.gov.au/housing-and-construction/rules/urgent-repairs-residential-rental-properties"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Official NSW urgent repair guidance
                </a>
              </>
            }
          />
        )}
        <p className="muted">
          Polishing sends the original text and greeting from this form to the
          configured AI. Check the generated email. It will not be sent
          automatically.
        </p>
        <Space wrap>
          <Button
            type="primary"
            aria-label={email ? "Polish email again" : "Polish email with AI"}
            loading={generating}
            disabled={locked}
            onClick={() => void polish()}
          >
            {email ? "Polish email again" : "Polish email with AI"}
          </Button>
          {!email && (
            <Button
              aria-label="Prepare repair email"
              disabled={locked}
              onClick={() => void prepare()}
              loading={busy}
            >
              Prepare repair email
            </Button>
          )}
        </Space>
      </Form>
      {error && (
        <Alert
          role="alert"
          type="error"
          title="Email polishing or saving could not be completed"
          description={error}
        />
      )}
      {email && (
        <div
          className="living-polished-email"
          ref={preview}
          aria-label="Polished email"
        >
          <div className="living-card-heading">
            <h3>Polished email</h3>
            <span className="muted">Editable · Not sent</span>
          </div>
          {sourceChanged && (
            <Alert
              type="info"
              title="The original text or options have changed. This email does not update automatically. Polish it again or edit the email below."
            />
          )}
          <Form layout="vertical" disabled={locked}>
            <Form.Item label="Email subject" required>
              <Input
                aria-label="Polished email subject"
                value={email.subject}
                maxLength={200}
                onChange={(e) =>
                  setEmail({ ...email, subject: e.target.value })
                }
              />
            </Form.Item>
            <Form.Item label="Email body" required>
              <Input.TextArea
                aria-label="Polished email body"
                value={email.body}
                maxLength={8000}
                rows={10}
                onChange={(e) => setEmail({ ...email, body: e.target.value })}
              />
            </Form.Item>
          </Form>
          <Space wrap>
            <Button
              disabled={locked}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `Subject: ${email.subject}\n\n${email.body}`,
                  );
                  message.success("Email draft copied.");
                } catch {
                  message.error(
                    "Clipboard unavailable. Select and copy the subject and body directly.",
                  );
                }
              }}
            >
              Copy polished email
            </Button>
            <Button
              type="primary"
              disabled={locked}
              loading={busy}
              onClick={() => void prepare()}
            >
              Save polished repair draft
            </Button>
          </Space>
        </div>
      )}
    </>
  );
}
