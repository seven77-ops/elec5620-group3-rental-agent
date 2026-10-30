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
  budget: "Adjust budget",
  rooms: "Adjust housing needs",
  commute: "Adjust commute",
  area: "Adjust area",
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
          throw new Error(
            "The filter response is incomplete. Please load the latest conversation.",
          );
        if (valid) setContext(value);
      })
      .catch((e) => {
        if (valid)
          setReadError(
            e instanceof Error ? e.message : "Could not load criteria",
          );
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
        title="The current filters have not loaded"
        action={
          <Button onClick={() => setReload((v) => v + 1)}>Retry loading</Button>
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
    [f.min_bedrooms ?? c.min_bedrooms ?? 0, "bed"],
    [f.min_bathrooms ?? c.min_bathrooms ?? 0, "bath"],
    [f.min_car_spaces ?? c.min_car_spaces ?? 0, "car spaces"],
  ] as const;
  const parts = roomParts
    .filter(([value]) => value > 0)
    .map(([value, label]) => `${value} ${label}`);
  const roomLabel = parts.length
    ? `At least ${parts.join(" · ")}`
    : "Any layout";
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
        message.info("The criteria have not changed.");
        return;
      }
      if (await onApply(patch as RecommendationPatch, snapshot))
        setEditing(null);
    } catch {
      /* Inline validation preserves the inputs. */
    }
  };
  return (
    <section
      className="recommendation-controls"
      aria-label="Current housing criteria"
    >
      <div className="recommendation-controls-heading">
        <strong>Current housing criteria</strong>
        <span>
          {loading ? (
            <Spin size="small" />
          ) : (
            `Filtered ${context.total} properties`
          )}
        </span>
      </div>
      <div className="recommendation-condition-buttons">
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="Edit budget criteria"
          disabled={locked}
          onClick={() => open("budget")}
        >
          {f.max_weekly_rent != null
            ? `Weekly rent ≤AUD ${f.max_weekly_rent}`
            : c.budget_amount != null
              ? `Budget AUD ${c.budget_amount} (not used to filter listings)`
              : "Any budget"}
        </Button>
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="Edit housing criteria"
          disabled={locked}
          onClick={() => open("rooms")}
        >
          {roomLabel}
        </Button>
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="Edit commute criteria"
          disabled={locked}
          onClick={() => open("commute")}
        >
          {modeLabel
            ? `${modeLabel}${f.usyd_max_minutes || c.commute_max_minutes ? ` ≤${f.usyd_max_minutes ?? c.commute_max_minutes} minutes` : ""}`
            : "Add commute criteria"}
        </Button>
        <Button
          size="small"
          icon={<EditOutlined />}
          aria-label="Edit area criteria"
          disabled={locked}
          onClick={() => open("area")}
        >
          {f.suburb || "All areas"}
        </Button>
      </div>
      {context.total === 0 && context.alternatives.length > 0 && (
        <div
          className="recommendation-alternatives"
          aria-label="Options when there are no matches"
        >
          <p>Adjust one item below while keeping the other criteria:</p>
          {context.alternatives.map((option) => (
            <Button
              key={option.id}
              disabled={locked || option.count === 0}
              onClick={() => void onApply(option.patch, context)}
            >
              {option.label} ·{" "}
              {option.count
                ? `Matches available: ${option.count} properties`
                : "Still no matches"}
            </Button>
          ))}
        </div>
      )}
      {(readError || context.revision !== revision) && (
        <Alert
          type="warning"
          title="These criteria have changed. Load the latest conversation before editing."
          action={
            <Button onClick={onReload} disabled={busy}>
              Load latest conversation
            </Button>
          }
        />
      )}
      <Modal
        title={editing ? titles[editing] : "Adjust current criteria"}
        open={!!editing}
        onCancel={() => !busy && setEditing(null)}
        onOk={() => void apply()}
        okText="Apply changes and filter again"
        cancelText="Cancel"
        confirmLoading={busy}
        okButtonProps={{
          disabled:
            busy ||
            disabled ||
            loading ||
            snapshot?.revision !== context.revision,
        }}
        cancelButtonProps={{ disabled: busy, "aria-label": "Cancel" }}
        closable={!busy}
      >
        <Form form={form} layout="vertical" disabled={busy} preserve>
          {editing === "budget" && (
            <Form.Item
              name="budget_amount"
              label={
                snapshot?.filters.max_weekly_rent != null
                  ? "Maximum weekly rent (AUD)"
                  : "Budget amount (keep current pricing basis)"
              }
              rules={[{ required: true }]}
            >
              <InputNumber
                aria-label="Current budget limit"
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
                  ["min_bedrooms", "Minimum bedrooms"],
                  ["min_bathrooms", "Minimum bathrooms"],
                  ["min_car_spaces", "Minimum car spaces"],
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
                label="Travel mode"
                rules={[{ required: true }]}
              >
                <Select
                  aria-label="Current travel mode"
                  options={commuteModes}
                />
              </Form.Item>
              <Form.Item
                name="commute_max_minutes"
                label="Maximum one-way minutes"
                rules={[{ required: true }]}
              >
                <InputNumber
                  aria-label="Current commute limit"
                  min={1}
                  max={240}
                  precision={0}
                  style={{ width: "100%" }}
                />
              </Form.Item>
            </>
          )}
          {editing === "area" && (
            <Form.Item name="suburb" label="Area" rules={[{ required: true }]}>
              <Select
                aria-label="Current area"
                showSearch
                optionFilterProp="label"
                options={[
                  { value: "__all__", label: "All areas" },
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
          Applying updates these results and keeps the other criteria.
        </p>
        {error && (
          <Alert
            type="error"
            title="Could not complete the change"
            description={error}
          />
        )}
      </Modal>
    </section>
  );
}
