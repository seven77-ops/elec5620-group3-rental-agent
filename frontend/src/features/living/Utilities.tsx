import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Form, Select, Space } from "antd";
import type {
  LivingRecord,
  LivingProvider,
  LivingWrite,
  Utility,
} from "../../api/living";
const fields: { key: Utility; label: string; category: string }[] = [
  { key: "electricity", label: "电力供应商", category: "electricity" },
  { key: "gas", label: "燃气供应商", category: "gas" },
  { key: "internet", label: "网络供应商", category: "internet" },
  { key: "water", label: "供水机构", category: "water" },
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
      title: "确认保存供应商选择？",
      content: (
        <ul>
          {fields.map((f) => (
            <li key={f.key}>
              {f.label}：
              {providers.find((p) => p.id === utilities[f.key])?.name ||
                "尚未选择"}
            </li>
          ))}
        </ul>
      ),
      okText: "确认保存选择",
      cancelText: "取消",
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
          <h2>水电气网</h2>
        </div>
      </div>
      <Alert
        type="info"
        title="供水通常由地址对应的供水机构提供，不能像电力或网络一样自由更换。"
      />
      {dirty && snapshot.current.version !== record.version && (
        <Alert
          type="warning"
          title="资料已有新版本，你未保存的选择仍保留。恢复最新选择后再修改并保存。"
          action={
            <Button
              disabled={busy}
              onClick={() => {
                snapshot.current = record;
                form.setFieldsValue(record.profile.utilities);
                setDirty(false);
              }}
            >
              恢复最新选择
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
                placeholder="尚未选择"
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
          aria-label="保存供应商选择"
          type="primary"
          htmlType="submit"
          loading={busy}
        >
          保存供应商选择
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
            <article
              className="living-provider-card"
              key={p.id}
              data-provider-id={p.id}
            >
              <span className="living-category">
                {p.categories
                  .map(
                    (c) =>
                      ({
                        electricity: "电力",
                        gas: "燃气",
                        internet: "网络",
                        water: "供水",
                        removalist: "搬运",
                        cleaner: "清洁",
                      })[c],
                  )
                  .join(" · ")}
              </span>
              <h3>{p.name}</h3>
              <p>{p.coverage}</p>
              {p.notes && <p className="muted">{p.notes}</p>}
              <Space wrap>
                <a href={p.website} target="_blank" rel="noopener noreferrer">
                  官方网站
                </a>
                <a
                  href={p.contact_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  联系页面
                </a>
                {p.phone && <a href={`tel:${p.phone}`}>{p.phone}</a>}
              </Space>
              <small>
                来源：
                <a
                  href={p.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  官方页面
                </a>{" "}
                · 核对日期 {p.checked_on}
              </small>
            </article>
          ))}
      </div>
    </section>
  );
}
