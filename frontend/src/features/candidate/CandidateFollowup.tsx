import { housingCopy } from "../real-data/listingPresentation";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  App,
  Button,
  Collapse,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Tag,
} from "antd";
import { ArrowRightOutlined, CalendarOutlined } from "@ant-design/icons";
import { currentConfirmation, useCase } from "../../app/context";
import { downloadUrl, newRequestId } from "../../api/client";
import { getFollowup, saveFollowup } from "../../api/followup";
import type {
  CandidateFacts,
  CandidateFollowup as Followup,
} from "../../api/followup";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";

const questions = [
  "目前是否仍可租？何时可以看房？",
  "实际租金是多少，按周、月还是两周支付？是整套、每间还是每人计价？",
  "哪些账单包含在租金中？还有哪些费用？",
  "起租日期、租期和押金分别是多少？",
  "卧室、浴室和车位是否全部包含在本次出租范围内？",
  "申请需要哪些资料？能否提供拟签合同及出租方或代理信息？",
];
const options = (pairs: [string, string][]) =>
  pairs.map(([value, label]) => ({ value, label }));
export default function CandidateFollowup({
  compact = false,
}: {
  compact?: boolean;
}) {
  const { current, go } = useCase();
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState<Followup | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [revision, setRevision] = useState(0);
  const [form] = Form.useForm<CandidateFacts>();
  const action = useAction();
  const [params, setParams] = useSearchParams();
  const selection =
    current.selection?.data_mode === "real_listings" ? current.selection : null;
  const confirmation = currentConfirmation(current);
  const isCurrent = Boolean(
    selection &&
    confirmation &&
    selection.profile_version === confirmation.version &&
    selection.profile_fingerprint === confirmation.fingerprint,
  );
  // Includes selected_at: choosing the same ad again creates a new candidate context.
  const identity = JSON.stringify(selection);
  useEffect(() => {
    if (params.get("followup") === "1" && selection) {
      setOpen(true);
      const next = new URLSearchParams(params);
      next.delete("followup");
      setParams(next, { replace: true });
    }
  }, [params, setParams, identity]);
  useEffect(() => {
    let valid = true;
    setValue(null);
    setError(null);
    if (!open || !selection) return;
    setLoading(true);
    getFollowup(current.case_id)
      .then((result) => {
        if (!valid) return;
        setValue(result);
        form.setFieldsValue(result.facts);
      })
      .catch((e) => {
        if (valid) setError(e);
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [open, identity, current.case_id, form, revision]);
  if (!selection) return null;
  const save = async () => {
    let facts: CandidateFacts;
    try {
      facts = await form.validateFields();
    } catch {
      return;
    }
    if (!value) return;
    const body = {
      request_id: newRequestId(),
      expected_version: value.version,
      selection_signature: value.selection_signature,
      confirmed: true as const,
      facts: {
        ...facts,
        rent_amount: facts.rent_amount ?? null,
        bond: facts.bond ?? null,
        start_date: facts.start_date || null,
        end_date: facts.end_date || null,
        landlord: facts.landlord || "",
        viewing_note: facts.viewing_note || "",
        notes: facts.notes || "",
      },
    };
    void action.run(async () => {
      const saved = await saveFollowup(current.case_id, body);
      setValue(saved);
      message.success("跟进记录已保存，合同复核会带入这份记录。");
    });
  };
  return (
    <>
      <section
        className={`candidate-next ${compact ? "candidate-next-compact" : ""}`}
        data-testid="candidate-next"
      >
        <div className="candidate-next-copy">
          <span className="muted small">
            {compact ? "当前候选" : "已保存真实房源候选"}
          </span>
          <strong>
            {String(selection.listing_snapshot.address ?? selection.listing_id)}
          </strong>
          {!compact && (
            <p className="muted">
              下一步，安排看房并确认租赁信息；已有合同可以直接复核。
            </p>
          )}
        </div>
        <Space wrap>
          <Button
            aria-label="准备看房与询问"
            icon={<CalendarOutlined />}
            type={compact ? "default" : "primary"}
            onClick={() => {
              action.clear();
              setOpen(true);
            }}
          >
            准备看房与询问
          </Button>
          <Button
            disabled={!isCurrent}
            onClick={() => go("contract?mode=draft")}
          >
            生成租约草稿
          </Button>
          <Button
            disabled={!isCurrent}
            onClick={() => go("contract?mode=review")}
            aria-label="已有合同，开始复核"
            icon={<ArrowRightOutlined />}
          >
            已有合同，开始复核
          </Button>
        </Space>
        {!isCurrent && (
          <Alert
            type="warning"
            showIcon
            title="历史候选 · 需求已变化，请重新选择后继续。"
          />
        )}
      </section>
      <Drawer
        title="房源跟进"
        open={open}
        onClose={() => {
          if (!action.busy) setOpen(false);
        }}
        size={640}
        className="candidate-followup-drawer"
        extra={
          <a
            href={downloadUrl(
              `/cases/${current.case_id}/candidate-followup/questions`,
            )}
          >
            下载询问清单
          </a>
        }
      >
        <div className="candidate-followup-heading">
          <h2>{String(selection.listing_snapshot.address)}</h2>
          <Space wrap>
            <Tag color="blue">
              房源 AUD {String(selection.listing_snapshot.weekly_rent)}/周
            </Tag>
            <a
              href={String(selection.listing_snapshot.source_url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              查看原始房源 ↗
            </a>
          </Space>
        </div>
        <Collapse
          defaultActiveKey={["questions"]}
          items={[
            {
              key: "questions",
              label: "看房前可以这样问",
              children: (
                <ol className="candidate-questions">
                  {questions.map((q) => (
                    <li key={q}>{housingCopy(q)}</li>
                  ))}
                </ol>
              ),
            },
          ]}
        />
        <div className="candidate-followup-form-heading">
          <h3>记录中介回复与看房情况</h3>
          <span className="muted small">
            {value?.version
              ? `已保存 v${value.version} · 用户记录`
              : "未知的内容可以留空"}
          </span>
        </div>
        <Failure
          error={error || action.error}
          retry={error ? () => setRevision((v) => v + 1) : action.retry}
        />
        {Boolean(action.error) && (
          <Button
            onClick={() => {
              action.clear();
              setRevision((v) => v + 1);
            }}
          >
            重新读取跟进记录
          </Button>
        )}
        {!isCurrent && (
          <Alert type="warning" showIcon title="这是历史候选，当前只能查看。" />
        )}
        <Form
          form={form}
          layout="vertical"
          requiredMark={false}
          onFinish={() => void save()}
          disabled={!value || loading || action.busy || !isCurrent}
        >
          <div className="candidate-facts-grid">
            <Form.Item name="stage" label="当前安排">
              <Select
                virtual={false}
                options={options([
                  ["research", "了解房源"],
                  ["viewing", "准备看房"],
                  ["application", "准备申请"],
                ])}
              />
            </Form.Item>
            <Form.Item name="availability" label="中介回复的在租情况">
              <Select
                virtual={false}
                options={options([
                  ["unknown", "待确认"],
                  ["available", "回复可租"],
                  ["unavailable", "回复已不可租"],
                ])}
              />
            </Form.Item>
            <Form.Item name="rent_amount" label="回复中的租金（AUD）">
              <InputNumber min={0.01} max={999999} />
            </Form.Item>
            <Form.Item name="rent_period" label="租金周期">
              <Select
                virtual={false}
                options={options([
                  ["unknown", "待确认"],
                  ["week", "每周"],
                  ["fortnight", "每两周"],
                  ["month", "每月"],
                ])}
              />
            </Form.Item>
            <Form.Item name="rent_scope" label="租金计价对象">
              <Select
                virtual={false}
                options={options([
                  ["unknown", "待确认"],
                  ["whole_property", "整套"],
                  ["per_room", "每间"],
                  ["per_person", "每人"],
                ])}
              />
            </Form.Item>
            <Form.Item name="bills" label="账单">
              <Select
                virtual={false}
                options={options([
                  ["unknown", "待确认"],
                  ["included", "包含账单"],
                  ["excluded", "不含账单"],
                ])}
              />
            </Form.Item>
            <Form.Item name="bond" label="回复中的押金（AUD）">
              <InputNumber min={0.01} max={999999} />
            </Form.Item>
            <Form.Item name="landlord" label="出租方（合同主体）">
              <Input maxLength={200} />
            </Form.Item>
            <Form.Item name="start_date" label="起租日期">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="end_date" label="结束日期">
              <Input type="date" />
            </Form.Item>
          </div>
          <Form.Item name="viewing_note" label="看房安排">
            <Input placeholder="例如：周六 11:30，尚未预约" maxLength={500} />
          </Form.Item>
          <Form.Item
            name="source_note"
            label="信息来源"
            rules={[
              { required: true, whitespace: true, message: "请填写信息来源" },
            ]}
          >
            <Input
              placeholder="例如：10月22日中介邮件／本人看房记录"
              maxLength={500}
            />
          </Form.Item>
          <Form.Item name="notes" label="其他回复或待问事项">
            <Input.TextArea rows={3} maxLength={2000} />
          </Form.Item>
          <p className="muted small">
            这些内容按你的记录保存，尚未经平台独立核实。准备申请不代表已经提交。
          </p>
          <Space wrap>
            <Button type="primary" htmlType="submit" loading={action.busy}>
              确认保存跟进信息
            </Button>
            <Button
              disabled={!isCurrent}
              onClick={() => go("contract?mode=review")}
            >
              已有合同，开始复核
            </Button>
          </Space>
        </Form>
      </Drawer>
    </>
  );
}
