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
import { useCase } from "../../app/context";
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
} from "./leaseFields";
import LeaseAddressFields, { addressGroups } from "./LeaseAddressFields";
import { applyLeaseChange, leaseDurations } from "./leaseTerm";
import { housingCopy } from "../real-data/listingPresentation";

const sections: { title: string; fields: (keyof LeaseFields)[] }[] = [
  {
    title: "房屋信息",
    fields: ["rental_mode", "address", "max_occupants", "inclusions"],
  },
  {
    title: "租赁双方",
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
    title: "租期与租金",
    fields: [
      "lease_type",
      "lease_term_months",
      "start_date",
      "end_date",
      "rent_amount",
      "rent_period",
      "bond",
    ],
  },
  {
    title: "付款信息",
    fields: [
      "payment_method",
      "first_rent_date",
      "rent_due_day",
      "payment_details",
    ],
  },
];
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
  return Object.fromEntries(
    Object.keys(defaults).map((key) => [
      key,
      (key.endsWith("_date") && fields[key as keyof LeaseFields] === ""
        ? null
        : fields[key as keyof LeaseFields]) ??
        (typeof defaults[key as keyof LeaseFields] === "string" ? "" : null),
    ]),
  ) as unknown as LeaseFields;
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
  const sourceKey = JSON.stringify([
    current.selection,
    current.draft.revision,
    current.draft.fingerprint,
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
        getLeaseContext(current.case_id),
        listLeaseDrafts(current.case_id),
      ]);
      if (token !== generation.current) return;
      if (list.status === "fulfilled") setItems(list.value.items);
      else setError(list.reason);
      if (source.status === "fulfilled") {
        setContext(source.value);

        setDirty(false);
        const latest =
          list.status === "fulfilled"
            ? list.value.items.find(
                (v) => v.context_token === source.value.context_token,
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
      } else setError(source.reason);
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
      message.success(`租约草稿 v${d.version} 已保存，签字栏保持空白。`);
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
          onEdited={() => {
            setDirty(true);
            action.clear();
          }}
        />
      );
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
          placeholder="待确认"
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
            ? "按自然月 / 年顺延至同日；月末落到目标月最后一天。"
            : key === "end_date" && fields?.lease_term_months != null
              ? "已根据租期和起租日期自动计算。"
              : !saved && context?.prefill_sources[key]
                ? housingCopy(context.prefill_sources[key]!)
                : undefined
        }
        rules={
          key === "rental_mode"
            ? [{ required: true, message: "请先确认适用新州普通整租住宅。" }]
            : key === "end_date"
              ? [
                  {
                    validator: (_, value) => {
                      const start = form.getFieldValue("start_date");
                      return value && start && value <= start
                        ? Promise.reject(new Error("结束日期须晚于起租日期。"))
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
          <h2>准备一份租约草稿</h2>
          <p className="muted">
            填写信息 → 核对确认 → 预览并下载合同。未知项可以先留空。
          </p>
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
            查看官方模板 ↗
          </a>
          <Button
            onClick={() => setRevision((v) => v + 1)}
            disabled={action.busy || readAction.busy}
          >
            重新读取
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
          <span>正在读取房源与草稿…</span>
        </div>
      ) : (
        <>
          {items.length > 0 && (
            <section className="lease-version-bar">
              <Select
                aria-label="草稿版本"
                virtual={false}
                value={saved ? `${saved.draft_id}:${saved.version}` : undefined}
                placeholder="查看已保存草稿"
                options={items.flatMap((item, index) =>
                  Array.from({ length: item.version }, (_, i) => ({
                    value: `${item.draft_id}:${item.version - i}`,
                    label: `草稿 ${items.length - index} · v${item.version - i}${item.source_current ? "" : " · 历史房源/需求"}`,
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
                  新建当前候选草稿
                </Button>
              )}
              {saved && (
                <Tag color="blue">
                  未签署草稿 v{saved.version}
                  {dirty ? " · 有未保存修改" : ""}
                </Tag>
              )}
            </section>
          )}
          {!context && !saved ? (
            <Blank
              text="先保存一套房源候选，再准备租约草稿。"
              action={
                <Button onClick={() => go("recommendations")}>
                  前往房源推荐
                </Button>
              }
            />
          ) : (
            <>
              {readOnly && (
                <Alert
                  type="warning"
                  showIcon
                  title="正在查看历史版本"
                  description="这份草稿保留原来的房源与信息，可以下载；请新建当前候选草稿后继续修改。"
                />
              )}
              {context && !readOnly && (
                <Collapse
                  key={context.context_token}
                  className="lease-ai-support"
                  items={[
                    {
                      key: "ai",
                      label: "AI 辅助填写（可选）",
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
                requiredMark={false}
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
                  <h2>直接填写合同信息</h2>
                  <span className="muted small">
                    金额均为 AUD；房源标价仅作参考，不自动填作已商定租金。
                  </span>
                </div>
                <p className="muted small">
                  房屋地址取自所选房源。双方接收通知的地址请分别填写，区域、State和邮编可搜索选择，也可手动填写。
                </p>
                {context && (
                  <div className="lease-source-note">
                    当前房源：
                    {String(
                      context.sources.selection.listing_snapshot.address,
                    )}{" "}
                    · 房源 AUD{" "}
                    {String(
                      context.sources.selection.listing_snapshot.weekly_rent,
                    )}
                    /周
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
                      label: "代理信息（如适用）",
                      children: (
                        <div className="lease-fields-grid">
                          {extra.map(renderField)}
                        </div>
                      ),
                    },
                    {
                      key: "signing",
                      label: "签约信息（可选）",
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
                      label: "补充出租方信息（如适用）",
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
                      label: "紧急维修联系人（可选）",
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
                    <strong>还有 {missing.length} 项核心信息待补充</strong>
                    <p>{missing.map((k) => leaseLabels[k]).join("、")}</p>
                    <span className="muted small">
                      可以先保存未完成草稿；导出的文件会列出这些待确认项。
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
                    核对并填入合同
                  </Button>
                  {saved && (
                    <Button
                      onClick={() => setPreview(saved)}
                      disabled={action.busy || readAction.busy}
                    >
                      预览已保存 v{saved.version} 合同
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
                      下载已保存 v{saved.version} PDF
                    </a>
                  )}
                </div>
                {saved && dirty && (
                  <p className="lease-unsaved-note" role="status">
                    表单有未保存修改，预览和下载仍为已保存的 v{saved.version}。
                  </p>
                )}
                <p className="muted small">
                  标准条款保留在官方表单中。紧急维修、账单、送达通知及相关附件仍须由双方完善；生成草稿不会代替对方确认或签字。
                </p>
              </Form>
            </>
          )}
        </>
      )}
      <Modal
        title="确认保存租约草稿"
        open={confirm}
        onCancel={() => {
          if (!action.busy) setConfirm(false);
        }}
        onOk={save}
        okText="确认保存未签署草稿"
        cancelText="返回修改"
        confirmLoading={action.busy}
        okButtonProps={{ disabled: !applicable }}
        width={680}
        styles={{ body: { maxHeight: "65vh", overflowY: "auto" } }}
      >
        <p>以下信息将填写到官方表单；缺失内容保持空白，签字栏不填写。</p>
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
            title={`还有 ${missingLeaseFields(reviewFields).length} 项核心信息未填写，将标为待确认。`}
          />
        )}
        <Checkbox
          checked={applicable}
          onChange={(e) => setApplicable(e.target.checked)}
        >
          我确认这是新州普通整租住宅的拟定信息，理解草稿尚未经双方签署。
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
