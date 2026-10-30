import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Checkbox, Modal, Space, Spin } from "antd";
import { getTenancySource, importTenancySource } from "../../api/living";
import type {
  LivingProfile,
  LivingRecord,
  TenancyPreview,
} from "../../api/living";
import { newRequestId } from "../../api/client";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";
const labels: Partial<Record<keyof LivingProfile, string>> = {
  address: "Home address",
  agent_name: "Agent or landlord name",
  agent_email: "Contact email",
  agent_phone: "Contact phone",
  lease_start_date: "Lease start date",
  lease_end_date: "Lease end date",
  carpeted: "Has carpet",
};
const sourceLabel = (
  label: string | undefined,
  version: number | undefined,
) => {
  const title = label || "Lease details";
  return version && !/\bv\d+\b/i.test(title) ? `${title} · v${version}` : title;
};
const nonempty = (value: unknown) =>
  value !== null &&
  value !== undefined &&
  (typeof value !== "string" || value.trim() !== "");
const display = (value: unknown) =>
  value === true
    ? "Yes"
    : value === false
      ? "No"
      : nonempty(value)
        ? String(value)
        : "Not entered";
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
    [error, setError] = useState<unknown>(null);
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
      if (token === generation.current) setError(error);
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
      title: "Import these actual lease details?",
      content: (
        <>
          <p>
            Only selected non-empty fields are updated. Existing providers,
            repairs, service records, and attachments are preserved.
          </p>
          <ul>
            {fields.map((key) => (
              <li key={key}>
                {labels[key as keyof LivingProfile] || key}:
                {display(source.values[key as keyof LivingProfile])}
              </li>
            ))}
          </ul>
        </>
      ),
      okText: "Confirm lease import",
      cancelText: "Continue checking",
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
        <strong>Lease and living details</strong>
        {record.tenancy_source && (
          <p>{`Imported: ${sourceLabel(record.tenancy_source.label, record.tenancy_source.version)}`}</p>
        )}
      </div>
      <Button disabled={busy || action.busy} onClick={() => void read()}>
        View lease source
      </Button>
      <Modal
        title="Check lease source"
        open={open}
        onCancel={() => !action.busy && setOpen(false)}
        onOk={confirm}
        okText="Import selected details"
        cancelText="Cancel"
        confirmLoading={action.busy}
        okButtonProps={{
          disabled:
            loading || !actual || !preview?.source?.current || !selected.length,
          "aria-label": "Import selected details",
        }}
        cancelButtonProps={{ disabled: action.busy, "aria-label": "Cancel" }}
        closable={!action.busy}
        mask={{ closable: !action.busy }}
        width={680}
      >
        {loading ? (
          <div className="living-loading">
            <Spin />
            <span>Loading lease source…</span>
          </div>
        ) : (
          <>
            {Boolean(error || action.error) && (
              <>
                <Failure error={error || action.error} />
                <Space>
                  {Boolean(action.error) && (
                    <Button
                      loading={action.busy}
                      onClick={() => void action.retry()}
                    >
                      Retry original import
                    </Button>
                  )}
                  <Button disabled={action.busy} onClick={() => void read()}>
                    Preview again
                  </Button>
                </Space>
              </>
            )}
            {!preview?.source ? (
              <p className="muted">
                No lease details are available to import. A lease draft or
                contract review does not prove actual occupancy.
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
                  <p role="alert">
                    The source is outdated. Check the current lease or property
                    details first.
                  </p>
                )}
                {preview.previous.address &&
                  preview.values.address &&
                  preview.previous.address !== preview.values.address && (
                    <Alert
                      type="warning"
                      title="This source address differs from your saved home. Importing preserves existing provider, repair, service, and attachment records. Check separately whether they apply to the new home."
                    />
                  )}
                <div className="living-source-fields">
                  {fields.map((key) => (
                    <div className="living-source-field" key={key}>
                      <Checkbox
                        aria-label={`Import ${labels[key as keyof LivingProfile] || key}`}
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
                        <span>Saved</span>
                        <p>
                          {display(
                            preview.previous[key as keyof LivingProfile],
                          )}
                        </p>
                      </div>
                      <div>
                        <span>Source information</span>
                        <p>
                          {display(preview.values[key as keyof LivingProfile])}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                {!fields.length && (
                  <p className="muted">
                    The source has no non-empty fields available to import.
                  </p>
                )}
                <Checkbox
                  checked={actual}
                  disabled={action.busy || !preview.source.current}
                  onChange={(event) => setActual(event.target.checked)}
                >
                  I confirm these details correspond to my actual lease.
                </Checkbox>
                <p className="living-note">
                  A draft or review does not establish that a lease is signed.
                  Only selected fields are imported; missing values do not clear
                  existing information.
                </p>
              </>
            )}
          </>
        )}
      </Modal>
    </section>
  );
}
