import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Checkbox, Modal, Space, Spin } from "antd";
import { getTenancySource, importTenancySource } from "../../api/living";
import type {
  LivingProfile,
  LivingRecord,
  TenancyPreview,
} from "../../api/living";
import { newRequestId } from "../../api/client";
import { useAction } from "../../components/useAction";
const labels: Partial<Record<keyof LivingProfile, string>> = {
  address: "居住地址",
  agent_name: "中介或房东姓名",
  agent_email: "联系邮箱",
  agent_phone: "联系电话",
  lease_start_date: "租约开始日期",
  lease_end_date: "租约结束日期",
  carpeted: "有地毯",
};
const sourceLabel = (
  label: string | undefined,
  version: number | undefined,
) => {
  const title = label || "租约资料";
  return version && !/\bv\d+\b/i.test(title)
    ? `${title} · v${version}`
    : title;
};
const nonempty = (value: unknown) =>
  value !== null &&
  value !== undefined &&
  (typeof value !== "string" || value.trim() !== "");
const display = (value: unknown) =>
  value === true
    ? "是"
    : value === false
      ? "否"
      : nonempty(value)
        ? String(value)
        : "尚未填写";
export default function TenancySource({
  record,
  busy,
  onImported,
}: {
  record: LivingRecord;
  busy: boolean;
  onImported: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false),
    [preview, setPreview] = useState<TenancyPreview | null>(null),
    [selected, setSelected] = useState<string[]>([]),
    [actual, setActual] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState<string | null>(null);
  const action = useAction(),
    generation = useRef(0),
    { modal } = App.useApp();
  useEffect(
    () => () => {
      generation.current++;
    },
    [record.case_id],
  );
  const read = async () => {
    if (action.busy) return;
    const token = ++generation.current;
    setOpen(true);
    setLoading(true);
    setPreview(null);
    setError(null);
    setActual(false);
    action.clear();
    try {
      const value = await getTenancySource(record.case_id);
      if (token !== generation.current) return;
      setPreview(value);
      setSelected(
        Object.keys(value.values).filter(
          (key) =>
            key in labels &&
            nonempty(value.values[key as keyof LivingProfile]) &&
            JSON.stringify(value.values[key as keyof LivingProfile]) !==
              JSON.stringify(value.previous[key as keyof LivingProfile]),
        ),
      );
    } catch (error) {
      if (token === generation.current)
        setError(
          error instanceof Error ? error.message : "租约来源暂时无法读取。",
        );
    } finally {
      if (token === generation.current) setLoading(false);
    }
  };
  const confirm = () => {
    if (!actual || !preview?.source?.current || !selected.length || action.busy)
      return;
    const source = structuredClone(preview),
      fields = [...selected],
      requestId = newRequestId(),
      token = generation.current;
    modal.confirm({
      title: "确认接入这些实际租约资料？",
      content: (
        <>
          <p>
            只更新你勾选的非空字段，现有供应商、报修、服务记录与附件保持不变。
          </p>
          <ul>
            {fields.map((key) => (
              <li key={key}>
                {labels[key as keyof LivingProfile] || key}：
                {display(source.values[key as keyof LivingProfile])}
              </li>
            ))}
          </ul>
        </>
      ),
      okText: "确认接入租约资料",
      cancelText: "继续核对",
      onOk: () =>
        action
          .run(async () => {
            await importTenancySource(
              record.case_id,
              source,
              fields,
              requestId,
            );
            if (generation.current !== token) return;
            await onImported();
            if (generation.current !== token) return;
            const latest = await getTenancySource(record.case_id);
            if (generation.current !== token) return;
            setPreview(latest);
            setActual(false);
            setSelected([]);
            setOpen(false);
          })
          .then(() => undefined),
    });
  };
  const fields = Object.keys(preview?.values ?? {}).filter(
    (key) =>
      key in labels && nonempty(preview?.values[key as keyof LivingProfile]),
  );
  return (
    <section className="living-source-bar">
      <div>
        <strong>租约与生活资料</strong>
        <p>
          {record.tenancy_source
            ? `已接入：${sourceLabel(record.tenancy_source.label, record.tenancy_source.version)}`
            : "从已保存的租约核对地址、联系人与租期。"}
        </p>
      </div>
      <Button disabled={busy || action.busy} onClick={() => void read()}>
        查看租约来源
      </Button>
      <Modal
        title="核对租约来源"
        open={open}
        onCancel={() => !action.busy && setOpen(false)}
        onOk={confirm}
        okText="接入所选资料"
        cancelText="取消"
        confirmLoading={action.busy}
        okButtonProps={{
          disabled:
            loading || !actual || !preview?.source?.current || !selected.length,
          "aria-label": "接入所选资料",
        }}
        cancelButtonProps={{ disabled: action.busy, "aria-label": "取消" }}
        closable={!action.busy}
        mask={{ closable: !action.busy }}
        width={680}
      >
        {loading ? (
          <div className="living-loading">
            <Spin />
            <span>正在读取租约来源…</span>
          </div>
        ) : (
          <>
            {(error || action.error) && (
              <Alert
                type="error"
                title="来源接入未完成"
                description={
                  error ||
                  (action.error instanceof Error
                    ? action.error.message
                    : "请重新核对来源。")
                }
                action={
                  <Space>
                    {Boolean(action.error) && (
                      <Button
                        loading={action.busy}
                        onClick={() => void action.retry()}
                      >
                        重试原接入
                      </Button>
                    )}
                    <Button disabled={action.busy} onClick={() => void read()}>
                      重新预览
                    </Button>
                  </Space>
                }
              />
            )}
            {!preview?.source ? (
              <p className="muted">
                还没有可接入的租约资料。租约草稿或合同复核都不能自动证明实际入住。
              </p>
            ) : (
              <>
                <p className="living-source-label">
                  {sourceLabel(preview.source.label, preview.source.version)}
                </p>
                {preview.source.warning && (
                  <Alert
                    type={preview.source.current ? "info" : "warning"}
                    title={preview.source.warning}
                  />
                )}
                {!preview.source.current && (
                  <p role="alert">来源已过期，请先核对当前租约或房源资料。</p>
                )}
                {preview.previous.address &&
                  preview.values.address &&
                  preview.previous.address !== preview.values.address && (
                    <Alert
                      type="warning"
                      title="这次来源的地址与已保存住处不同。接入后，原有供应商、报修、服务与附件仍保持原记录，请另外核对是否适用于新住处。"
                    />
                  )}
                <div className="living-source-fields">
                  {fields.map((key) => (
                    <div className="living-source-field" key={key}>
                      <Checkbox
                        aria-label={`接入 ${labels[key as keyof LivingProfile] || key}`}
                        checked={selected.includes(key)}
                        disabled={action.busy || !preview.source?.current}
                        onChange={(event) => {
                          setActual(false);
                          setSelected((keys) =>
                            event.target.checked
                              ? [...keys, key]
                              : keys.filter((item) => item !== key),
                          );
                        }}
                      >
                        {labels[key as keyof LivingProfile] || key}
                      </Checkbox>
                      <div>
                        <span>已保存</span>
                        <p>
                          {display(
                            preview.previous[key as keyof LivingProfile],
                          )}
                        </p>
                      </div>
                      <div>
                        <span>来源资料</span>
                        <p>
                          {display(preview.values[key as keyof LivingProfile])}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                {!fields.length && (
                  <p className="muted">来源没有可接入的非空字段。</p>
                )}
                <Checkbox
                  checked={actual}
                  disabled={action.busy || !preview.source.current}
                  onChange={(event) => setActual(event.target.checked)}
                >
                  我确认这些资料对应我的实际租约。
                </Checkbox>
                <p className="living-note">
                  草稿或复核结果不代表租约已签订。只接入勾选的资料，缺失值不会清空现有资料。
                </p>
              </>
            )}
          </>
        )}
      </Modal>
    </section>
  );
}
