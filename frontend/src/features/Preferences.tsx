import { useState } from "react";
import {
  App,
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
} from "antd";
import { useCase, currentConfirmation } from "../app/context";
import { post, newRequestId } from "../api/client";
import type { Profile } from "../api/types";
import { mergeEditableProfile } from "../api/profile";
import { Failure, label, money, PageTitle } from "../components/Common";
import { useAction } from "../components/useAction";
import WeightControl from "./WeightControl";
const dimensions = ["commute", "cost", "housing", "amenities"];
const facilities = [
  "private_bedroom",
  "private_bathroom",
  "furnished",
  "laundry",
  "kitchen_access",
];
function Summary({ profile }: { profile: Profile }) {
  return (
    <dl className="summary-list" tabIndex={0} aria-label="完整偏好摘要">
      <div>
        <dt>周预算</dt>
        <dd>
          {money(profile.budget?.preferred)}，最高{" "}
          {money(profile.budget?.maximum)} /{" "}
          {label(profile.budget?.scope ?? "")}
          <small>
            {profile.budget?.includes_bills ? "包含账单" : "账单另核对"} ·{" "}
            {profile.budget?.hard_limit
              ? "最高预算为硬条件"
              : "最高预算为软限制"}
          </small>
        </dd>
      </div>
      <div>
        <dt>居住</dt>
        <dd>
          {profile.occupants} 人 · {label(profile.rental_mode)}
        </dd>
      </div>
      <div>
        <dt>通勤</dt>
        <dd>
          期望 {profile.commute?.preferred_minutes} 分钟，最长{" "}
          {profile.commute?.maximum_minutes} 分钟
          <small>
            {profile.destination_id} · {profile.arrival_time} 到达 ·{" "}
            {profile.timezone ?? "Australia/Sydney"}
            <br />
            {profile.commute?.modes?.map(label).join("、")} ·{" "}
            {profile.commute?.hard_limit
              ? "最长通勤为硬条件"
              : "最长通勤为软限制"}
          </small>
        </dd>
      </div>
      <div>
        <dt>租期</dt>
        <dd>
          {profile.move_in_window?.from} 至 {profile.move_in_window?.to} 入住
          <small>{profile.lease_months} 个月</small>
        </dd>
      </div>
      <div>
        <dt>必须满足</dt>
        <dd>
          {profile.hard_requirements?.map(label).join("、") ||
            "无额外设施硬要求"}
        </dd>
      </div>
      <div>
        <dt>软设施偏好</dt>
        <dd>
          {Object.entries(profile.soft_preferences ?? {})
            .filter(
              ([k, v]) => v > 0 && !profile.hard_requirements?.includes(k),
            )
            .map(([k, v]) => `${label(k)} ${v}`)
            .join("、") || "未指定"}
        </dd>
      </div>
      <div>
        <dt>四维相对权重</dt>
        <dd>
          {Object.entries(profile.weights ?? {})
            .map(([k, v]) => `${label(k)} ${v}`)
            .join(" · ")}
        </dd>
      </div>
    </dl>
  );
}
export default function Preferences() {
  const { current, refresh, go } = useCase();
  const [form] = Form.useForm<Profile>();
  const { modal, message } = App.useApp();
  const [dirty, setDirty] = useState(false);
  const action = useAction();
  const confirmation = currentConfirmation(current);
  const values = Form.useWatch([], form) as Profile | undefined;
  const profile = values ?? current.draft.profile;
  const save = async () => {
    try {
      const value = await form.validateFields();
      if (Object.values(value.weights ?? {}).every((v) => v === 0)) {
        form.setFields([
          { name: ["weights", "commute"], errors: ["四维权重至少一项大于零"] },
        ]);
        return;
      }
      value.soft_preferences = Object.fromEntries(
        Object.entries(value.soft_preferences ?? {}).filter(
          ([key, v]) =>
            !value.hard_requirements.includes(key) && v != null && v > 0,
        ),
      );
      void action.run(async () => {
        await post(`/cases/${current.case_id}/profile-drafts`, {
          expected_revision: current.draft.revision,
          profile: mergeEditableProfile(current.draft.profile, value),
        });
        await refresh();
        setDirty(false);
        message.success("草稿已保存，请确认当前偏好后再生成推荐。");
      });
    } catch {
      /* Form renders field errors. */
    }
  };
  const confirm = () =>
    modal.confirm({
      title: "确认当前偏好",
      content: (
        <>
          <p>你将批准当前保存的草稿修订 {current.draft.revision}。</p>
          <Summary profile={current.draft.profile} />
        </>
      ),
      okText: "确认这些条件",
      cancelText: "返回检查",
      onOk: () =>
        action.run(async () => {
          await post(`/cases/${current.case_id}/profile-confirmations`, {
            draft_revision: current.draft.revision,
            fingerprint: current.draft.fingerprint,
          });
          await refresh();
          message.success("当前偏好已确认。");
        }),
    });
  const evaluate = () => {
    const body = {
      request_id: newRequestId(),
      confirmation_version: confirmation?.version,
    };
    void action.run(async () => {
      await post(`/cases/${current.case_id}/evaluations`, body);
      await refresh();
      go("recommendations");
    });
  };
  return (
    <>
      <PageTitle
        title="租房偏好"
        description="先把需要的条件说清楚，再确认用于推荐的版本。"
        extra={
          <span className="revision-label">
            草稿修订 {current.draft.revision}
          </span>
        }
      />
      <Alert
        type="info"
        showIcon
        title="模拟 Agent 1 输入"
        description="以下初始值来自合成偏好样例，可编辑后确认。当前未接入真实对话或模型提取。"
      />
      <Failure error={action.error} retry={action.retry} />
      <div className="preference-layout">
        <Form
          form={form}
          name="preferences"
          initialValues={current.draft.profile}
          layout="vertical"
          onValuesChange={() => setDirty(true)}
          className="preference-form"
          key={current.draft.revision}
        >
          <section className="panel">
            <h2>预算与居住方式</h2>
            <div className="form-grid">
              <Form.Item
                label="期望周预算（AUD）"
                name={["budget", "preferred"]}
                rules={[{ required: true, message: "填写期望周预算" }]}
              >
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item
                label="最高周预算（AUD）"
                name={["budget", "maximum"]}
                rules={[
                  { required: true, message: "填写最高周预算" },
                  {
                    validator: (_, v) =>
                      v >= form.getFieldValue(["budget", "preferred"])
                        ? Promise.resolve()
                        : Promise.reject(new Error("最高预算不能低于期望预算")),
                  },
                ]}
              >
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item
                label="计价对象"
                name={["budget", "scope"]}
                rules={[{ required: true }]}
              >
                <Select
                  options={["per_person", "per_room", "whole_property"].map(
                    (value) => ({ value, label: label(value) }),
                  )}
                />
              </Form.Item>
              <Form.Item label="租赁方式" name="rental_mode">
                <Select
                  options={[
                    "private_room",
                    "whole_property",
                    "shared_room",
                    "student_accommodation",
                  ].map((value) => ({ value, label: label(value) }))}
                />
              </Form.Item>
              <Form.Item
                label="居住人数"
                name="occupants"
                rules={[{ required: true }]}
              >
                <InputNumber min={1} precision={0} />
              </Form.Item>
              <div className="switch-group">
                <Form.Item
                  label="预算包含账单"
                  name={["budget", "includes_bills"]}
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
                <Form.Item
                  label="最高预算为硬条件"
                  name={["budget", "hard_limit"]}
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
              </div>
            </div>
          </section>
          <section className="panel">
            <h2>通勤安排</h2>
            <div className="form-grid">
              <Form.Item
                label="目的地标识"
                name="destination_id"
                rules={[{ required: true }]}
                extra="演示目的地：demo-usyd"
              >
                <Input />
              </Form.Item>
              <Form.Item
                label="到达时间（悉尼）"
                name="arrival_time"
                rules={[{ required: true }]}
              >
                <Input type="time" />
              </Form.Item>
              <Form.Item
                label="期望通勤（分钟）"
                name={["commute", "preferred_minutes"]}
                rules={[{ required: true }]}
              >
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item
                label="最长通勤（分钟）"
                name={["commute", "maximum_minutes"]}
                rules={[
                  { required: true },
                  {
                    validator: (_, v) =>
                      v >= form.getFieldValue(["commute", "preferred_minutes"])
                        ? Promise.resolve()
                        : Promise.reject(new Error("最长通勤不能小于期望通勤")),
                  },
                ]}
              >
                <InputNumber min={0} />
              </Form.Item>
            </div>
            <Form.Item
              label="交通方式"
              name={["commute", "modes"]}
              rules={[
                {
                  required: true,
                  type: "array",
                  min: 1,
                  message: "至少选择一种交通方式",
                },
              ]}
            >
              <Checkbox.Group
                options={["public_transport", "walk", "bike", "drive"].map(
                  (value) => ({ value, label: label(value) }),
                )}
              />
            </Form.Item>
            <Form.Item
              label="最长通勤为硬条件"
              name={["commute", "hard_limit"]}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </section>
          <section className="panel">
            <h2>入住与租期</h2>
            <div className="form-grid">
              <Form.Item
                label="最早入住"
                name={["move_in_window", "from"]}
                rules={[{ required: true }]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item
                label="最晚入住"
                name={["move_in_window", "to"]}
                rules={[
                  { required: true },
                  {
                    validator: (_, v) =>
                      v >= form.getFieldValue(["move_in_window", "from"])
                        ? Promise.resolve()
                        : Promise.reject(new Error("最晚入住不能早于最早入住")),
                  },
                ]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item
                label="租期（月）"
                name="lease_months"
                rules={[{ required: true }]}
              >
                <InputNumber min={1} />
              </Form.Item>
            </div>
          </section>
          <section className="panel">
            <h2>硬要求与偏好</h2>
            <Form.Item label="必须满足的设施" name="hard_requirements">
              <Checkbox.Group
                options={facilities.map((value) => ({
                  value,
                  label: label(value),
                }))}
              />
            </Form.Item>
            <p className="muted">
              软偏好权重为 0 表示未指定；硬要求设施不重复参与软偏好计分。
            </p>
            <div className="form-grid">
              {facilities.map((key) => (
                <Form.Item
                  key={key}
                  name={["soft_preferences", key]}
                  label={`${label(key)} · 软偏好`}
                >
                  <InputNumber
                    disabled={profile.hard_requirements?.includes(key)}
                    min={0}
                    step={0.1}
                  />
                </Form.Item>
              ))}
            </div>
            <h3>你更看重什么？</h3>
            <p className="muted">
              四维权重至少一项大于零。后端统一归一化后计算。
            </p>
            {dimensions.map((key) => (
              <Form.Item
                key={key}
                name={["weights", key]}
                label={`${label(key)}权重`}
                dependencies={dimensions
                  .filter((other) => other !== key)
                  .map((other) => ["weights", other])}
                rules={[
                  {
                    required: true,
                    type: "number",
                    min: 0,
                    max: 1,
                    message: "权重须介于 0 和 1 之间",
                  },
                  {
                    validator: () =>
                      key !== "commute" ||
                      dimensions.some(
                        (dimension) =>
                          Number(form.getFieldValue(["weights", dimension])) >
                          0,
                      )
                        ? Promise.resolve()
                        : Promise.reject(new Error("四维权重至少一项大于零")),
                  },
                ]}
              >
                <WeightControl dimension={label(key)} />
              </Form.Item>
            ))}
          </section>
        </Form>
        <aside className="preference-summary">
          <section className="panel">
            <h2>你的偏好摘要</h2>
            <Summary profile={profile} />
            <div className="summary-state">
              {dirty
                ? "有未保存修改"
                : confirmation
                  ? `当前草稿已确认 · v${confirmation.version}`
                  : "当前草稿尚未确认"}
            </div>
            <Space orientation="vertical" className="full-width">
              <Button
                block
                onClick={save}
                loading={action.busy}
                aria-label="保存草稿"
              >
                保存草稿
              </Button>
              <Button
                block
                disabled={dirty || Boolean(confirmation)}
                onClick={confirm}
                loading={action.busy}
                aria-label="确认当前偏好"
              >
                确认当前偏好
              </Button>
              <Button
                block
                type="primary"
                disabled={dirty || !confirmation}
                onClick={evaluate}
                loading={action.busy}
                aria-label="生成推荐"
              >
                生成推荐
              </Button>
            </Space>
            <p className="muted small">
              修改后需先保存草稿，再重新确认。旧确认版本及旧报告会保留。
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}
