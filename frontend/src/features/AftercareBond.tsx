import { useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Timeline,
} from "antd";
import { useCase } from "../app/context";
import type { Dict } from "../api/types";
import {
  CommandRecovery,
  type CommandRecoveryProps,
  type SendCommand,
} from "./AftercarePlan";
import { JsonDetails, money, Status, text } from "../components/Common";
export default function AftercareBond({
  bond,
  evidence,
  send,
  busy,
  clock,
  recovery,
}: {
  bond: Dict | null;
  evidence: Dict[];
  send: SendCommand;
  busy: boolean;
  clock: string;
  recovery: CommandRecoveryProps;
}) {
  const { config } = useCase();
  const real = config.mode === "real_listings";
  const [bondRef, setBondRef] = useState(real ? "" : "SYNTHETIC-RBO-001");
  const [update, setUpdate] = useState(false);
  const [form] = Form.useForm();
  const [outcome, setOutcome] = useState("");
  const { modal } = App.useApp();
  const state = String(bond?.state ?? "");
  const history = (bond?.history ?? []) as Dict[];
  const claims = (bond?.claims ?? []) as Dict[];
  const drafts = (bond?.drafts ?? []) as Dict[];
  const submitUpdate = async () => {
    try {
      const v = await form.validateFields();
      const claim = v.has_claim
        ? [
            {
              claim_id: `claim-${crypto.randomUUID()}`,
              amount_cents: v.amount_cents,
              reason: v.reason,
              evidence_refs: v.evidence_refs ?? [],
              disputed: Boolean(v.disputed),
            },
          ]
        : [];
      const saved = await send(
        state === "Draft" ? "activate_bond" : "bond_update",
        {
          entry: {
            text: v.text,
            occurred_at: clock,
            evidence_refs: v.evidence_refs ?? [],
            tenant_confirmed: true,
            claims: claim,
            conflicting_evidence: false,
          },
        },
      );
      if (saved) setUpdate(false);
    } catch {
      /* Inline errors. */
    }
  };
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>押金跟进</h2>
        {bond && <Status value={state} />}
      </div>
      <p className="muted">
        记录租客报告的事实和扣款主张。记录扣款不表示你已接受，跟进草稿也不会自动发送。
      </p>
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
          {state === "UnderReview" && (
            <Alert
              type="warning"
              showIcon
              title="存在争议或审核门禁"
              description="需要授权操作员处理。租客仍可记录事实或明确确认结果；普通页面不能放行。"
            />
          )}
          <Space wrap className="section-actions">
            <Button
              type="primary"
              disabled={["Resolved", "Withdrawn"].includes(state)}
              loading={busy}
              onClick={() => {
                form.resetFields();
                setUpdate(true);
              }}
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
              准备跟进草稿
            </Button>
          </Space>
          <h3>事实时间线</h3>
          {history.length ? (
            <Timeline
              items={history.map((h) => ({
                content: (
                  <>
                    <strong>{text(h.occurred_at)}</strong>
                    <p>{text(h.text)}</p>
                    <small>
                      证据引用：
                      {text(
                        ((h.evidence_refs as string[]) ?? []).join("、") ||
                          "无",
                      )}
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
              <h3>报告的扣款主张 · reported_claim</h3>
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
          {drafts.length > 0 && (
            <>
              <h3>跟进草稿 · 尚未发送</h3>
              {drafts.map((d, i) => (
                <article className="draft-block" key={i}>
                  <Status value={String(d.status)} />
                  <p className="source-quote">{text(d.text)}</p>
                  <small>
                    依据版本 {text(d.based_on_version)} · 需租客复核
                  </small>
                </article>
              ))}
            </>
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
          {bond.outcome && <JsonDetails value={bond.outcome} />}
        </>
      )}
      <Modal
        title={
          state === "Draft" ? "确认事实并激活跟进" : "记录新事实或扣款主张"
        }
        open={update}
        onCancel={() => {
          if (busy || recovery.refreshing) return;
          if (recovery.error) recovery.abandon();
          setUpdate(false);
        }}
        confirmLoading={busy}
        okButtonProps={{
          "aria-label": "确认并记录",
          disabled: recovery.refreshing,
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
        <details>
          <summary>查看当前已保存事实与扣款主张</summary>
          <JsonDetails value={{ history, claims }} />
        </details>
        <Form
          disabled={busy || recovery.refreshing}
          form={form}
          layout="vertical"
          initialValues={{
            has_claim: false,
            disputed: true,
            amount_cents: 18000,
          }}
        >
          <Form.Item
            name="text"
            label="租客报告的事实"
            rules={[{ required: true, message: "填写你确认的事实" }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="evidence_refs" label="关联证据">
            <Select
              mode="multiple"
              options={evidence.map((e) => ({
                value: String(e.evidence_id),
                label: String(e.evidence_id),
              }))}
            />
          </Form.Item>
          <Form.Item name="has_claim" valuePropName="checked">
            <Checkbox>包含一项报告的扣款主张</Checkbox>
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(a, b) => a.has_claim !== b.has_claim}
          >
            {({ getFieldValue }) =>
              getFieldValue("has_claim") ? (
                <>
                  <Form.Item
                    name="amount_cents"
                    label="主张金额（AUD 整数分，18000 = AUD 180）"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={0} precision={0} />
                  </Form.Item>
                  <Form.Item
                    name="reason"
                    label="报告的扣款原因"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item name="disputed" valuePropName="checked">
                    <Checkbox>租客对该主张有争议</Checkbox>
                  </Form.Item>
                </>
              ) : null
            }
          </Form.Item>
          <p className="muted small">
            记录时间由服务器演示时钟处理，事实时间：{clock}
            。点击确认表示你确认这条报告，不表示接受扣款。
          </p>
        </Form>
      </Modal>
    </section>
  );
}
