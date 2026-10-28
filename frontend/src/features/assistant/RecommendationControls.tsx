import { useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Form,
  InputNumber,
  Modal,
  Select,
  Spin,
} from "antd";
import { EditOutlined } from "@ant-design/icons";
import type {
  RecommendationContext,
  RecommendationPatch,
} from "../../api/assistant";
import { getRecommendationContext } from "../../api/assistant";
import { commuteModes } from "../real-data/commuteSummary";
import "./recommendationControls.css";

type Group = "budget" | "rooms" | "commute" | "area";
const titles: Record<Group, string> = {
  budget: "调整预算",
  rooms: "调整房型",
  commute: "调整通勤",
  area: "调整区域",
};
const fields: Record<Group, (keyof RecommendationPatch)[]> = {
  budget: ["budget_amount"],
  rooms: ["min_bedrooms", "min_bathrooms", "min_car_spaces"],
  commute: ["commute_mode", "commute_max_minutes"],
  area: ["suburb"],
};

export default function RecommendationControls({
  caseId,
  conversationId,
  revision,
  busy,
  error,
  disabled = false,
  onReload,
  onApply,
}: {
  caseId: string;
  conversationId: string | null;
  revision: number;
  busy: boolean;
  error: string | null;
  disabled?: boolean;
  onReload: () => void;
  onApply: (
    patch: RecommendationPatch,
    context: RecommendationContext,
  ) => Promise<boolean>;
}) {
  const [context, setContext] = useState<RecommendationContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [readError, setReadError] = useState("");
  const [reload, setReload] = useState(0);
  const [editing, setEditing] = useState<Group | null>(null);
  const [snapshot, setSnapshot] = useState<RecommendationContext | null>(null);
  const [form] = Form.useForm();
  const { message } = App.useApp();
  useEffect(() => {
    let valid = true;
    if (!conversationId) {
      setContext(null);
      return;
    }
    setLoading(true);
    setReadError("");
    getRecommendationContext(caseId, conversationId)
      .then((value) => {
        if (
          value &&
          (!value.criteria ||
            !value.filters ||
            !Array.isArray(value.alternatives) ||
            !Array.isArray(value.suburbs))
        )
          throw new Error("筛选条件返回格式不完整，请读取最新会话。");
        if (valid) setContext(value);
      })
      .catch((e) => {
        if (valid)
          setReadError(e instanceof Error ? e.message : "条件读取失败");
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [caseId, conversationId, revision, reload]);
  if (!context)
    return readError ? (
      <Alert
        type="warning"
        title="本次筛选条件暂未读取"
        action={
          <Button onClick={() => setReload((v) => v + 1)}>重试读取</Button>
        }
      />
    ) : null;
  const { criteria: c, filters: f } = context;
  const locked =
    busy || disabled || loading || !!readError || context.revision !== revision;
  const modeLabel = commuteModes.find(
    (item) => item.value === (f.usyd_mode || c.commute_mode),
  )?.label;
  const roomParts = [
    [f.min_bedrooms ?? c.min_bedrooms ?? 0, "卧"],
    [f.min_bathrooms ?? c.min_bathrooms ?? 0, "卫"],
    [f.min_car_spaces ?? c.min_car_spaces ?? 0, "车位"],
  ] as const;
  const parts = roomParts
    .filter(([value]) => value > 0)
    .map(([value, label]) => `${value} ${label}`);
  const roomLabel = parts.length ? `至少 ${parts.join(" · ")}` : "房型不限";
  const open = (group: Group) => {
    setSnapshot(context);
    setEditing(group);
    form.setFieldsValue({
      budget_amount: f.max_weekly_rent ?? c.budget_amount,
      min_bedrooms: f.min_bedrooms ?? c.min_bedrooms ?? 0,
      min_bathrooms: f.min_bathrooms ?? c.min_bathrooms ?? 0,
      min_car_spaces: f.min_car_spaces ?? c.min_car_spaces ?? 0,
      commute_mode: f.usyd_mode || c.commute_mode || "public_transport",
      commute_max_minutes: f.usyd_max_minutes ?? c.commute_max_minutes ?? 30,
      suburb: f.suburb || "__all__",
    });
  };
  const apply = async () => {
    if (!editing || !snapshot || busy) return;
    try {
      const input = await form.validateFields(fields[editing]);
      const patch: Record<string, unknown> = {};
      for (const key of fields[editing]) {
        const next =
          key === "suburb" && input[key] === "__all__" ? null : input[key];
        const old =
          snapshot.criteria[key] ??
          (key.startsWith("min_") ? 0 : key === "suburb" ? null : undefined);
        if (next !== old) patch[key] = next;
      }
      if (!Object.keys(patch).length) {
        message.info("条件没有变化。");
        return;
      }
      if (await onApply(patch as RecommendationPatch, snapshot))
        setEditing(null);
    } catch {
      /* Inline validation preserves the inputs. */
    }
  };
  return (
    <section className="recommendation-controls" aria-label="本次找房条件">
      <div className="recommendation-controls-heading">
        <strong>本次找房条件</strong>
        <span>
          {loading ? <Spin size="small" /> : `已筛选 ${context.total} 套`}
        </span>
      </div>
      <div className="recommendation-condition-buttons">
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="修改预算条件"
          disabled={locked}
          onClick={() => open("budget")}
        >
          {f.max_weekly_rent != null
            ? `周租 ≤AUD ${f.max_weekly_rent}`
            : c.budget_amount != null
              ? `预算 AUD ${c.budget_amount}（未用于房源筛选）`
              : "预算不限"}
        </Button>
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="修改房型条件"
          disabled={locked}
          onClick={() => open("rooms")}
        >
          {roomLabel}
        </Button>
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="修改通勤条件"
          disabled={locked}
          onClick={() => open("commute")}
        >
          {modeLabel
            ? `${modeLabel}${f.usyd_max_minutes || c.commute_max_minutes ? ` ≤${f.usyd_max_minutes ?? c.commute_max_minutes}分钟` : ""}`
            : "添加通勤条件"}
        </Button>
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="修改区域条件"
          disabled={locked}
          onClick={() => open("area")}
        >
          {f.suburb || "全部区域"}
        </Button>
      </div>
      {context.total === 0 && context.alternatives.length > 0 && (
        <div
          className="recommendation-alternatives"
          aria-label="无结果调整方案"
        >
          <p>可以只调整下面一项，其余条件保持不变：</p>
          {context.alternatives.map((option) => (
            <Button
              key={option.id}
              disabled={locked || option.count === 0}
              onClick={() => void onApply(option.patch, context)}
            >
              {option.label} ·{" "}
              {option.count ? `可找到 ${option.count} 套` : "仍无匹配"}
            </Button>
          ))}
        </div>
      )}
      {(readError || context.revision !== revision) && (
        <Alert
          type="warning"
          title="本次条件已有更新，请读取最新会话后再修改。"
          action={
            <Button onClick={onReload} disabled={busy}>
              读取最新会话
            </Button>
          }
        />
      )}
      <Modal
        title={editing ? titles[editing] : "调整本次条件"}
        open={!!editing}
        onCancel={() => !busy && setEditing(null)}
        onOk={() => void apply()}
        okText="应用修改并重新筛选"
        cancelText="取消"
        confirmLoading={busy}
        okButtonProps={{
          disabled:
            busy ||
            disabled ||
            loading ||
            snapshot?.revision !== context.revision,
        }}
        cancelButtonProps={{ disabled: busy, "aria-label": "取消" }}
        closable={!busy}
      >
        <Form form={form} layout="vertical" disabled={busy} preserve>
          {editing === "budget" && (
            <Form.Item
              name="budget_amount"
              label={
                snapshot?.filters.max_weekly_rent != null
                  ? "每周周租上限（AUD）"
                  : "预算金额（保留原计价方式）"
              }
              rules={[{ required: true }]}
            >
              <InputNumber
                aria-label="本次预算上限"
                min={0.01}
                max={1e12}
                precision={2}
                style={{ width: "100%" }}
              />
            </Form.Item>
          )}
          {editing === "rooms" && (
            <div className="recommendation-edit-grid">
              {(
                [
                  ["min_bedrooms", "至少卧室数"],
                  ["min_bathrooms", "至少浴室数"],
                  ["min_car_spaces", "至少车位数"],
                ] as const
              ).map(([key, label]) => (
                <Form.Item
                  key={key}
                  name={key}
                  label={label}
                  rules={[{ required: true }]}
                >
                  <InputNumber
                    aria-label={label}
                    min={0}
                    max={100}
                    precision={0}
                    style={{ width: "100%" }}
                  />
                </Form.Item>
              ))}
            </div>
          )}
          {editing === "commute" && (
            <>
              <Form.Item
                name="commute_mode"
                label="交通方式"
                rules={[{ required: true }]}
              >
                <Select aria-label="本次交通方式" options={commuteModes} />
              </Form.Item>
              <Form.Item
                name="commute_max_minutes"
                label="单程最多分钟数"
                rules={[{ required: true }]}
              >
                <InputNumber
                  aria-label="本次通勤上限"
                  min={1}
                  max={240}
                  precision={0}
                  style={{ width: "100%" }}
                />
              </Form.Item>
            </>
          )}
          {editing === "area" && (
            <Form.Item name="suburb" label="区域" rules={[{ required: true }]}>
              <Select
                aria-label="本次区域"
                showSearch
                optionFilterProp="label"
                options={[
                  { value: "__all__", label: "全部区域" },
                  ...(context.suburbs || []).map((value) => ({
                    value,
                    label: value,
                  })),
                ]}
              />
            </Form.Item>
          )}
        </Form>
        <p className="muted small">
          应用后更新本次找房结果，其他条件保持不变。
        </p>
        {error && (
          <Alert type="error" title="修改暂未完成" description={error} />
        )}
      </Modal>
    </section>
  );
}
