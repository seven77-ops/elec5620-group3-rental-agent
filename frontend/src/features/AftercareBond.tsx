import { useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Timeline,
} from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { useCase } from "../app/context";
import { post } from "../api/client";
import type { Dict } from "../api/types";
import {
  CommandRecovery,
  type CommandRecoveryProps,
  type SendCommand,
} from "./AftercarePlan";
import { Failure, money, Status, text } from "../components/Common";
import { useAction } from "../components/useAction";
import AftercareBondDetails from "./AftercareBondDetails";
import type { PrefillValue } from "./aftercare/prefill";
import { sydneyIso, sydneyTime, sydneyToday } from "./aftercare/presentation";

interface ExtractedClaim {
  amount: number;
  amount_cents: number;
  reason: string;
  quote: string;
}
interface Extraction {
  claims: ExtractedClaim[];
  rejected: number;
  event_date: string | null;
  event_date_quote: string | null;
  notice: string;
}

const draftModes: Record<string, string> = {
  template: "事实模板",
  constrained_model: "AI 选择要点 · 程序逐句校验",
};

export default function AftercareBond({
  bond,
  evidence,
  send,
  busy,
  recovery,
  bondAmount,
}: {
  bond: Dict | null;
  evidence: Dict[];
  send: SendCommand;
  busy: boolean;
  clock?: string;
  recovery: CommandRecoveryProps;
  bondAmount?: PrefillValue;
}) {
  const { config, current } = useCase();
  const real = config.mode === "real_listings";
  const aiEnabled = Boolean((config.capabilities as Dict).external_ai);
  const [bondRef, setBondRef] = useState(real ? "" : "SYNTHETIC-RBO-001");
  const [update, setUpdate] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [form] = Form.useForm();
  const [outcome, setOutcome] = useState("");
  const [agentMessage, setAgentMessage] = useState("");
  const [aiConsent, setAiConsent] = useState(false);
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const extract = useAction();
  const { modal, message } = App.useApp();
  const state = String(bond?.state ?? "");
  const history = (bond?.history ?? []) as Dict[];
  const claims = (bond?.claims ?? []) as Dict[];
  const drafts = (bond?.drafts ?? []) as Dict[];
  const today = sydneyToday();
  const openUpdate = () => {
    form.resetFields();
    form.setFieldsValue({
      occurred_on: today,
      claims: [],
      conflicting_evidence: false,
    });
    setExtraction(null);
    setAgentMessage("");
    setAiConsent(false);
    extract.clear();
    setUpdate(true);
  };
  const readDeductions = () =>
    extract.run(async () => {
      const result = await post<Extraction>(
        `/cases/${encodeURIComponent(current.case_id)}/aftercare/deduction-extract`,
        { allow_external_ai: true, message: agentMessage },
      );
      setExtraction(result);
      const existing = (form.getFieldValue("claims") ?? []) as Dict[];
      form.setFieldsValue({
        claims: [
          ...existing,
          ...result.claims.map((c) => ({
            amount: c.amount,
            reason: c.reason,
            disputed: false,
            quote: c.quote,
          })),
        ],
        ...(result.event_date ? { occurred_on: result.event_date } : {}),
        ...(!form.getFieldValue("text")
          ? {
              text: `收到中介/房东关于押金扣款的通知（${result.claims.length} 项）。`,
            }
          : {}),
      });
    });
  const submitUpdate = async () => {
    try {
      const v = await form.validateFields();
      const entryClaims = ((v.claims ?? []) as Dict[]).map((c) => ({
        claim_id: `claim-${crypto.randomUUID()}`,
        amount_cents: Math.round(Number(c.amount) * 100),
        reason: String(c.reason).trim(),
        evidence_refs: v.evidence_refs ?? [],
        disputed: Boolean(c.disputed),
      }));
      // Today keeps the current time (a minute back for clock drift); earlier days use midday Sydney.
      const occurred =
        v.occurred_on && v.occurred_on < today
          ? sydneyIso(v.occurred_on, "12:00")
          : new Date(Date.now() - 60_000).toISOString();
      const saved = await send(
        state === "Draft" ? "activate_bond" : "bond_update",
        {
          entry: {
            text: v.text,
            occurred_at: occurred,
            evidence_refs: v.evidence_refs ?? [],
            tenant_confirmed: true,
            claims: entryClaims,
            conflicting_evidence: Boolean(v.conflicting_evidence),
          },
        },
      );
      if (saved) setUpdate(false);
    } catch {
      /* Inline errors. */
    }
  };
  const currentDraft = drafts.filter((d) => d.status === "current").at(-1);
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>押金跟进</h2>
        {bond && <Status value={state} />}
      </div>
      <p className="muted">
        记录租客报告的事实和扣款主张。记录扣款不表示你已接受，跟进草稿也不会自动发送。
      </p>
      {bondAmount && (
        <Alert
          className="aftercare-prefill"
          type="info"
          showIcon
          title={`合同中记录的押金：${money(Number(bondAmount.value))}`}
          description={`来源：${bondAmount.label}${bondAmount.quote ? `「${bondAmount.quote}」` : ""}。押金编号与实际金额请以 Rental Bonds Online 记录为准。`}
        />
      )}
      {!bond ? (
        <div className="date-actions">
          <label htmlFor="bond-reference">
            {real ? "押金记录编号（可暂不填写）" : "合成押金记录编号"}
          </label>
          <Input
            id="bond-reference"
            value={bondRef}
            onChange={(e) => setBondRef(e.target.value)}
          />
          <Button
            type="primary"
            loading={busy}
            onClick={() =>
              send("open_bond", {
                bond_reference: bondRef || null,
                deposit_evidence_ref: null,
              })
            }
            aria-label="建立押金跟进"
          >
            建立押金跟进
          </Button>
        </div>
      ) : (
        <>
          <p>押金编号：{text(bond.bond_reference)}</p>
          <p>押金凭证：{text(bond.deposit_evidence_ref)}</p>
          {state === "Draft" && (
            <>
              {!bond.bond_reference && !bond.deposit_evidence_ref && (
                <Alert
                  type="info"
                  showIcon
                  title="激活前请补录押金编号，或关联一份押金凭证。"
                />
              )}
              <Button
                disabled={busy || recovery.refreshing}
                onClick={() => {
                  recovery.abandon();
                  setDetailsOpen(true);
                }}
              >
                补录押金资料
              </Button>
            </>
          )}
          {state === "UnderReview" && (
            <Alert
              type="warning"
              showIcon
              title="存在争议或审核门禁"
              description="已转交人工审核。放行前不会生成跟进草稿；你仍可记录新事实，或明确确认结果。"
            />
          )}
          <Space wrap className="section-actions">
            <Button
              type="primary"
              disabled={["Resolved", "Withdrawn"].includes(state)}
              loading={busy}
              onClick={openUpdate}
              aria-label={
                state === "Draft"
                  ? "确认事实并激活跟进"
                  : "记录新事实或扣款主张"
              }
            >
              {state === "Draft"
                ? "确认事实并激活跟进"
                : "记录新事实或扣款主张"}
            </Button>
            <Button
              disabled={state !== "AwaitingOutcome"}
              loading={busy}
              onClick={() =>
                send("request_draft", {
                  use_model: false,
                  allow_external_ai: false,
                })
              }
              aria-label="准备跟进草稿"
            >
              准备事实草稿
            </Button>
            {aiEnabled && (
              <Button
                disabled={state !== "AwaitingOutcome"}
                loading={busy}
                onClick={() =>
                  modal.confirm({
                    title: "使用 AI 选择草稿要点？",
                    content:
                      "将把已登记的事实句目录发送至配置的 AI。AI 只能从目录中挑选句子编号，程序会核对必选事实和引用；不会生成新的事实，也不会发送邮件。",
                    okText: "同意并生成",
                    cancelText: "取消",
                    onOk: () =>
                      send("request_draft", {
                        use_model: true,
                        allow_external_ai: true,
                      }),
                  })
                }
                aria-label="AI 辅助准备草稿"
              >
                AI 辅助准备草稿
              </Button>
            )}
          </Space>
          <h3>事实时间线</h3>
          {history.length ? (
            <Timeline
              items={history.map((h) => ({
                content: (
                  <>
                    <strong>{sydneyTime(h.occurred_at, false)}</strong>
                    <p>{text(h.text)}</p>
                    <small>
                      证据引用：
                      {text(
                        ((h.evidence_refs as string[]) ?? []).join("、") ||
                          "无",
                      )}
                      {h.conflicting_evidence ? " · 已标记证据冲突" : ""}
                      {" · 登记于 "}
                      {sydneyTime(h.recorded_at)}
                    </small>
                  </>
                ),
              }))}
            />
          ) : (
            <p className="muted">尚未记录事实。</p>
          )}
          {claims.length > 0 && (
            <>
              <h3>报告的扣款主张（仅为对方主张，不代表扣款成立）</h3>
              {claims.map((c, i) => (
                <div key={i} className="detail-row">
                  <strong>{money(Number(c.amount_cents) / 100)}</strong>
                  <p>
                    {text(c.reason)} ·{" "}
                    {c.disputed ? "租客有争议" : "尚未标记争议"}
                  </p>
                  <small>
                    证据引用：
                    {text(
                      ((c.evidence_refs as string[]) ?? []).join("、") || "无",
                    )}
                  </small>
                </div>
              ))}
            </>
          )}
          {currentDraft && (
            <>
              <h3>跟进草稿 · 尚未发送</h3>
              <article className="draft-block">
                <Space wrap>
                  <Status value={String(currentDraft.status)} />
                  <span className="muted small">
                    {draftModes[String(currentDraft.mode)] ??
                      text(currentDraft.mode)}{" "}
                    · 依据案件版本 {text(currentDraft.based_on_version)} ·
                    需租客复核
                  </span>
                </Space>
                <p className="source-quote">{text(currentDraft.text)}</p>
                <Button
                  size="small"
                  onClick={() =>
                    void navigator.clipboard
                      .writeText(String(currentDraft.text))
                      .then(() => message.success("已复制，可粘贴到你自己的邮箱。"))
                  }
                >
                  复制草稿
                </Button>
              </article>
            </>
          )}
          {drafts.length > (currentDraft ? 1 : 0) && (
            <Collapse
              ghost
              items={[
                {
                  key: "old",
                  label: `查看较早或已过期的草稿（${drafts.length - (currentDraft ? 1 : 0)}）`,
                  children: drafts
                    .filter((d) => d !== currentDraft)
                    .map((d, i) => (
                      <article className="draft-block" key={i}>
                        <Status value={String(d.status)} />
                        <p className="source-quote">{text(d.text)}</p>
                      </article>
                    )),
                },
              ]}
            />
          )}
          {!["Resolved", "Withdrawn"].includes(state) && (
            <div className="closure-box">
              <h3>确认结果或撤回</h3>
              <label htmlFor="bond-outcome">你确认的结果或撤回原因</label>
              <Input.TextArea
                id="bond-outcome"
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                rows={3}
              />
              <Space wrap>
                <Button
                  disabled={
                    !outcome.trim() ||
                    !["AwaitingOutcome", "UnderReview"].includes(state)
                  }
                  loading={busy}
                  onClick={() =>
                    modal.confirm({
                      title: "明确确认押金结果并关闭跟进？",
                      content: outcome,
                      okText: "确认结果并关闭",
                      cancelText: "继续核对",
                      onOk: () =>
                        send("confirm_outcome", {
                          outcome,
                          evidence_refs: [],
                          tenant_confirmed: true,
                        }),
                    })
                  }
                  aria-label="确认结果并关闭跟进"
                >
                  确认结果并关闭跟进
                </Button>
                <Button
                  danger
                  disabled={!outcome.trim() || busy}
                  onClick={() =>
                    modal.confirm({
                      title: "明确撤回押金跟进？",
                      content: outcome,
                      okText: "确认撤回",
                      cancelText: "返回",
                      onOk: () =>
                        send("withdraw", {
                          reason: outcome,
                          tenant_confirmed: true,
                        }),
                    })
                  }
                >
                  撤回跟进
                </Button>
              </Space>
            </div>
          )}
          {Boolean(bond.outcome) && (
            <Alert
              type={state === "Resolved" ? "success" : "info"}
              showIcon
              title={state === "Resolved" ? "你已确认押金结果" : "你已撤回跟进"}
              description={`${text(
                (bond.outcome as Dict).outcome ?? (bond.outcome as Dict).reason,
              )} · 登记于 ${sydneyTime((bond.outcome as Dict).recorded_at)}`}
            />
          )}
        </>
      )}
      {detailsOpen && bond && (
        <AftercareBondDetails
          bond={bond}
          evidence={evidence}
          send={send}
          busy={busy}
          recovery={recovery}
          onClose={() => setDetailsOpen(false)}
        />
      )}
      <Modal
        title={
          state === "Draft" ? "确认事实并激活跟进" : "记录新事实或扣款主张"
        }
        open={update}
        width={720}
        onCancel={() => {
          if (busy || recovery.refreshing) return;
          if (recovery.error) recovery.abandon();
          setUpdate(false);
        }}
        confirmLoading={busy}
        okButtonProps={{
          "aria-label": "确认并记录",
          disabled: recovery.refreshing || extract.busy,
        }}
        cancelButtonProps={{ disabled: busy || recovery.refreshing }}
        closable={!busy && !recovery.refreshing}
        mask={{ closable: !busy && !recovery.refreshing }}
        onOk={submitUpdate}
        okText="确认并记录"
        cancelText={recovery.error ? "取消本次编辑" : "取消"}
      >
        <CommandRecovery
          {...recovery}
          retry={async () => {
            const saved = await recovery.retry();
            if (saved) setUpdate(false);
            return saved;
          }}
        />
        <p className="muted small">
          当前已保存跟进状态：
          <Status value={state} />
        </p>
        {aiEnabled ? (
          <Collapse
            className="aftercare-ai"
            items={[
              {
                key: "ai",
                label: "可选：用 AI 从中介/房东原文读取扣款主张",
                children: (
                  <>
                    <Input.TextArea
                      aria-label="中介或房东原文"
                      rows={4}
                      maxLength={8000}
                      value={agentMessage}
                      placeholder="粘贴中介或房东的邮件/短信原文"
                      onChange={(e) => setAgentMessage(e.target.value)}
                    />
                    <Checkbox
                      checked={aiConsent}
                      onChange={(e) => setAiConsent(e.target.checked)}
                    >
                      我同意只把这段原文发送至配置的 AI；原文不会保存到案件。
                    </Checkbox>
                    <div>
                      <Button
                        disabled={!aiConsent || !agentMessage.trim()}
                        loading={extract.busy}
                        onClick={() => void readDeductions()}
                      >
                        读取扣款主张
                      </Button>
                    </div>
                    <Failure error={extract.error} retry={extract.retry} />
                    {extraction && (
                      <Alert
                        type={extraction.claims.length ? "success" : "warning"}
                        showIcon
                        title={
                          extraction.claims.length
                            ? `已带入 ${extraction.claims.length} 项候选主张，请逐项核对金额和原因`
                            : "没有读到可核对的扣款金额，请手动填写"
                        }
                        description={
                          <>
                            <p className="small">{extraction.notice}</p>
                            {extraction.rejected > 0 && (
                              <p className="small">
                                另有 {extraction.rejected}{" "}
                                项因金额或引文与原文不符被程序丢弃。
                              </p>
                            )}
                            {extraction.event_date && (
                              <p className="small">
                                事实日期取自原文「{extraction.event_date_quote}」
                              </p>
                            )}
                          </>
                        }
                      />
                    )}
                  </>
                ),
              },
            ]}
          />
        ) : (
          <p className="muted small">
            配置 AI 后，可以粘贴中介原文自动读取扣款主张；现在请手动填写。
          </p>
        )}
        <Form
          disabled={busy || recovery.refreshing}
          form={form}
          layout="vertical"
          initialValues={{
            occurred_on: today,
            claims: [],
            conflicting_evidence: false,
          }}
        >
          <Form.Item
            name="text"
            label="租客报告的事实"
            rules={[{ required: true, message: "填写你确认的事实" }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            name="occurred_on"
            label="事实发生日期（悉尼时间）"
            rules={[
              { required: true, message: "选择日期" },
              {
                validator: (_, value) =>
                  !value || value <= today
                    ? Promise.resolve()
                    : Promise.reject(new Error("不能选择未来日期")),
              },
            ]}
          >
            <Input type="date" max={today} />
          </Form.Item>
          <Form.Item name="evidence_refs" label="关联证据">
            <Select
              mode="multiple"
              options={evidence.map((e) => ({
                value: String(e.evidence_id),
                label: `${e.summary ?? e.evidence_id}`,
              }))}
            />
          </Form.Item>
          <h4>对方报告的扣款主张</h4>
          <Form.List name="claims">
            {(fields, { add, remove }) => (
              <>
                {fields.map((f) => (
                  <div className="list-form-row claim-row" key={f.key}>
                    <Form.Item
                      name={[f.name, "amount"]}
                      label="金额（AUD）"
                      rules={[{ required: true, message: "填写金额" }]}
                    >
                      <InputNumber min={0.01} max={100000} precision={2} />
                    </Form.Item>
                    <Form.Item
                      name={[f.name, "reason"]}
                      label="对方说明的原因"
                      rules={[{ required: true, message: "填写原因" }]}
                    >
                      <Input maxLength={300} />
                    </Form.Item>
                    <Form.Item
                      name={[f.name, "disputed"]}
                      valuePropName="checked"
                      label="是否有争议"
                    >
                      <Checkbox>我对此有争议</Checkbox>
                    </Form.Item>
                    <Button
                      aria-label="移除此扣款主张"
                      icon={<MinusCircleOutlined />}
                      onClick={() => remove(f.name)}
                    />
                  </div>
                ))}
                <Button
                  icon={<PlusOutlined aria-hidden="true" />}
                  onClick={() => add({ amount: null, reason: "", disputed: false })}
                >
                  添加扣款主张
                </Button>
              </>
            )}
          </Form.List>
          <Form.Item name="conflicting_evidence" valuePropName="checked">
            <Checkbox>现有证据互相矛盾（例如入住报告与照片不一致），需要人工核对</Checkbox>
          </Form.Item>
          <p className="muted small">
            有争议的扣款或证据冲突会转交人工审核。点击确认表示你确认这条报告，不表示接受扣款。
          </p>
        </Form>
      </Modal>
    </section>
  );
}
