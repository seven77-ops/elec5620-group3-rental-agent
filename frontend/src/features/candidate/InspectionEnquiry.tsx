import { useState } from "react";
import { Button, Form, Input, Modal, Space } from "antd";
import { CopyOutlined, MailOutlined } from "@ant-design/icons";
import { enquiryMailto, prepareEnquiry } from "./enquiryTemplate";

export default function InspectionEnquiry({ address }: { address: string }) {
  const [agentName, setAgentName] = useState("");
  const [preferredTime, setPreferredTime] = useState("");
  const [questions, setQuestions] = useState("");
  const [email, setEmail] = useState("");
  const [draft, setDraft] = useState<ReturnType<typeof prepareEnquiry> | null>(
    null,
  );
  const [feedback, setFeedback] = useState("");
  const [copying, setCopying] = useState(false);
  const [modal, contextHolder] = Modal.useModal();
  const mailto = draft ? enquiryMailto(email, draft.subject, draft.body) : null;
  const prepare = () => {
    const generate = () => {
      setDraft(
        prepareEnquiry(address, { agentName, preferredTime, questions }),
      );
      setFeedback("");
    };
    if (draft) {
      modal.confirm({
        title: "Replace this draft?",
        content:
          "This will replace the current subject and message with a new draft using the details above.",
        okText: "Replace draft",
        cancelText: "Keep editing",
        onOk: generate,
      });
    } else generate();
  };
  const copy = async () => {
    if (!draft || copying) return;
    setCopying(true);
    setFeedback("");
    try {
      await navigator.clipboard.writeText(
        `Subject: ${draft.subject}\n\n${draft.body}`,
      );
      setFeedback("Message copied.");
    } catch {
      setFeedback("Could not copy. Select and copy the message manually.");
    } finally {
      setCopying(false);
    }
  };
  return (
    <section className="inspection-enquiry" aria-label="Inspection enquiry">
      {contextHolder}
      <h3>Prepare an enquiry</h3>
      <p className="muted small">
        Add any details below, or prepare a message straight away. Review it
        before contacting the agent.
      </p>
      <Form layout="vertical" component="div">
        <div className="inspection-enquiry-details">
          <Form.Item
            label="Agent name (optional)"
            htmlFor="inspection-agent-name"
          >
            <Input
              id="inspection-agent-name"
              value={agentName}
              maxLength={160}
              placeholder="e.g. Alex"
              onChange={(e) => setAgentName(e.target.value)}
            />
          </Form.Item>
          <Form.Item
            label="Preferred viewing time (optional)"
            htmlFor="inspection-preferred-time"
          >
            <Input
              id="inspection-preferred-time"
              value={preferredTime}
              maxLength={250}
              placeholder="e.g. Saturday afternoon"
              onChange={(e) => setPreferredTime(e.target.value)}
            />
          </Form.Item>
        </div>
        <Form.Item
          label="Other questions (optional)"
          htmlFor="inspection-questions"
        >
          <Input.TextArea
            id="inspection-questions"
            value={questions}
            maxLength={2000}
            autoSize={{ minRows: 2, maxRows: 5 }}
            placeholder="Anything else you would like to ask"
            onChange={(e) => setQuestions(e.target.value)}
          />
        </Form.Item>
        <Button
          aria-label="Prepare enquiry"
          icon={<MailOutlined />}
          onClick={prepare}
        >
          Prepare enquiry
        </Button>
        {draft && (
          <div className="inspection-enquiry-draft">
            <div className="inspection-enquiry-draft-heading">
              <h3>Your message</h3>
              <span className="muted small">Editable draft</span>
            </div>
            <Form.Item label="Subject" htmlFor="inspection-subject">
              <Input
                id="inspection-subject"
                value={draft.subject}
                maxLength={300}
                onChange={(e) => {
                  setDraft({ ...draft, subject: e.target.value });
                  setFeedback("");
                }}
              />
            </Form.Item>
            <Form.Item label="Message" htmlFor="inspection-message">
              <Input.TextArea
                id="inspection-message"
                value={draft.body}
                autoSize={{ minRows: 8, maxRows: 16 }}
                onChange={(e) => {
                  setDraft({ ...draft, body: e.target.value });
                  setFeedback("");
                }}
              />
            </Form.Item>
            <Form.Item
              label="Agent email (optional)"
              htmlFor="inspection-agent-email"
              validateStatus={email.trim() && !mailto ? "warning" : undefined}
              help={
                email.trim() && !mailto
                  ? "Enter one valid email address to open your email app."
                  : undefined
              }
            >
              <Input
                id="inspection-agent-email"
                type="email"
                value={email}
                maxLength={254}
                placeholder="Use the email provided by the agent"
                onChange={(e) => setEmail(e.target.value)}
              />
            </Form.Item>
            <Space wrap>
              <Button
                type="primary"
                icon={<CopyOutlined />}
                aria-label="Copy message"
                onClick={() => void copy()}
                loading={copying}
                disabled={!draft.body.trim()}
              >
                Copy message
              </Button>
              {mailto && draft.body.trim() && (
                <Button
                  aria-label="Open email app"
                  href={mailto}
                  icon={<MailOutlined />}
                >
                  Open email app
                </Button>
              )}
            </Space>
            <div className="inspection-enquiry-feedback small" role="status">
              {feedback}
            </div>
            <p className="muted small">
              Opening your email app creates a draft. Send it yourself after
              checking the details. This message stays here while this page is
              open; it is not saved after a refresh.
            </p>
          </div>
        )}
      </Form>
    </section>
  );
}
