import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Tabs,
} from "antd";
import { useCase } from "../app/context";
import { api, downloadUrl, newRequestId, post } from "../api/client";
import type { AftercareCase, Dict } from "../api/types";
import {
  EvidenceDrawer,
  JsonDetails,
  Loading,
  PageTitle,
  Status,
  text,
} from "../components/Common";
import { useAction } from "../components/useAction";
import TenancyForm from "./TenancyForm";
import AftercarePlan, { CommandRecovery } from "./AftercarePlan";
import AftercareBond from "./AftercareBond";
import AftercareFailure from "./aftercare/AftercareFailure";
import TenancyDetails from "./aftercare/TenancyDetails";
import {
  missingTenancyDetails,
  tenancySource,
  evidenceKind,
  sydneyIso,
  sydneyTime,
  sydneyToday,
  taskTitle,
} from "./aftercare/presentation";
import { useTenancyPrefill } from "./aftercare/prefill";

const decisionNames: Record<string, string> = {
  annotate: "Notes",
  return: "Return for more information",
  hold: "Defer",
  refer: "Refer",
  release: "Release",
};
export default function Aftercare({
  embedded = false,
  initialTab = "plan",
  initialMoveOutDate,
}: {
  embedded?: boolean;
  initialTab?: "plan" | "bond";
  initialMoveOutDate?: string;
}) {
  const { current, refresh, config } = useCase();
  const action = useAction();
  const { message } = App.useApp();
  const [record, setRecord] = useState<AftercareCase | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [tenancyOpen, setTenancyOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pendingOperation, setPendingOperation] = useState("");
  const [evidenceForm] = Form.useForm();
  const prefill = useTenancyPrefill(current.case_id, current.reviews.length);
  const [followDate, setFollowDate] = useState("");
  const [followTime, setFollowTime] = useState("10:00");
  const activeRef = useRef(false);
  activeRef.current = action.busy || refreshing || Boolean(action.error);
  const load = useCallback(async () => {
    if (current.aftercare_case_id) {
      const r = await api<AftercareCase>(
        `/aftercare/cases/${current.aftercare_case_id}`,
      );
      setRecord(r);
      setError(null);
    }
  }, [current.aftercare_case_id]);
  useEffect(() => {
    let valid = true;
    if (current.aftercare_case_id)
      api<AftercareCase>(`/aftercare/cases/${current.aftercare_case_id}`)
        .then((r) => {
          if (valid) setRecord(r);
        })
        .catch((e) => {
          if (valid) setError(e);
        });
    return () => {
      valid = false;
    };
  }, [current.aftercare_case_id]);
  const recordRef = useRef(record);
  recordRef.current = record;
  const send = useCallback(
    (operation: string, payload: Dict) => {
      if (action.busy || refreshing) return Promise.resolve(false);
      setPendingOperation(operation);
      const body = {
        case_id: current.case_id,
        request_id: newRequestId(),
        expected_version: recordRef.current?.version ?? 0,
        operation,
        payload: structuredClone(payload),
      };
      return action.run(async () => {
        await post("/aftercare/commands", body);
        await refresh();
        const id =
          current.aftercare_case_id ??
          (await api<typeof current>(`/cases/${current.case_id}`))
            .aftercare_case_id;
        if (id) {
          setRecord(await api<AftercareCase>(`/aftercare/cases/${id}`));
        }
        if (operation !== "poll_reminders") message.success("Action saved.");
      });
    },
    [current, refresh, action, message, refreshing],
  );
  const pollRef = useRef(send);
  pollRef.current = send;
  useEffect(() => {
    if (!record?.reminders_enabled) return;
    // Show anything that fell due while the page was closed, then keep checking.
    if (!activeRef.current) void pollRef.current("poll_reminders", {});
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible" && !activeRef.current)
        pollRef.current("poll_reminders", {});
    }, 30_000);
    return () => clearInterval(timer);
  }, [record?.reminders_enabled]);
  const refreshCurrent = async () => {
    if (action.busy || refreshing) return;
    setRefreshing(true);
    try {
      await load();
      action.clear();
      setError(null);
      message.success(
        "Latest state loaded. Your input is preserved. Check it and save again.",
      );
    } catch (e) {
      setError(e);
    } finally {
      setRefreshing(false);
    }
  };
  const abandon = () => {
    action.clear();
    setError(null);
    setPendingOperation("");
  };
  const recovery = {
    error: error || action.error,
    busy: action.busy,
    refreshing,
    retry: action.retry,
    refreshCurrent,
    abandon,
  };
  const evidence = (record?.evidence ?? []) as Dict[];
  const reviews = (record?.reviews ?? []) as Dict[];
  const reminders = (record?.reminders ?? []) as Dict[];
  const bondState = String((record?.bond as Dict | null)?.state ?? "");
  const bondActive = ["AwaitingOutcome", "UnderReview"].includes(bondState);
  const savedFollowUp = bondActive
    ? ((record?.bond as Dict).follow_up_at as string | null)
    : null;
  // A follow-up time already in the past cannot be re-saved; keep only future ones.
  const keptFollowUp =
    savedFollowUp && new Date(savedFollowUp) > new Date()
      ? savedFollowUp
      : null;
  const tenancyEditable = Boolean(
    record &&
    (!record.plan || record.plan.state === "Draft") &&
    (!record.bond || record.bond.state === "Draft"),
  );
  const missingTenancy = record ? missingTenancyDetails(record.tenancy) : [];
  const openTenancy = () => {
    abandon();
    setEvidenceOpen(false);
    setTenancyOpen(true);
  };
  const openEvidenceForm = () => {
    evidenceForm.resetFields();
    setFormOpen(true);
  };
  const addEvidence = async () => {
    try {
      const values = await evidenceForm.validateFields();
      const saved = await send("add_evidence", {
        evidence: {
          evidence_id: `evidence-${crypto.randomUUID()}`,
          recorded_at: config.clocks.aftercare,
          ...values,
        },
      });
      if (saved) setFormOpen(false);
    } catch {
      /* Inline validation. */
    }
  };
  return (
    <>
      {!embedded && (
        <PageTitle
          title="Aftercare services"
          description="Confirm lease details, plan your move-out, and preserve facts and evidence at every step."
          extra={
            record ? (
              <Space wrap>
                <span className="revision-label">
                  Case version {record.version}
                </span>
                <Button
                  loading={refreshing}
                  disabled={action.busy}
                  aria-label="Load latest state"
                  onClick={() => void refreshCurrent()}
                >
                  Load latest state
                </Button>
                <a
                  href={downloadUrl(
                    `/aftercare/cases/${record.case_id}/export`,
                  )}
                >
                  Download case JSON
                </a>
              </Space>
            ) : undefined
          }
        />
      )}
      {embedded && record && (
        <Space wrap className="section-actions">
          <Button
            loading={refreshing}
            disabled={action.busy}
            onClick={() => void refreshCurrent()}
          >
            Load latest move-out state
          </Button>
          <a href={downloadUrl(`/aftercare/cases/${record.case_id}/export`)}>
            Download case record
          </a>
        </Space>
      )}
      <AftercareFailure
        error={action.error || error}
        retry={action.retry}
        onResolve={
          tenancyEditable &&
          ["create_plan", "confirm_plan"].includes(pendingOperation)
            ? openTenancy
            : undefined
        }
        resolveLabel="Complete lease details"
      />
      {!record ? (
        current.aftercare_case_id ? (
          error ? (
            <section className="panel">
              <p>
                Unable to load the existing aftercare case. Retry loading the
                current case.
              </p>
              <Button
                loading={refreshing}
                disabled={action.busy}
                aria-label="Load latest state"
                onClick={() => void refreshCurrent()}
              >
                Load latest state
              </Button>
            </section>
          ) : (
            <Loading />
          )
        ) : (
          <TenancyForm
            create={(payload) => send("create", payload)}
            busy={action.busy}
          />
        )
      ) : (
        <>
          <section className="selection-strip">
            <div>
              <span>Confirmed lease details</span>
              <strong>{text(record.tenancy.address)}</strong>
              <p>
                {tenancySource(record.tenancy.source_ref)} · Information version{" "}
                {text(record.tenancy.source_version)}
              </p>
              {missingTenancy.length > 0 && (
                <p className="aftercare-missing">
                  Missing: {missingTenancy.join(", ")}
                </p>
              )}
            </div>
            <Space wrap>
              <Button
                disabled={!tenancyEditable || action.busy || refreshing}
                onClick={openTenancy}
              >
                Complete lease details
              </Button>
              <Button onClick={() => setEvidenceOpen(true)}>
                View details and evidence
              </Button>
            </Space>
          </section>
          <Tabs
            defaultActiveKey={initialTab}
            items={[
              {
                key: "plan",
                label: "Move-out plan and tasks",
                children: (
                  <AftercarePlan
                    key={
                      record.plan
                        ? "plan"
                        : String(prefill?.values.move_out_date?.value ?? "")
                    }
                    initialDate={
                      config.mode === "real_listings"
                        ? initialMoveOutDate ||
                          (prefill?.values.move_out_date?.value as
                            string | undefined) ||
                          config.clocks.aftercare.slice(0, 10)
                        : undefined
                    }
                    missingDetails={missingTenancy}
                    onCompleteTenancy={
                      tenancyEditable ? openTenancy : undefined
                    }
                    plan={(record.plan ?? null) as Dict | null}
                    evidence={evidence}
                    send={send}
                    busy={action.busy}
                    recovery={{
                      ...recovery,
                      error:
                        pendingOperation === "edit_task"
                          ? recovery.error
                          : null,
                    }}
                  />
                ),
              },
              {
                key: "bond",
                label: "Bond follow-up",
                children: (
                  <AftercareBond
                    bond={(record.bond ?? null) as Dict | null}
                    evidence={evidence}
                    send={send}
                    busy={action.busy}
                    recovery={{
                      ...recovery,
                      error: [
                        "activate_bond",
                        "bond_update",
                        "open_bond",
                      ].includes(pendingOperation)
                        ? recovery.error
                        : null,
                    }}
                    clock={String(record.updated_at ?? config.clocks.aftercare)}
                    bondAmount={prefill?.values.bond_amount}
                  />
                ),
              },
              {
                key: "reminders",
                label: "Local reminders",
                children: (
                  <section className="panel">
                    <h2>Optional local reminders</h2>
                    <p className="muted">
                      {config.mode === "real_listings"
                        ? "Off by default. When enabled, the active page checks every 30 seconds. Delivery is not guaranteed after the page closes."
                        : "Off by default. When enabled, the active page checks every 30 seconds. This fixed synthetic replay advances to the sample reminder checkpoint when checked. Delivery is not guaranteed after the page closes."}
                    </p>
                    <Space wrap>
                      <Switch
                        aria-label="Enable local reminders"
                        checked={Boolean(record.reminders_enabled)}
                        disabled={action.busy}
                        onChange={(enabled) =>
                          send("reminder_preferences", {
                            enabled,
                            follow_up_at: enabled ? keptFollowUp : null,
                          })
                        }
                      />
                      <span>
                        {record.reminders_enabled
                          ? "Reminders enabled"
                          : "Reminders disabled"}
                      </span>
                      <Button
                        disabled={!record.reminders_enabled}
                        loading={action.busy}
                        onClick={() => send("poll_reminders", {})}
                        aria-label="Check due reminders"
                      >
                        Check due reminders
                      </Button>
                    </Space>
                    <h3>Bond follow-up reminder</h3>
                    {bondActive ? (
                      <>
                        <p className="muted small">
                          Current reminder time:
                          {savedFollowUp
                            ? sydneyTime(savedFollowUp)
                            : "Not set"}
                          . You choose the date. The system does not calculate
                          legal deadlines.
                        </p>
                        <Space wrap>
                          <Input
                            type="date"
                            aria-label="Bond follow-up reminder date"
                            min={sydneyToday()}
                            value={followDate}
                            onChange={(e) => setFollowDate(e.target.value)}
                          />
                          <Input
                            type="time"
                            aria-label="Bond follow-up reminder time"
                            value={followTime}
                            onChange={(e) => setFollowTime(e.target.value)}
                          />
                          <Button
                            disabled={!followDate || !followTime}
                            loading={action.busy}
                            onClick={() =>
                              send("reminder_preferences", {
                                enabled: true,
                                follow_up_at: sydneyIso(followDate, followTime),
                              })
                            }
                          >
                            Save reminder time (Sydney time)
                          </Button>
                        </Space>
                      </>
                    ) : (
                      <p className="muted small">
                        Once bond follow-up is active, choose a reminder time to
                        check its status.
                      </p>
                    )}
                    <h3>Local inbox</h3>
                    {reminders.filter((r) => r.state === "delivered").length ===
                    0 ? (
                      <p className="muted">No delivered reminders.</p>
                    ) : (
                      reminders
                        .filter((r) => r.state === "delivered")
                        .map((r, i) => (
                          <div className="detail-row" key={i}>
                            <strong>{taskTitle(r.title)}</strong>
                            <p>Due: {sydneyTime(r.due_at)}</p>
                            <small>
                              Reminder at {sydneyTime(r.delivered_at)}
                            </small>
                          </div>
                        ))
                    )}
                    <Collapse
                      ghost
                      items={[
                        {
                          key: "all",
                          label: "View scheduled and suppressed reminders",
                          children: reminders.map((r, i) => (
                            <div className="detail-row" key={i}>
                              <strong>{taskTitle(r.title)}</strong>
                              <p>
                                Due: {sydneyTime(r.due_at)} ·{" "}
                                <Status value={String(r.state)} />
                              </p>
                            </div>
                          )),
                        },
                      ]}
                    />
                  </section>
                ),
              },
              {
                key: "review",
                label: `Review items ${reviews.filter((r) => r.status === "open").length}`,
                children: (
                  <section className="panel">
                    <h2>Human review items</h2>
                    <p className="muted">
                      The local demo operator handles these in a separate view.
                      Tenants cannot release restrictions.
                    </p>
                    {reviews.length === 0 ? (
                      <p>No review items.</p>
                    ) : (
                      reviews.map((r, i) => (
                        <div className="detail-row" key={i}>
                          <Status value={String(r.status)} />
                          <strong>{text(r.reason)}</strong>
                          <p className="small">
                            Submitted at {sydneyTime(r.created_at)}
                          </p>
                          {((r.decisions as Dict[]) ?? []).map((d, j) => (
                            <p className="small" key={j}>
                              {decisionNames[String(d.decision)] ??
                                text(d.decision)}
                              : {text(d.note)}({sydneyTime(d.at)})
                            </p>
                          ))}
                        </div>
                      ))
                    )}
                  </section>
                ),
              },
            ]}
          />
          <Collapse
            items={[
              {
                key: "audit",
                label: "Action history and original case references",
                children: (
                  <JsonDetails
                    value={{
                      case_id: record.case_id,
                      version: record.version,
                      updated_at: record.updated_at,
                      audit: record.audit,
                    }}
                  />
                ),
              },
            ]}
          />
        </>
      )}
      <EvidenceDrawer
        title="Confirmed details and evidence"
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
      >
        {record && (
          <TenancyDetails
            tenancy={record.tenancy}
            evidence={evidence}
            editable={tenancyEditable && !action.busy && !refreshing}
            onEdit={openTenancy}
            onAddEvidence={openEvidenceForm}
          />
        )}
      </EvidenceDrawer>
      <Modal
        title="Complete lease details"
        open={tenancyOpen}
        footer={null}
        width={840}
        destroyOnHidden
        closable={!action.busy && !refreshing}
        mask={{ closable: !action.busy && !refreshing }}
        onCancel={() => {
          if (!action.busy && !refreshing) {
            if (pendingOperation === "revise_tenancy") abandon();
            setTenancyOpen(false);
          }
        }}
      >
        {record && (
          <>
            {!tenancyEditable && (
              <Alert
                type="warning"
                title="The plan is confirmed or bond follow-up is active. Current lease details cannot be edited."
              />
            )}
            <TenancyForm
              tenancy={record.tenancy}
              busy={action.busy}
              disabled={refreshing || !tenancyEditable}
              create={async (payload) => {
                const saved = await send("revise_tenancy", payload);
                if (saved) setTenancyOpen(false);
                return saved;
              }}
              recovery={{
                ...recovery,
                error:
                  pendingOperation === "revise_tenancy" ? recovery.error : null,
                retry: async () => {
                  const saved = await action.retry();
                  if (saved) setTenancyOpen(false);
                  return saved;
                },
              }}
            />
          </>
        )}
      </Modal>
      <Modal
        title={
          config.mode === "real_listings"
            ? "Register information reference"
            : "Register synthetic evidence metadata"
        }
        open={formOpen}
        onCancel={() => {
          if (action.busy || refreshing) return;
          if (pendingOperation === "add_evidence" && recovery.error) abandon();
          setFormOpen(false);
        }}
        confirmLoading={action.busy}
        okButtonProps={{
          "aria-label": "Save evidence reference",
          disabled: refreshing,
        }}
        cancelButtonProps={{ disabled: action.busy || refreshing }}
        closable={!action.busy && !refreshing}
        mask={{ closable: !action.busy && !refreshing }}
        onOk={addEvidence}
        okText="Save evidence reference"
        cancelText={
          pendingOperation === "add_evidence" && recovery.error
            ? "Cancel this edit"
            : "Cancel"
        }
      >
        <CommandRecovery
          {...recovery}
          error={pendingOperation === "add_evidence" ? recovery.error : null}
          retry={async () => {
            const saved = await action.retry();
            if (saved) setFormOpen(false);
            return saved;
          }}
        />
        <Form
          disabled={action.busy || refreshing}
          form={evidenceForm}
          layout="vertical"
          initialValues={{ kind: "other", source_version: 1 }}
        >
          <Form.Item name="kind" label="Evidence type">
            <Select
              options={[
                "photo",
                "receipt",
                "condition_report",
                "deposit_record",
                "inspection_record",
                "correspondence",
                "outcome",
                "other",
              ].map((value) => ({ value, label: evidenceKind(value) }))}
            />
          </Form.Item>
          <Form.Item
            name="source_ref"
            label={
              config.mode === "real_listings"
                ? "Document name or location"
                : "Synthetic source reference"
            }
            rules={[{ required: true }]}
          >
            <Input
              placeholder={
                config.mode === "real_listings"
                  ? "Enter the name or location of your saved documents"
                  : "synthetic://…"
              }
            />
          </Form.Item>
          <Form.Item
            name="source_version"
            label="Source version"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} precision={0} />
          </Form.Item>
          <Form.Item
            name="summary"
            label="Evidence summary"
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
