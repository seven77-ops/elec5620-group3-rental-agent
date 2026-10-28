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
      language: values.language,
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
          e instanceof Error ? e.message : "润色暂未完成，原稿仍保留，请重试。",
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
        setError("请补全邮件主题和正文后保存。");
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
        title: "准备这封报修邮件？",
        content: (
          <>
            <p>
              <strong>{email?.subject || values.title}</strong> ·{" "}
              {values.location || "未注明位置"}
            </p>
            <p className="living-prewrap">
              {email?.body || values.description}
            </p>
            <p>
              收件人：{values.recipient_name || "未填写姓名"} ·{" "}
              {record.profile.agent_email ||
                "尚未填写邮箱，可复制草稿后自行填写"}
            </p>
            <p>只保存邮件草稿，之后由你核对并在自己的邮箱中发送。</p>
          </>
        ),
        okText: "确认保存报修草稿",
        cancelText: "继续编辑",
        onOk: async () => {
          const saved = await save("/repairs", values, record.version, () => {
            form.resetFields();
            setEmail(null);
            setSourceChanged(false);
            setError("");
            request.current = null;
          });
          if (!saved) throw new Error("保存未完成，请核对页面提示后重试。");
        },
      });
    } catch {
      /* Form validation stays beside the inputs. */
    }
  };

  return (
    <>
      <p className="muted">
        写下报修原稿，提供中介或房东姓名，AI 会整理成一封可编辑的邮件。
      </p>
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
          <Form.Item name="recipient_name" label="中介或房东姓名（邮件称呼）">
            <Input
              aria-label="报修邮件收件人姓名"
              maxLength={200}
              placeholder="例如 Alex；不清楚可留空"
            />
          </Form.Item>
          <Form.Item
            name="title"
            label="报修标题"
            rules={[
              {
                required: !email,
                whitespace: true,
                message: "请填写报修标题，或先让 AI 生成邮件。",
              },
            ]}
          >
            <Input
              aria-label="报修标题"
              maxLength={200}
              placeholder="可先留空，由 AI 生成主题"
            />
          </Form.Item>
        </div>
        <Form.Item
          name="description"
          label="报修原稿 / 问题描述"
          rules={[
            {
              required: true,
              whitespace: true,
              message: "请写下要报修的问题。",
            },
          ]}
        >
          <Input.TextArea
            aria-label="问题描述"
            rows={4}
            maxLength={5000}
            showCount
            placeholder="中文或英文都可以，例如：厨房水槽下面从昨晚开始漏水，想请中介安排检查。"
          />
        </Form.Item>
        <div className="living-form-grid">
          <Form.Item name="location" label="位置">
            <Input
              aria-label="位置"
              maxLength={500}
              placeholder="例如厨房、浴室（可选）"
            />
          </Form.Item>
          <Form.Item name="priority" label="紧急程度">
            <Select
              aria-label="报修紧急程度"
              options={[
                { value: "normal", label: "普通" },
                { value: "urgent", label: "紧急" },
              ]}
            />
          </Form.Item>
          <Form.Item name="language" label="邮件语言">
            <Select
              aria-label="邮件语言"
              options={[
                { value: "en", label: "英文" },
                { value: "zh", label: "中文" },
              ]}
            />
          </Form.Item>
          <Form.Item name="tone" label="邮件语气">
            <Select
              aria-label="邮件语气"
              options={[
                { value: "polite", label: "礼貌" },
                { value: "standard", label: "正式" },
                { value: "concise", label: "简洁" },
              ]}
            />
          </Form.Item>
        </div>
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
        <p className="muted">
          点击润色会将本表单原稿和称呼发送至已配置的
          AI，生成后请核对。邮件不会自动发送。
        </p>
        <Space wrap>
          <Button
            type="primary"
            aria-label={email ? "重新润色邮件" : "AI 润色邮件"}
            loading={generating}
            disabled={locked}
            onClick={() => void polish()}
          >
            {email ? "重新润色邮件" : "AI 润色邮件"}
          </Button>
          {!email && (
            <Button
              aria-label="准备报修邮件"
              disabled={locked}
              onClick={() => void prepare()}
              loading={busy}
            >
              准备报修邮件
            </Button>
          )}
        </Space>
      </Form>
      {error && (
        <Alert
          role="alert"
          type="error"
          title="邮件润色或保存未完成"
          description={error}
        />
      )}
      {email && (
        <div
          className="living-polished-email"
          ref={preview}
          aria-label="润色后的邮件"
        >
          <div className="living-card-heading">
            <h3>润色后的邮件</h3>
            <span className="muted">可继续编辑 · 尚未发送</span>
          </div>
          {sourceChanged && (
            <Alert
              type="info"
              title="原稿或选项已修改，当前邮件不会自动更新。请重新润色，或在下方自行修改邮件。"
            />
          )}
          <Form layout="vertical" disabled={locked}>
            <Form.Item label="邮件主题" required>
              <Input
                aria-label="润色邮件主题"
                value={email.subject}
                maxLength={200}
                onChange={(e) =>
                  setEmail({ ...email, subject: e.target.value })
                }
              />
            </Form.Item>
            <Form.Item label="邮件正文" required>
              <Input.TextArea
                aria-label="润色邮件正文"
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
                  message.success("邮件草稿已复制。");
                } catch {
                  message.error("无法访问剪贴板，可直接选中主题和正文复制。");
                }
              }}
            >
              复制润色邮件
            </Button>
            <Button
              type="primary"
              disabled={locked}
              loading={busy}
              onClick={() => void prepare()}
            >
              保存润色报修草稿
            </Button>
          </Space>
        </div>
      )}
    </>
  );
}
