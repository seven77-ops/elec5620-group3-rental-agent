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
  Failure,
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
  const [refreshing, setRefreshing] = useState(false);
  const [pendingOperation, setPendingOperation] = useState("");
  const [evidenceForm] = Form.useForm();
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
      <Failure error={action.error || error} retry={action.retry} />
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
                来源：{text(record.tenancy.source_ref)} · v
                {text(record.tenancy.source_version)}
              </p>
            </div>
            <Button onClick={() => setEvidenceOpen(true)}>
              查看资料与证据
            </Button>
          </section>
          <Tabs
            defaultActiveKey={initialTab}
            items={[
              {
                key: "plan",
                label: "退租计划与任务",
                children: (
                  <AftercarePlan
                    initialDate={
                      config.mode === "real_listings"
                        ? initialMoveOutDate ||
                          config.clocks.aftercare.slice(0, 10)
                        : undefined
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
                      error: ["activate_bond", "bond_update"].includes(
                        pendingOperation,
                      )
                        ? recovery.error
                        : null,
                    }}
                    clock={String(record.updated_at ?? config.clocks.aftercare)}
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
                            follow_up_at: null,
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
                    <h3>本地收件箱</h3>
                    {reminders.filter((r) => r.state === "delivered").length ===
                    0 ? (
                      <p className="muted">当前没有已投递提醒。</p>
                    ) : (
                      reminders
                        .filter((r) => r.state === "delivered")
                        .map((r, i) => (
                          <div className="detail-row" key={i}>
                            <strong>{text(r.title)}</strong>
                            <p>{text(r.due_at)}</p>
                            <small>{text(r.delivered_at)}</small>
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
                              <strong>{text(r.title)}</strong>
                              <p>
                                到期：{text(r.due_at)} · 原始状态：
                                {text(r.state)}
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
                          <p>引用：{text(r.source_refs)}</p>
                          <JsonDetails value={r.decisions} />
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
        <h3>租约资料</h3>
        <JsonDetails value={record?.tenancy} />
        <h3>证据元数据</h3>
        <Alert
          type="info"
          title="引用不等于事实已核实"
          description={
            config.mode === "real_listings"
              ? "这里只记录你填写的资料位置和摘要，不上传文件或验证内容。"
              : "这里只登记合成证据元数据，不上传照片或执行图片识别。"
          }
        />
        {evidence.map((e, i) => (
          <div className="detail-row" key={i}>
            <strong>
              {text(e.evidence_id)} · {text(e.kind)}
            </strong>
            <p>{text(e.summary)}</p>
            <small className="break-word">
              {text(e.source_ref)} · v{text(e.source_version)}
            </small>
          </div>
        ))}
        <Button
          onClick={() => {
            evidenceForm.resetFields();
            setFormOpen(true);
          }}
        >
          登记证据引用
        </Button>
      </EvidenceDrawer>
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
              ].map((value) => ({ value, label: value }))}
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
