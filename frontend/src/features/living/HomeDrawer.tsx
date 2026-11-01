import { useEffect, useRef, useState } from "react";
import { Button, Descriptions, Drawer, Form, Input, Space, Spin } from "antd";
import {
  getHomeSummary,
  writeLivingServices,
  type BasicHome,
  type HomeSummary,
  type LivingRecord,
  type LivingProvider,
} from "../../api/living";
import { newRequestId } from "../../api/client";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";
import HomeSavedServices, { type HomeServiceTarget } from "./HomeSavedServices";
const labels: Record<keyof BasicHome, string> = {
  address: "Address",
  suburb: "Suburb",
  postcode: "Postcode",
  agent_name: "Agent / landlord",
  agent_email: "Email",
  agent_phone: "Phone",
};
export default function HomeDrawer({
  caseId,
  open,
  onClose,
  onSaved,
  providers,
  onOpenService,
}: {
  caseId: string;
  open: boolean;
  onClose: () => void;
  onSaved: (record: LivingRecord) => void;
  providers: LivingProvider[];
  onOpenService: (target: HomeServiceTarget) => void;
}) {
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [form] = Form.useForm();
  const action = useAction();
  const generation = useRef(0);
  const read = async (preserve = false) => {
    const edits =
      preserve && summary
        ? Object.fromEntries(
            (Object.keys(labels) as (keyof BasicHome)[])
              .filter((key) => form.getFieldValue(key) !== summary.values[key])
              .map((key) => [key, form.getFieldValue(key)]),
          )
        : {};
    const token = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const value = await getHomeSummary(caseId);
      if (token !== generation.current) return;
      setSummary(value);
      if (preserve) form.setFieldsValue({ ...value.values, ...edits });
      else if (editing) form.setFieldsValue(value.values);
      action.clear();
    } catch (error) {
      if (token === generation.current) setError(error);
    } finally {
      if (token === generation.current) setLoading(false);
    }
  };
  useEffect(() => {
    if (open) {
      setEditing(false);
      setSummary(null);
      action.clear();
      void read();
    }
    return () => {
      generation.current++;
    };
  }, [open, caseId]);
  const save = async () => {
    if (!summary || action.busy || action.error) return;
    try {
      const values = await form.validateFields();
      const body = { ...summary.profile, ...values };
      const version = summary.expected_version;
      const requestId = newRequestId();
      const token = generation.current;
      await action.run(async () => {
        const updated = await writeLivingServices(
          caseId,
          "/profile",
          body,
          version,
          requestId,
        );
        if (token !== generation.current) return;
        onSaved(updated);
        setSummary({
          profile: updated.profile,
          expected_version: updated.version,
          bookings: updated.bookings,
          values: Object.fromEntries(
            Object.keys(labels).map((key) => [
              key,
              updated.profile[key as keyof BasicHome],
            ]),
          ) as BasicHome,
          sources: Object.fromEntries(
            Object.keys(labels).map((key) => [key, "Saved home details"]),
          ),
        });
        setEditing(false);
      });
    } catch {
      /* Inline errors retain edits. */
    }
  };
  return (
    <Drawer
      rootClassName="home-toolbar-drawer"
      title="My home"
      width={560}
      open={open}
      onClose={() => {
        if (!action.busy) onClose();
      }}
      closable={!action.busy}
      mask={{ closable: !action.busy }}
    >
      <Failure error={error} retry={() => void read(editing)} />
      {loading ? (
        <Spin />
      ) : (
        summary && (
          <>
            {!editing ? (
              <>
                <Descriptions
                  column={1}
                  items={Object.entries(labels).map(([key, label]) => ({
                    key,
                    label,
                    children:
                      summary.values[key as keyof BasicHome] || "Not provided",
                  }))}
                />
                {Object.values(summary.sources).length > 0 && (
                  <p className="muted small">
                    Source:{" "}
                    {[...new Set(Object.values(summary.sources))].join(" · ")}
                  </p>
                )}
                <Button
                  onClick={() => {
                    form.setFieldsValue(summary.values);
                    setEditing(true);
                  }}
                >
                  Edit details
                </Button>
              </>
            ) : (
              <>
                <Form
                  name="basic-home"
                  form={form}
                  layout="vertical"
                  disabled={action.busy || Boolean(action.error)}
                >
                  {Object.entries(labels).map(([key, label]) => (
                    <Form.Item
                      key={key}
                      name={key}
                      label={label}
                      rules={
                        key === "agent_email"
                          ? [
                              {
                                type: "email",
                                message: "Enter a valid email address.",
                              },
                            ]
                          : key === "postcode"
                            ? [
                                {
                                  pattern: /^[0-9]{4}$/,
                                  message: "Enter a four-digit postcode.",
                                },
                              ]
                            : []
                      }
                    >
                      <Input
                        maxLength={key === "postcode" ? 4 : 1000}
                        type={
                          key === "agent_email"
                            ? "email"
                            : key === "agent_phone"
                              ? "tel"
                              : "text"
                        }
                      />
                    </Form.Item>
                  ))}
                </Form>
                <Space wrap>
                  <Button
                    type="primary"
                    loading={action.busy}
                    disabled={Boolean(action.error)}
                    onClick={() => void save()}
                  >
                    Save details
                  </Button>
                  <Button
                    disabled={action.busy}
                    onClick={() => {
                      setEditing(false);
                      action.clear();
                    }}
                  >
                    Cancel editing
                  </Button>
                </Space>
              </>
            )}
            {!editing && (
              <HomeSavedServices
                summary={summary}
                providers={providers}
                onOpen={onOpenService}
              />
            )}
          </>
        )
      )}
      <Failure error={action.error} retry={action.retry} />
      {Boolean(action.error) && (
        <Button
          loading={loading}
          disabled={action.busy}
          onClick={() => void read(true)}
        >
          Load latest details
        </Button>
      )}
    </Drawer>
  );
}
