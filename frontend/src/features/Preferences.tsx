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
    <dl
      className="summary-list"
      tabIndex={0}
      aria-label="Full preference summary"
    >
      <div>
        <dt>Weekly budget</dt>
        <dd>
          {profile.budget?.preferred != null
            ? `Preferred ${money(profile.budget.preferred)}, `
            : ""}
          Maximum {money(profile.budget?.maximum)} /{" "}
          {label(profile.budget?.scope ?? "")}
          <small>
            {profile.budget?.includes_bills == null
              ? "Bills requirement not entered"
              : profile.budget.includes_bills
                ? "Bills included"
                : "Check bills separately"}{" "}
            ·{" "}
            {profile.budget?.hard_limit == null
              ? ""
              : profile.budget.hard_limit
                ? "Maximum budget is a hard requirement"
                : "Maximum budget is a soft limit"}
          </small>
        </dd>
      </div>
      <div>
        <dt>Living arrangements</dt>
        <dd>
          {profile.occupants == null
            ? "Occupant count not entered"
            : `${profile.occupants} occupants`}{" "}
          ·{" "}
          {profile.rental_mode
            ? label(profile.rental_mode)
            : "Rental type not entered"}
        </dd>
      </div>
      {profile.housing_preferences && (
        <div>
          <dt>Housing criteria</dt>
          <dd>
            {profile.housing_preferences.suburb || "Any area"}
            <small>
              At least {profile.housing_preferences.min_bedrooms ?? "Any"} bed ·{" "}
              {profile.housing_preferences.min_bathrooms ?? "Any"} bathrooms ·{" "}
              {profile.housing_preferences.min_car_spaces ?? "Any"} car spaces
            </small>
            <small>
              {profile.housing_preferences.budget_match_mode ===
              "matching_scope"
                ? "Filter budget only for matching pricing basis"
                : "Filter advertised weekly rent by amount; pricing basis needs checking"}
            </small>
          </dd>
        </div>
      )}
      {(profile.commute || profile.destination_id) && (
        <div>
          <dt>Commute</dt>
          <dd>
            Preferred {profile.commute?.preferred_minutes} minutes; maximum{" "}
            {profile.commute?.maximum_minutes} minutes
            <small>
              {profile.destination_id} · {profile.arrival_time} arrival ·{" "}
              {profile.timezone ?? "Australia/Sydney"}
              <br />
              {profile.commute?.modes?.map(label).join(", ")} ·{" "}
              {profile.commute?.hard_limit
                ? "Maximum commute is a hard requirement"
                : "Maximum commute is a soft limit"}
            </small>
          </dd>
        </div>
      )}
      {(profile.move_in_window || profile.lease_months) && (
        <div>
          <dt>Lease term</dt>
          <dd>
            {profile.move_in_window?.from} to {profile.move_in_window?.to}{" "}
            move-in
            <small>{profile.lease_months} months</small>
          </dd>
        </div>
      )}
      <div>
        <dt>Must-haves</dt>
        <dd>
          {profile.hard_requirements?.map(label).join(", ") ||
            (profile.hard_requirements
              ? "No additional facility requirements"
              : "Not entered")}
        </dd>
      </div>
      <div>
        <dt>Facility preferences</dt>
        <dd>
          {Object.entries(profile.soft_preferences ?? {})
            .filter(
              ([k, v]) => v > 0 && !profile.hard_requirements?.includes(k),
            )
            .map(([k, v]) => `${label(k)} ${v}`)
            .join(", ") || "Not specified"}
        </dd>
      </div>
      <div>
        <dt>Relative weights across four dimensions</dt>
        <dd>
          {Object.entries(profile.weights ?? {})
            .map(([k, v]) => `${label(k)} ${v}`)
            .join(" · ")}
        </dd>
      </div>
    </dl>
  );
}
function Agent1Warnings({
  warnings,
  real = false,
}: {
  warnings: string[];
  real?: boolean;
}) {
  if (!warnings.length) return null;
  const additional = warnings.filter(
    (warning) => !warning.startsWith("Agent2 uses fictional listings"),
  );
  return (
    <Alert
      type="warning"
      showIcon
      title={
        real
          ? "Costs, availability and lease term still need verification"
          : "Check service limits before confirming"
      }
      description={
        additional.length
          ? additional.join("; ")
          : real
            ? undefined
            : "Demo listings do not check occupant capacity."
      }
    />
  );
}
export default function Preferences() {
  const { current, config, refresh, go } = useCase();
  const [form] = Form.useForm<Profile>();
  const { modal, message } = App.useApp();
  const [dirty, setDirty] = useState(false);
  const action = useAction();
  const confirmation = currentConfirmation(current);
  const legacy = !current.agent1;
  const values = Form.useWatch([], form) as Profile | undefined;
  const savedProfile = current.requirements_profile ?? current.draft.profile;
  const profile = values ?? savedProfile;
  const save = async () => {
    try {
      const value = await form.validateFields();
      if (
        config.mode !== "real_listings" &&
        Object.values(value.weights ?? {}).every((v) => v === 0)
      ) {
        form.setFields([
          {
            name: ["weights", "commute"],
            errors: [
              "At least one of the four weights must be greater than zero",
            ],
          },
        ]);
        return;
      }
      if (config.mode === "real_listings") {
        value.budget = { currency: "AUD", period: "week", ...value.budget };
        value.housing_preferences = { ...value.housing_preferences };
        for (const key of [
          "suburb",
          "min_bedrooms",
          "min_bathrooms",
          "min_car_spaces",
        ] as const) {
          if (value.housing_preferences[key] == null) {
            if (savedProfile.housing_preferences?.[key] != null)
              value.housing_preferences[key] = null;
            else delete value.housing_preferences[key];
          }
        }
      }
      if (
        value.soft_preferences &&
        Object.values(value.soft_preferences).some((v) => v != null)
      )
        value.soft_preferences = Object.fromEntries(
          Object.entries(value.soft_preferences ?? {}).filter(
            ([key, v]) =>
              !value.hard_requirements?.includes(key) && v != null && v > 0,
          ),
        );
      else delete value.soft_preferences;
      void action.run(async () => {
        await post(`/cases/${current.case_id}/profile-drafts`, {
          expected_revision: current.draft.revision,
          profile: mergeEditableProfile(savedProfile, value),
        });
        await refresh();
        setDirty(false);
        message.success(
          "Draft saved. Confirm current preferences before generating recommendations.",
        );
      });
    } catch {
      /* Form renders field errors. */
    }
  };
  const confirm = () =>
    modal.confirm({
      title: "Confirm current preferences",
      content: (
        <>
          <p>
            You are approving saved draft revision {current.draft.revision}.
          </p>
          <Agent1Warnings
            warnings={current.agent1?.warnings ?? []}
            real={config.mode === "real_listings"}
          />
          <Summary profile={savedProfile} />
        </>
      ),
      okText: "Confirm these criteria",
      cancelText: "Back to review",
      onOk: () =>
        action.run(async () => {
          await post(`/cases/${current.case_id}/profile-confirmations`, {
            draft_revision: current.draft.revision,
            fingerprint: current.draft.fingerprint,
            review_token: current.agent1?.review_token,
          });
          await refresh();
          message.success("Current preferences confirmed.");
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
        title="Rental preferences"
        description="Describe your needs, then confirm the version to use for recommendations."
        extra={
          <Space>
            {config.mode === "real_listings" && (
              <Button onClick={() => go("assistant")}>
                Fill in through chat
              </Button>
            )}
            <span className="revision-label">
              Draft revision {current.draft.revision}
            </span>
          </Space>
        }
      />
      {legacy ? (
        <Alert
          type="info"
          showIcon
          title="Previous preference records are read-only"
          description="Historical records are retained. Create a new case to enter your needs."
        />
      ) : config.mode !== "real_listings" && !current.confirmations.length ? (
        <p className="muted small">
          The initial criteria are examples. Save and confirm your own needs.
        </p>
      ) : null}
      <Failure error={action.error} retry={action.retry} />
      <div className="preference-layout">
        <Form
          form={form}
          disabled={legacy || action.busy}
          name="preferences"
          initialValues={savedProfile}
          layout="vertical"
          onValuesChange={() => setDirty(true)}
          className="preference-form"
          key={current.draft.revision}
        >
          <section className="panel">
            <h2>Budget and living arrangements</h2>
            <div className="form-grid">
              <Form.Item
                label="Preferred weekly budget (AUD)"
                name={["budget", "preferred"]}
                rules={[
                  {
                    required: config.mode !== "real_listings",
                    message: "Enter preferred weekly budget",
                  },
                ]}
              >
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item
                label="Maximum weekly budget (AUD)"
                name={["budget", "maximum"]}
                rules={[
                  { required: true, message: "Enter maximum weekly budget" },
                  {
                    validator: (_, v) =>
                      v == null ||
                      form.getFieldValue(["budget", "preferred"]) == null ||
                      v >= form.getFieldValue(["budget", "preferred"])
                        ? Promise.resolve()
                        : Promise.reject(
                            new Error(
                              "Maximum budget cannot be below the preferred budget",
                            ),
                          ),
                  },
                ]}
              >
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item
                label="Pricing basis"
                name={["budget", "scope"]}
                rules={[{ required: config.mode !== "real_listings" }]}
              >
                <Select
                  options={["per_person", "per_room", "whole_property"].map(
                    (value) => ({ value, label: label(value) }),
                  )}
                />
              </Form.Item>
              <Form.Item label="Rental type" name="rental_mode">
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
                label="Number of occupants"
                name="occupants"
                rules={[{ required: config.mode !== "real_listings" }]}
              >
                <InputNumber min={1} precision={0} />
              </Form.Item>
              <div className="switch-group">
                <Form.Item
                  label="Budget includes bills"
                  name={["budget", "includes_bills"]}
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
                <Form.Item
                  label="Maximum budget is a hard requirement"
                  name={["budget", "hard_limit"]}
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
              </div>
            </div>
          </section>
          {config.mode === "real_listings" && (
            <section className="panel">
              <h2>Housing criteria</h2>
              <p className="muted">
                After saving and confirming, these criteria carry into housing
                recommendations. Empty fields do not restrict results.
              </p>
              <div className="form-grid">
                <Form.Item
                  label="Area"
                  name={["housing_preferences", "suburb"]}
                >
                  <Select
                    aria-label="Preferred area"
                    showSearch
                    allowClear
                    placeholder="Any area"
                    options={
                      config.catalog?.suburbs.map((value) => ({
                        value,
                        label: value,
                      })) ?? []
                    }
                  />
                </Form.Item>
                <Form.Item
                  label="Minimum bedrooms"
                  name={["housing_preferences", "min_bedrooms"]}
                >
                  <InputNumber
                    aria-label="Preferred minimum bedrooms"
                    min={0}
                    max={100}
                    precision={0}
                  />
                </Form.Item>
                <Form.Item
                  label="Minimum bathrooms"
                  name={["housing_preferences", "min_bathrooms"]}
                >
                  <InputNumber
                    aria-label="Preferred minimum bathrooms"
                    min={0}
                    max={100}
                    precision={0}
                  />
                </Form.Item>
                <Form.Item
                  label="Minimum car spaces"
                  name={["housing_preferences", "min_car_spaces"]}
                >
                  <InputNumber
                    aria-label="Preferred minimum car spaces"
                    min={0}
                    max={100}
                    precision={0}
                  />
                </Form.Item>
                <Form.Item
                  label="Budget filtering method"
                  name={["housing_preferences", "budget_match_mode"]}
                  initialValue="advertised_amount"
                >
                  <Select
                    options={[
                      {
                        value: "advertised_amount",
                        label: "Filter weekly rent by budget amount",
                      },
                      {
                        value: "matching_scope",
                        label: "Filter budget only when pricing basis matches",
                      },
                    ]}
                  />
                </Form.Item>
              </div>
              <p className="muted">
                Filtering by amount does not establish that a listing meets a
                per-person or bills-included budget. A 0-bedroom studio counts
                as one open-plan sleeping area; separate bedrooms still need
                verification.
              </p>
            </section>
          )}
          <section className="panel">
            <h2>Commute arrangements</h2>
            <div className="form-grid">
              <Form.Item
                label="Destination ID"
                name="destination_id"
                rules={[{ required: config.mode !== "real_listings" }]}
                extra={
                  config.mode === "real_listings"
                    ? undefined
                    : "Demo destination: demo-usyd"
                }
              >
                <Input />
              </Form.Item>
              <Form.Item
                label="Arrival time (Sydney)"
                name="arrival_time"
                rules={[{ required: config.mode !== "real_listings" }]}
              >
                <Input type="time" />
              </Form.Item>
              <Form.Item
                label="Preferred commute (minutes)"
                name={["commute", "preferred_minutes"]}
                rules={[{ required: config.mode !== "real_listings" }]}
              >
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item
                label="Maximum commute (minutes)"
                name={["commute", "maximum_minutes"]}
                rules={[
                  { required: config.mode !== "real_listings" },
                  {
                    validator: (_, v) =>
                      v == null ||
                      form.getFieldValue(["commute", "preferred_minutes"]) ==
                        null ||
                      v >= form.getFieldValue(["commute", "preferred_minutes"])
                        ? Promise.resolve()
                        : Promise.reject(
                            new Error(
                              "Maximum commute cannot be shorter than the preferred commute",
                            ),
                          ),
                  },
                ]}
              >
                <InputNumber min={0} />
              </Form.Item>
            </div>
            <Form.Item
              label="Travel mode"
              name={["commute", "modes"]}
              rules={[
                {
                  required: config.mode !== "real_listings",
                  type: "array",
                  min: 1,
                  message: "Select at least one travel mode",
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
              label="Maximum commute is a hard requirement"
              name={["commute", "hard_limit"]}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </section>
          <section className="panel">
            <h2>Move-in and lease term</h2>
            <div className="form-grid">
              <Form.Item
                label="Earliest move-in"
                name={["move_in_window", "from"]}
                rules={[{ required: config.mode !== "real_listings" }]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item
                label="Latest move-in"
                name={["move_in_window", "to"]}
                rules={[
                  { required: config.mode !== "real_listings" },
                  {
                    validator: (_, v) =>
                      v == null ||
                      !v ||
                      !form.getFieldValue(["move_in_window", "from"]) ||
                      v >= form.getFieldValue(["move_in_window", "from"])
                        ? Promise.resolve()
                        : Promise.reject(
                            new Error(
                              "Latest move-in cannot be before earliest move-in",
                            ),
                          ),
                  },
                ]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item
                label="Lease term (months)"
                name="lease_months"
                rules={[{ required: config.mode !== "real_listings" }]}
              >
                <InputNumber min={1} />
              </Form.Item>
            </div>
          </section>
          <section className="panel">
            <h2>Requirements and preferences</h2>
            <Form.Item label="Required facilities" name="hard_requirements">
              <Checkbox.Group
                options={facilities.map((value) => ({
                  value,
                  label: label(value),
                }))}
              />
            </Form.Item>
            <p className="muted">
              A preference weight of 0 means unspecified. Required facilities
              are not counted again in preference scoring.
            </p>
            <div className="form-grid">
              {facilities.map((key) => (
                <Form.Item
                  key={key}
                  name={["soft_preferences", key]}
                  label={`${label(key)} · Preferences`}
                >
                  <InputNumber
                    disabled={
                      legacy || profile.hard_requirements?.includes(key)
                    }
                    min={0}
                    step={0.1}
                  />
                </Form.Item>
              ))}
            </div>
            {config.mode !== "real_listings" && (
              <>
                <h3>What matters most to you?</h3>
                <p className="muted">
                  At least one of the four weights must exceed zero. Weights are
                  normalised on the server.
                </p>
                {dimensions.map((key) => (
                  <Form.Item
                    key={key}
                    name={["weights", key]}
                    label={`${label(key)} Weight`}
                    dependencies={dimensions
                      .filter((other) => other !== key)
                      .map((other) => ["weights", other])}
                    rules={[
                      {
                        required: true,
                        type: "number",
                        min: 0,
                        max: 1,
                        message: "Weight must be between 0 and 1",
                      },
                      {
                        validator: () =>
                          key !== "commute" ||
                          dimensions.some(
                            (dimension) =>
                              Number(
                                form.getFieldValue(["weights", dimension]),
                              ) > 0,
                          )
                            ? Promise.resolve()
                            : Promise.reject(
                                new Error(
                                  "At least one of the four weights must be greater than zero",
                                ),
                              ),
                      },
                    ]}
                  >
                    <WeightControl dimension={label(key)} />
                  </Form.Item>
                ))}
              </>
            )}
          </section>
        </Form>
        <aside className="preference-summary">
          <section className="panel">
            <h2>Your preference summary</h2>
            <Agent1Warnings
              warnings={current.agent1?.warnings ?? []}
              real={config.mode === "real_listings"}
            />
            <Summary profile={profile} />
            <div className="summary-state">
              {dirty
                ? "Unsaved changes"
                : confirmation
                  ? `Current draft confirmed · v${confirmation.version}`
                  : "Current draft is not confirmed"}
            </div>
            <Space orientation="vertical" className="full-width">
              <Button
                block
                onClick={save}
                disabled={legacy}
                loading={action.busy}
                aria-label="Save draft"
              >
                Save draft
              </Button>
              <Button
                block
                disabled={
                  legacy ||
                  dirty ||
                  Boolean(confirmation) ||
                  !current.agent1?.review_token
                }
                onClick={confirm}
                loading={action.busy}
                aria-label="Confirm current preferences"
              >
                Confirm current preferences
              </Button>
              <Button
                block
                type="primary"
                disabled={legacy || dirty || !confirmation}
                onClick={evaluate}
                loading={action.busy}
                aria-label="Generate recommendations"
              >
                Generate recommendations
              </Button>
            </Space>
            <p className="muted small">
              After editing, save the draft and confirm again. Previous
              confirmed versions and reports are retained.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}
