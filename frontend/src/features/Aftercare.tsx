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
  annotate: "备注",
  return: "退回补充",
  hold: "暂缓",
  refer: "转介",
  release: "放行",
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
        if (operation !== "poll_reminders") message.success("操作已保存。");
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
      message.success("已读取最新状态，当前输入已保留，请核对后重新保存。");
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
    savedFollowUp && new Date(savedFollowUp) > new Date() ? savedFollowUp : null;
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
          title="租后服务"
          description="确认租约资料，安排退租事项，保留每一步的事实与证据。"
          extra={
            record ? (
              <Space wrap>
                <span className="revision-label">
                  案件版本 {record.version}
                </span>
                <Button
                  loading={refreshing}
                  disabled={action.busy}
                  aria-label="读取最新状态"
                  onClick={() => void refreshCurrent()}
                >
                  读取最新状态
                </Button>
                <a
                  href={downloadUrl(
                    `/aftercare/cases/${record.case_id}/export`,
                  )}
                >
                  下载案件 JSON
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
            读取最新退租状态
          </Button>
          <a href={downloadUrl(`/aftercare/cases/${record.case_id}/export`)}>
            下载案件记录
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
        resolveLabel="补充租约资料"
      />
      {!record ? (
        current.aftercare_case_id ? (
          error ? (
            <section className="panel">
              <p>已有租后案件暂时无法读取，请重试读取当前案件。</p>
              <Button
                loading={refreshing}
                disabled={action.busy}
                aria-label="读取最新状态"
                onClick={() => void refreshCurrent()}
              >
                读取最新状态
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
              <span>已确认租约资料</span>
              <strong>{text(record.tenancy.address)}</strong>
              <p>
                {tenancySource(record.tenancy.source_ref)} · 资料版本{" "}
                {text(record.tenancy.source_version)}
              </p>
              {missingTenancy.length > 0 && (
                <p className="aftercare-missing">
                  待补充：{missingTenancy.join("、")}
                </p>
              )}
            </div>
            <Space wrap>
              <Button
                disabled={!tenancyEditable || action.busy || refreshing}
                onClick={openTenancy}
              >
                补充租约资料
              </Button>
              <Button onClick={() => setEvidenceOpen(true)}>
                查看资料与证据
              </Button>
            </Space>
          </section>
          <Tabs
            defaultActiveKey={initialTab}
            items={[
              {
                key: "plan",
                label: "退租计划与任务",
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
                            | string
                            | undefined) ||
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
                label: "押金跟进",
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
                label: "本地提醒",
                children: (
                  <section className="panel">
                    <h2>可选本地提醒</h2>
                    <p className="muted">
                      {config.mode === "real_listings"
                        ? "默认关闭，开启后只在活跃页面每30秒查询。页面关闭后不保证提醒投递。"
                        : "默认关闭，开启后只在活跃页面每30秒查询。本次固定合成回放会在查询时推进至样例提醒检查点；页面关闭后不保证投递。"}
                    </p>
                    <Space wrap>
                      <Switch
                        aria-label="开启本地提醒"
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
                        {record.reminders_enabled ? "提醒已开启" : "提醒已关闭"}
                      </span>
                      <Button
                        disabled={!record.reminders_enabled}
                        loading={action.busy}
                        onClick={() => send("poll_reminders", {})}
                        aria-label="查询到期提醒"
                      >
                        查询到期提醒
                      </Button>
                    </Space>
                    <h3>押金跟进提醒</h3>
                    {bondActive ? (
                      <>
                        <p className="muted small">
                          当前提醒时间：
                          {savedFollowUp
                            ? sydneyTime(savedFollowUp)
                            : "尚未设置"}
                          。由你选择日期，系统不会自行推算法定期限。
                        </p>
                        <Space wrap>
                          <Input
                            type="date"
                            aria-label="押金跟进提醒日期"
                            min={sydneyToday()}
                            value={followDate}
                            onChange={(e) => setFollowDate(e.target.value)}
                          />
                          <Input
                            type="time"
                            aria-label="押金跟进提醒时间"
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
                            保存提醒时间（悉尼时间）
                          </Button>
                        </Space>
                      </>
                    ) : (
                      <p className="muted small">
                        押金跟进激活后，可以选择一个查看押金状态的提醒时间。
                      </p>
                    )}
                    <h3>本地收件箱</h3>
                    {reminders.filter((r) => r.state === "delivered").length ===
                    0 ? (
                      <p className="muted">当前没有已投递提醒。</p>
                    ) : (
                      reminders
                        .filter((r) => r.state === "delivered")
                        .map((r, i) => (
                          <div className="detail-row" key={i}>
                            <strong>{taskTitle(r.title)}</strong>
                            <p>到期：{sydneyTime(r.due_at)}</p>
                            <small>提醒于 {sydneyTime(r.delivered_at)}</small>
                          </div>
                        ))
                    )}
                    <Collapse
                      ghost
                      items={[
                        {
                          key: "all",
                          label: "查看计划中及已抑制的提醒",
                          children: reminders.map((r, i) => (
                            <div className="detail-row" key={i}>
                              <strong>{taskTitle(r.title)}</strong>
                              <p>
                                到期：{sydneyTime(r.due_at)} ·{" "}
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
                label: `待审核事项 ${reviews.filter((r) => r.status === "open").length}`,
                children: (
                  <section className="panel">
                    <h2>人工审核事项</h2>
                    <p className="muted">
                      本地演示操作员在独立视图处理，租客不能放行。
                    </p>
                    {reviews.length === 0 ? (
                      <p>当前没有审核事项。</p>
                    ) : (
                      reviews.map((r, i) => (
                        <div className="detail-row" key={i}>
                          <Status value={String(r.status)} />
                          <strong>{text(r.reason)}</strong>
                          <p className="small">
                            提交于 {sydneyTime(r.created_at)}
                          </p>
                          {((r.decisions as Dict[]) ?? []).map((d, j) => (
                            <p className="small" key={j}>
                              {decisionNames[String(d.decision)] ??
                                text(d.decision)}
                              ：{text(d.note)}（{sydneyTime(d.at)}）
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
                label: "操作记录与原始案件引用",
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
        title="已确认资料与证据"
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
        title="补充租约资料"
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
                title="计划已确认或押金跟进已激活，当前租约资料不可修改。"
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
            ? "登记资料引用"
            : "登记合成证据元数据"
        }
        open={formOpen}
        onCancel={() => {
          if (action.busy || refreshing) return;
          if (pendingOperation === "add_evidence" && recovery.error) abandon();
          setFormOpen(false);
        }}
        confirmLoading={action.busy}
        okButtonProps={{ "aria-label": "保存证据引用", disabled: refreshing }}
        cancelButtonProps={{ disabled: action.busy || refreshing }}
        closable={!action.busy && !refreshing}
        mask={{ closable: !action.busy && !refreshing }}
        onOk={addEvidence}
        okText="保存证据引用"
        cancelText={
          pendingOperation === "add_evidence" && recovery.error
            ? "取消本次编辑"
            : "取消"
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
          <Form.Item name="kind" label="证据类型">
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
                ? "资料位置或文档名称"
                : "合成来源引用"
            }
            rules={[{ required: true }]}
          >
            <Input
              placeholder={
                config.mode === "real_listings"
                  ? "填写你保存资料的位置或名称"
                  : "synthetic://…"
              }
            />
          </Form.Item>
          <Form.Item
            name="source_version"
            label="来源版本"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} precision={0} />
          </Form.Item>
          <Form.Item
            name="summary"
            label="证据摘要"
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
