import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Form, Select } from "antd";
import type {
  LivingRecord,
  LivingProvider,
  LivingWrite,
  Utility,
} from "../../api/living";
import UtilityProviderDetails, {
  providerCategories,
} from "./UtilityProviderDetails";
const fields: { key: Utility; label: string; category: string }[] = [
  {
    key: "electricity",
    label: "Electricity provider",
    category: "electricity",
  },
  { key: "gas", label: "Gas provider", category: "gas" },
  { key: "internet", label: "Internet provider", category: "internet" },
  { key: "water", label: "Water authority", category: "water" },
];
export default function Utilities({
  record,
  providers,
  busy,
  save,
}: {
  record: LivingRecord;
  providers: LivingProvider[];
  busy: boolean;
  save: LivingWrite;
}) {
  const [form] = Form.useForm();
  const [dirty, setDirty] = useState(false);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  useEffect(() => setDetailsId(null), [record.case_id]);
  const snapshot = useRef(record);
  const { modal } = App.useApp();
  useEffect(() => {
    if (!dirty) {
      snapshot.current = record;
      form.setFieldsValue(record.profile.utilities);
    }
  }, [record, form, dirty]);
  const submit = async () => {
    const values = await form.validateFields();
    const utilities = Object.fromEntries(
      fields.map((f) => [f.key, values[f.key] ?? null]),
    ) as LivingRecord["profile"]["utilities"];
    const profile = { ...snapshot.current.profile, utilities };
    const expectedVersion = snapshot.current.version;
    modal.confirm({
      title: "Save provider selection?",
      content: (
        <ul>
          {fields.map((f) => (
            <li key={f.key}>
              {f.label}:
              {providers.find((p) => p.id === utilities[f.key])?.name ||
                "Not selected"}
            </li>
          ))}
        </ul>
      ),
      okText: "Confirm selection",
      cancelText: "Cancel",
      onOk: () =>
        save("/profile", profile, expectedVersion, () => {
          setDirty(false);
        }).then(() => undefined),
    });
  };
  return (
    <section className="living-section">
      <div className="living-section-heading">
        <div>
          <h2>Utilities</h2>
        </div>
      </div>
      <Alert
        type="info"
        title="Water is usually supplied by the authority serving the address and cannot be freely switched like electricity or internet."
      />
      {dirty && snapshot.current.version !== record.version && (
        <Alert
          type="warning"
          title="A newer version is available. Your unsaved selection is preserved. Restore the latest selection before editing and saving."
          action={
            <Button
              disabled={busy}
              onClick={() => {
                snapshot.current = record;
                form.setFieldsValue(record.profile.utilities);
                setDirty(false);
              }}
            >
              Restore latest selection
            </Button>
          }
        />
      )}
      <Form
        name="living-utilities"
        form={form}
        layout="vertical"
        disabled={busy}
        onValuesChange={() => {
          setDirty(true);
        }}
        onFinish={() => void submit()}
      >
        <div className="living-form-grid">
          {fields.map((field) => (
            <Form.Item key={field.key} name={field.key} label={field.label}>
              <Select
                aria-label={field.label}
                allowClear
                placeholder="Not selected"
                options={providers
                  .filter((p) =>
                    p.categories.some(
                      (category) => category === field.category,
                    ),
                  )
                  .map((p) => ({ value: p.id, label: p.name }))}
              />
            </Form.Item>
          ))}
        </div>
        <Button
          aria-label="Save provider selection"
          type="primary"
          htmlType="submit"
          loading={busy}
        >
          Save provider selection
        </Button>
      </Form>
      <div className="living-provider-grid">
        {providers
          .filter((p) =>
            p.categories.some((category) =>
              ["electricity", "gas", "internet", "water"].includes(category),
            ),
          )
          .map((p) => (
            <button
              type="button"
              className="living-provider-card living-provider-trigger"
              key={p.id}
              data-provider-id={p.id}
              aria-label={`${p.name}, view provider details`}
              aria-haspopup="dialog"
              onClick={() => setDetailsId(p.id)}
            >
              <span className="living-category">{providerCategories(p)}</span>
              <strong className="living-provider-name">{p.name}</strong>
              <span className="living-provider-coverage">{p.coverage}</span>
              <span className="living-provider-card-action">
                <span className="muted">
                  {p.plans?.length
                    ? `${p.plans.length}  plans / tariffs`
                    : "Services and contact details"}
                </span>
                <span>View details →</span>
              </span>
            </button>
          ))}
      </div>
      <UtilityProviderDetails
        provider={providers.find((p) => p.id === detailsId)}
        onClose={() => setDetailsId(null)}
      />
    </section>
  );
}
