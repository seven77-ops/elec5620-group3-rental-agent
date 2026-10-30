import { useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
} from "antd";
import { useCase, currentConfirmation } from "../../app/context";
import { downloadUrl, newRequestId } from "../../api/client";
import {
  getLeaseContext,
  getLeaseDraft,
  listLeaseDrafts,
  saveLeaseDraft,
  leaseRoot,
} from "../../api/leaseDraft";
import type {
  LeaseContext,
  LeaseDraft as SavedDraft,
  LeaseFields,
  LeaseSummary,
} from "../../api/leaseDraft";
import { Failure, Blank } from "../../components/Common";
import { useAction } from "../../components/useAction";
import DraftAi from "./DraftAi";
import LeasePdfPreview from "./LeasePdfPreview";
import {
  leaseLabels,
  leaseOptions,
  leaseText,
  missingLeaseFields,
  leaseExtraDefaults,
  applicableLeaseFields,
  applicableLeaseValues,
} from "./leaseFields";
import LeaseAddressFields, { addressGroups } from "./LeaseAddressFields";
import { applyLeaseChange, leaseDurations } from "./leaseTerm";
import { housingCopy } from "../real-data/listingPresentation";

const sections: { title: string; fields: (keyof LeaseFields)[] }[] = [
  {
    title: "Property details",
    fields: ["rental_mode", "address", "max_occupants", "inclusions"],
  },
  {
    title: "Parties",
    fields: [
      "landlord_name",
      "landlord_contact",
      "landlord_notice_address",
      "tenant_names",
      "tenant_contact",
      "tenant_notice_address",
    ],
  },
  {
    title: "Lease term and rent",
    fields: [
      "lease_type",
      "lease_term_months",
      "start_date",
      "end_date",
      "rent_amount",
      "rent_period",
      "bond",
      "bond_recipient",
    ],
  },
  {
    title: "Payment details",
    fields: [
      "payment_method",
      "first_rent_date",
      "rent_due_day",
      "payment_details",
    ],
  },
];
sections.push(
  {
    title: "Charges and property facilities",
    fields: [
      "water_usage",
      "electricity_embedded",
      "gas_embedded",
      "smoke_alarm_type",
      "smoke_battery_replaceable",
      "smoke_battery_type",
      "smoke_backup_replaceable",
      "smoke_backup_type",
      "strata_bylaws",
      "smoke_strata_responsible",
    ],
  },
  {
    title: "Electronic service of notices",
    fields: [
      "landlord_email_consent",
      "landlord_notice_email",
      "tenant_email_consent",
      "tenant_notice_email",
    ],
  },
);
const extra: (keyof LeaseFields)[] = [
  "agent_name",
  "agent_contact",
  "agent_notice_address",
];
const monetary = new Set<keyof LeaseFields>([
  "rent_amount",
  "bond",
  "max_occupants",
]);
function clean(fields: LeaseFields, defaults: LeaseFields): LeaseFields {
  defaults = { ...leaseExtraDefaults, ...defaults };
  return applicableLeaseValues(
    Object.fromEntries(
      Object.keys(defaults).map((key) => [
        key,
        (key.endsWith("_date") && fields[key as keyof LeaseFields] === ""
          ? null
          : fields[key as keyof LeaseFields]) ??
          (typeof defaults[key as keyof LeaseFields] === "string" ? "" : null),
      ]),
    ) as unknown as LeaseFields,
  );
}
export default function LeaseDraft() {
  const { current, go } = useCase();
  const { message } = App.useApp();
  const [form] = Form.useForm<LeaseFields>();
  const [context, setContext] = useState<LeaseContext | null>(null);
  const [items, setItems] = useState<LeaseSummary[]>([]);
  const [saved, setSaved] = useState<SavedDraft | null>(null);
  const [preview, setPreview] = useState<SavedDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [revision, setRevision] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [applicable, setApplicable] = useState(false);
  const [reviewFields, setReviewFields] = useState<LeaseFields | null>(null);
  const action = useAction();
  const readAction = useAction();
  const generation = useRef(0);
  const watched = Form.useWatch([], { form, preserve: true });
  const confirmed = currentConfirmation(current);
  const prerequisite = !confirmed
    ? {
        title: "Confirm your rental needs first",
        action: "My rental needs",
        target: "assistant?needs=1",
      }
    : !current.selection
      ? {
          title: "Save a property candidate first",
          action: "Go to housing recommendations",
          target: "recommendations",
        }
      : null;
  const sourceKey = JSON.stringify([
    current.selection,
    current.draft.revision,
    current.draft.fingerprint,
    confirmed?.version,
  ]);
  useEffect(() => {
    const token = ++generation.current;
    setLoading(true);
    setError(null);
    setContext(null);
    setSaved(null);
    setPreview(null);
    setConfirm(false);
    action.clear();
    void (async () => {
      const [source, list] = await Promise.allSettled([
        prerequisite ? Promise.resolve(null) : getLeaseContext(current.case_id),
        listLeaseDrafts(current.case_id),
      ]);
      if (token !== generation.current) return;
      if (list.status === "fulfilled") setItems(list.value.items);
      else setError(list.reason);
      if (source.status === "fulfilled" && source.value) {
        setContext(source.value);

        setDirty(false);
        const latest =
          list.status === "fulfilled"
            ? list.value.items.find(
                (v) => v.context_token === source.value?.context_token,
              )
            : undefined;
        if (latest) {
          try {
            const d = await getLeaseDraft(
              current.case_id,
              latest.draft_id,
              latest.version,
            );
            if (token === generation.current) {
              setSaved(d);
            }
          } catch (e) {
            if (token === generation.current) setError(e);
          }
        }
      } else if (source.status === "rejected") setError(source.reason);
      if (token === generation.current) setLoading(false);
    })();
    return () => {
      generation.current++;
    };
  }, [current.case_id, sourceKey, form, revision]);
  useEffect(() => {
    if (!loading && (saved || context)) {
      form.resetFields();
      form.setFieldsValue(
        saved
          ? clean(saved.fields, context?.defaults ?? saved.fields)
          : context!.defaults,
      );
    }
    // Loading/reloading establishes a new source snapshot; ordinary field edits
    // and version selections must not rerun this initialization.
  }, [loading, context?.context_token, form]);
  const latest = saved
    ? items.find((i) => i.draft_id === saved.draft_id)
    : undefined;
  const readOnly = Boolean(
    saved &&
    (!context ||
      saved.context_token !== context.context_token ||
      saved.version !== latest?.version),
  );
  const fields = context
    ? clean(
        { ...context.defaults, ...watched } as LeaseFields,
        context.defaults,
      )
    : saved?.fields;
  const missing = fields ? missingLeaseFields(fields) : [];
  const required = fields ? applicableLeaseFields(fields) : [];
  const choose = (reference: string) => {
    const [id, v] = reference.split(":");
    const token = generation.current;
    void readAction.run(async () => {
      const d = await getLeaseDraft(current.case_id, id, Number(v));
      if (token !== generation.current) return;
      setSaved(d);
      setPreview(null);
      form.setFieldsValue(clean(d.fields, context?.defaults ?? d.fields));
      setDirty(false);
      action.clear();
    });
  };
  const newDraft = () => {
    if (context) {
      setSaved(null);
      setPreview(null);
      form.resetFields();
      form.setFieldsValue(context.defaults);
      setDirty(false);
      action.clear();
    }
  };
  const prepare = async () => {
    try {
      await form.validateFields();
      if (context) {
        setReviewFields(clean(form.getFieldsValue(true), context.defaults));
        setApplicable(false);
        setConfirm(true);
      }
    } catch {
      /* inline validation */
    }
  };
  const save = () => {
    if (!context || !reviewFields || !applicable) return;
    const token = generation.current;
    const body = {
      request_id: newRequestId(),
      context_token: context.context_token,
      expected_version: saved?.version ?? 0,
      ...(saved ? { draft_id: saved.draft_id } : {}),
      confirmed: true as const,
      applicability_confirmed: true as const,
      fields: reviewFields,
    };
    void action.run(async () => {
      const d = await saveLeaseDraft(current.case_id, body);
      if (token !== generation.current) return;
      setSaved(d);
      setDirty(false);
      setConfirm(false);
      setPreview(d);
      const list = await listLeaseDrafts(current.case_id);
      if (token === generation.current) setItems(list.items);
      message.success(
        `Lease draft v${d.version} saved. Signature fields remain blank.`,
      );
    });
  };
  const renderField = (key: keyof LeaseFields) => {
    if (Object.hasOwn(addressGroups, key))
      return (
        <LeaseAddressFields
          key={`${key}:${saved?.draft_id ?? "new"}:${saved?.version ?? 0}:${context?.context_token}`}
          name={key as keyof typeof addressGroups}
          form={form}
          source={
            !saved && context?.prefill_sources[key]
              ? housingCopy(context.prefill_sources[key]!)
              : undefined
          }
          requiredFields={required}
          onEdited={() => {
            setDirty(true);
            action.clear();
          }}
        />
      );
    if (
      (key === "smoke_battery_replaceable" || key === "smoke_battery_type") &&
      !["battery", "both"].includes(fields?.smoke_alarm_type ?? "")
    )
      return null;
    if (
      key === "smoke_battery_type" &&
      fields?.smoke_battery_replaceable !== "yes"
    )
      return null;
    if (
      (key === "smoke_backup_replaceable" || key === "smoke_backup_type") &&
      !["hardwired", "both"].includes(fields?.smoke_alarm_type ?? "")
    )
      return null;
    if (
      key === "smoke_backup_type" &&
      fields?.smoke_backup_replaceable !== "yes"
    )
      return null;
    if (key === "smoke_strata_responsible" && fields?.strata_bylaws !== "yes")
      return null;
    if (
      key === "landlord_notice_email" &&
      fields?.landlord_email_consent !== "yes"
    )
      return null;
    if (key === "tenant_notice_email" && fields?.tenant_email_consent !== "yes")
      return null;
    if (key === "lease_term_months" && fields?.lease_type !== "fixed")
      return null;
    let input;
    if (key === "lease_term_months")
      input = <Select virtual={false} options={leaseDurations} />;
    else if (leaseOptions[key])
      input = (
        <Select
          virtual={false}
          allowClear
          placeholder="To be confirmed"
          options={leaseOptions[key]}
        />
      );
    else if (monetary.has(key))
      input = (
        <InputNumber
          min={key === "bond" ? 0 : key === "max_occupants" ? 1 : 0.01}
          max={key === "max_occupants" ? 30 : 999999}
          precision={key === "max_occupants" ? 0 : 2}
        />
      );
    else if (key.endsWith("_date"))
      input = (
        <Input
          type="date"
          disabled={
            key === "end_date" &&
            (fields?.lease_type === "periodic" ||
              fields?.lease_term_months != null)
          }
        />
      );
    else if (
      key === "tenant_names" ||
      key === "payment_details" ||
      key === "inclusions"
    )
      input = (
        <Input.TextArea rows={key === "tenant_names" ? 2 : 3} maxLength={400} />
      );
    else input = <Input maxLength={key === "rent_due_day" ? 30 : 200} />;
    return (
      <Form.Item
        key={key}
        name={key}
        label={leaseLabels[key]}
        required={required.includes(key)}
        getValueProps={
          key === "lease_term_months"
            ? (value) => ({ value: value == null ? "custom" : String(value) })
            : undefined
        }
        getValueFromEvent={
          key === "lease_term_months"
            ? (value) => (value === "custom" ? null : Number(value))
            : undefined
        }
        dependencies={
          key === "end_date" ? ["start_date", "lease_type"] : undefined
        }
        className={
          key === "address" ||
          key === "tenant_names" ||
          key === "landlord_notice_address"
            ? "lease-field-wide"
            : ""
        }
        extra={
          key === "lease_term_months"
            ? "Advances by calendar months / years to the same day, or the last day of the target month."
            : key === "end_date" && fields?.lease_term_months != null
              ? "Calculated from the lease duration and start date."
              : !saved && context?.prefill_sources[key]
                ? housingCopy(context.prefill_sources[key]!)
                : undefined
        }
        rules={
          key === "rental_mode"
            ? [
                {
                  required: true,
                  message:
                    "Confirm that this is a standard NSW whole-property residential tenancy first.",
                },
              ]
            : key === "end_date"
              ? [
                  {
                    validator: (_, value) => {
                      const start = form.getFieldValue("start_date");
                      return value && start && value <= start
                        ? Promise.reject(
                            new Error(
                              "The end date must be after the start date.",
                            ),
                          )
                        : Promise.resolve();
                    },
                  },
                ]
              : undefined
        }
      >
        {input}
      </Form.Item>
    );
  };
  return (
    <div className="lease-draft-workspace">
      <section className="panel lease-draft-intro">
        <div>
          <h2>Prepare a lease draft</h2>
        </div>
        <Space wrap>
          <a
            href={
              context?.template.source_page ??
              saved?.template.source_page ??
              "https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/resources/standard-residential-tenancy-agreement"
            }
            target="_blank"
            rel="noopener noreferrer"
          >
            View official template ↗
          </a>
          <Button
            onClick={() => setRevision((v) => v + 1)}
            disabled={action.busy || readAction.busy}
          >
            Reload
          </Button>
        </Space>
      </section>
      <Failure
        error={error || action.error || readAction.error}
        retry={
          error
            ? () => setRevision((v) => v + 1)
            : action.error
              ? action.retry
              : readAction.retry
        }
      />
      {loading ? (
        <div className="lease-loading">
          <Spin />
          <span>Loading property and draft…</span>
        </div>
      ) : (
        <>
          {items.length > 0 && (
            <section className="lease-version-bar">
              <Select
                aria-label="Draft version"
                virtual={false}
                value={saved ? `${saved.draft_id}:${saved.version}` : undefined}
                placeholder="View saved drafts"
                options={items.flatMap((item, index) =>
                  Array.from({ length: item.version }, (_, i) => ({
                    value: `${item.draft_id}:${item.version - i}`,
                    label: `Draft ${items.length - index} · v${item.version - i}${item.source_current ? "" : " · Historical property/needs"}`,
                  })),
                )}
                onChange={choose}
                disabled={action.busy || readAction.busy}
              />
              {context && (
                <Button
                  onClick={newDraft}
                  disabled={action.busy || readAction.busy}
                >
                  New draft for current candidate
                </Button>
              )}
              {saved && (
                <Tag color="blue">
                  Unsigned draft v{saved.version}
                  {dirty ? " · Unsaved changes" : ""}
                </Tag>
              )}
            </section>
          )}
          {!context && !saved ? (
            <Blank
              text={
                prerequisite?.title ?? "Select a property again to continue."
              }
              action={
                <Button
                  onClick={() => go(prerequisite?.target ?? "recommendations")}
                >
                  {prerequisite?.action ?? "Go to housing recommendations"}
                </Button>
              }
            />
          ) : (
            <>
              {readOnly && (
                <Alert
                  type="warning"
                  showIcon
                  title="Viewing a historical version"
                  description="This draft retains its original property and details and can be downloaded. Create a draft for the current candidate to continue editing."
                />
              )}
              {context && !readOnly && (
                <Collapse
                  key={context.context_token}
                  className="lease-ai-support"
                  items={[
                    {
                      key: "ai",
                      label: "AI-assisted entry (optional)",
                      children: (
                        <DraftAi
                          context={context}
                          fields={fields!}
                          disabled={action.busy || readAction.busy}
                          onApply={(patch) => {
                            form.setFieldsValue(
                              applyLeaseChange(
                                form.getFieldsValue(true),
                                patch,
                              ),
                            );
                            setDirty(true);
                            action.clear();
                          }}
                        />
                      ),
                    },
                  ]}
                />
              )}
              <Form
                form={form}
                key={`form:${context?.context_token ?? saved?.draft_id}`}
                initialValues={
                  saved
                    ? clean(saved.fields, context?.defaults ?? saved.fields)
                    : context?.defaults
                }
                layout="vertical"
                requiredMark
                disabled={action.busy || readAction.busy || readOnly}
                onValuesChange={(changes, values) => {
                  form.setFieldsValue(
                    applyLeaseChange(
                      { ...values, lease_type: fields?.lease_type },
                      changes,
                    ),
                  );
                  setDirty(true);
                  action.clear();
                }}
                className="panel lease-fields-panel"
              >
                <div className="lease-form-heading">
                  <h2>Enter contract details directly</h2>
                  <span className="muted small">
                    All amounts are AUD. The listing price is a reference only
                    and is not automatically entered as agreed rent.
                  </span>
                </div>
                <p className="muted small">
                  Fields marked * are required for a complete draft. Save an
                  incomplete draft while details are unconfirmed. Enter separate
                  notice addresses for both parties. Suburb, state, and postcode
                  can be searched or entered manually.
                </p>
                {context && (
                  <div className="lease-source-note">
                    Current property:
                    {String(
                      context.sources.selection.listing_snapshot.address,
                    )}{" "}
                    · Listing AUD{" "}
                    {String(
                      context.sources.selection.listing_snapshot.weekly_rent,
                    )}
                    /week
                  </div>
                )}
                {sections.map((section, index) => (
                  <section className="lease-form-section" key={section.title}>
                    <h3>
                      <span aria-hidden="true">{index + 1}</span>
                      {section.title}
                    </h3>
                    <div className="lease-fields-grid">
                      {section.fields.map(renderField)}
                    </div>
                  </section>
                ))}
                <Collapse
                  items={[
                    {
                      key: "details",
                      label: "Landlord agent (if applicable)",
                      children: (
                        <>
                          <p className="muted small">
                            The agent who lets or manages the property for the
                            landlord is entered in the PDF as Landlord’s agent.
                            Enter any agent appointed by the tenant in the next
                            section.
                          </p>
                          <div className="lease-fields-grid">
                            {extra.map(renderField)}
                          </div>
                        </>
                      ),
                    },
                    {
                      key: "tenant-agent",
                      label: "Tenant agent (if applicable)",
                      children: (
                        <>
                          <p className="muted small">
                            Only enter an agent who represents the tenant for
                            this lease. This is entered in the PDF as Tenant’s
                            agent and recorded separately from the landlord
                            agent.
                          </p>
                          <div className="lease-fields-grid">
                            {(
                              [
                                "tenant_agent_name",
                                "tenant_agent_contact",
                                "tenant_agent_notice_address",
                              ] as const
                            ).map(renderField)}
                          </div>
                        </>
                      ),
                    },
                    {
                      key: "corporation",
                      label: "Corporate landlord (if applicable)",
                      children: (
                        <div className="lease-fields-grid">
                          {(
                            ["corporation_name", "corporation_address"] as const
                          ).map(renderField)}
                        </div>
                      ),
                    },
                    {
                      key: "signing",
                      label: "Signing details (optional)",
                      children: (
                        <div className="lease-fields-grid">
                          {(["agreement_date", "agreement_place"] as const).map(
                            renderField,
                          )}
                        </div>
                      ),
                    },
                    {
                      key: "owners",
                      label: "Additional landlord details (if applicable)",
                      children: (
                        <div className="lease-fields-grid">
                          {(
                            [
                              "landlord_name_2",
                              "landlord_residence",
                              "landlord_phone",
                            ] as const
                          ).map(renderField)}
                        </div>
                      ),
                    },
                    {
                      key: "repairs",
                      label:
                        "Emergency repair contacts (to be confirmed by both parties)",
                      children: (
                        <div className="lease-fields-grid">
                          {(
                            [
                              "electrical_repair_name",
                              "electrical_repair_phone",
                              "plumbing_repair_name",
                              "plumbing_repair_phone",
                              "other_repair_name",
                              "other_repair_phone",
                            ] as const
                          ).map(renderField)}
                        </div>
                      ),
                    },
                  ]}
                />
                {missing.length > 0 && (
                  <div className="lease-missing" data-testid="lease-missing">
                    <strong>
                      Complete draft still needs {missing.length} items
                    </strong>
                    <p>{missing.map((k) => leaseLabels[k]).join(", ")}</p>
                    <span className="muted small">
                      You can save an incomplete draft. Exported files will list
                      these unconfirmed items.
                    </span>
                  </div>
                )}
                <div className="lease-save-actions">
                  <Button
                    type="primary"
                    onClick={() => void prepare()}
                    loading={action.busy}
                    disabled={readOnly || !context || readAction.busy}
                  >
                    Check and fill contract
                  </Button>
                  {saved && (
                    <Button
                      onClick={() => setPreview(saved)}
                      disabled={action.busy || readAction.busy}
                    >
                      Preview saved v{saved.version} contract
                    </Button>
                  )}
                  {saved && (
                    <a
                      className="ant-btn ant-btn-default"
                      href={downloadUrl(
                        leaseRoot(current.case_id) +
                          `/${saved.draft_id}/pdf?version=${saved.version}`,
                      )}
                    >
                      Download saved v{saved.version} PDF
                    </a>
                  )}
                </div>
                {saved && dirty && (
                  <p className="lease-unsaved-note" role="status">
                    The form has unsaved changes. Preview and download still use
                    saved v{saved.version}.
                  </p>
                )}
                <p className="muted small">
                  Standard terms remain in the official form. Both parties
                  should check the completed details and attachments. Generating
                  a draft does not replace their confirmation or signatures.
                </p>
              </Form>
            </>
          )}
        </>
      )}
      <Modal
        title="Confirm lease draft save"
        open={confirm}
        onCancel={() => {
          if (!action.busy) setConfirm(false);
        }}
        onOk={save}
        okText="Confirm and save unsigned draft"
        cancelText="Return to editing"
        confirmLoading={action.busy}
        okButtonProps={{ disabled: !applicable }}
        width={680}
        styles={{ body: { maxHeight: "65vh", overflowY: "auto" } }}
      >
        <p>
          The following details will be entered in the official form. Missing
          items and signature fields remain blank.
        </p>
        <Failure error={action.error} retry={action.retry} />
        <Descriptions
          column={1}
          size="small"
          items={
            reviewFields
              ? Object.entries(reviewFields)
                  .filter(([, v]) => v != null && v !== "")
                  .map(([key, value]) => ({
                    key,
                    label: leaseLabels[key as keyof LeaseFields],
                    children: leaseText(key as keyof LeaseFields, value),
                  }))
              : []
          }
        />
        {reviewFields && missingLeaseFields(reviewFields).length > 0 && (
          <Alert
            type="info"
            showIcon
            title={`There are ${missingLeaseFields(reviewFields).length}  incomplete items for a complete draft. They will be marked unconfirmed.`}
          />
        )}
        <Checkbox
          checked={applicable}
          onChange={(e) => setApplicable(e.target.checked)}
        >
          I confirm these proposed details are for a standard NSW whole-property
          residential tenancy and understand the draft is not signed by either
          party.
        </Checkbox>
      </Modal>
      {preview && (
        <LeasePdfPreview
          key={`${preview.case_id}:${preview.draft_id}:${preview.version}`}
          draft={preview}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
