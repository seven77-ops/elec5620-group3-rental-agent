import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Form,
  InputNumber,
  Modal,
  Select,
  Spin,
  Typography,
} from "antd";
import type { HousingAd, HousingFilters } from "../../api/catalog";
import type { Conversation, RentalBrief } from "../../api/assistant";
import type { CaseState } from "../../api/types";
import { newRequestId, post } from "../../api/client";
import { commuteModes } from "../real-data/UsydCommute";

export interface SelectionSource {
  conversation_id?: string;
  filters?: HousingFilters;
}
interface Preview {
  listing: HousingAd;
  source: SelectionSource;
  brief: RentalBrief;
  summary: string[];
  missing_fields: string[];
  context_token: string;
}
export interface SelectionResult {
  case: CaseState;
  conversation: Conversation | null;
}
export default function FollowupDialog({
  caseId,
  listing,
  source,
  replacing,
  onClose,
  onSaved,
}: {
  caseId: string;
  listing: HousingAd;
  source: SelectionSource;
  replacing?: string;
  onClose: () => void;
  onSaved: (value: SelectionResult) => Promise<void>;
}) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const [form] = Form.useForm();
  const pending = useRef<object | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    let valid = true;
    setLoading(true);
    void post<Preview>(`/cases/${caseId}/followup-preview`, {
      listing_id: listing.listing_id,
      ...source,
    })
      .then((value) => {
        if (valid) {
          setPreview(value);
          setError(null);
          pending.current = null;
        }
      })
      .catch((e) => {
        if (valid)
          setError(
            e instanceof Error
              ? e.message
              : "Could not load selection criteria.",
          );
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [caseId, listing.listing_id, source, reload]);
  const save = async () => {
    if (!preview || loading || saving) return;
    try {
      const values = preview.missing_fields.length
        ? await form.validateFields()
        : {};
      setSaving(true);
      const supplement = Object.fromEntries(
        preview.missing_fields.map((field) => [field, values[field]]),
      );
      pending.current ??= {
        ...preview.source,
        listing_id: listing.listing_id,
        request_id: newRequestId(),
        context_token: preview.context_token,
        confirmed: true,
        supplement,
      };
      const value = await post<SelectionResult>(
        `/cases/${caseId}/followup-start`,
        pending.current,
      );
      if (alive.current) await onSaved(value);
    } catch (e) {
      if (e && typeof e === "object" && "errorFields" in e) return;
      if (alive.current)
        setError(
          e instanceof Error
            ? e.message
            : "Could not complete selection. Please try again.",
        );
    } finally {
      if (alive.current) setSaving(false);
    }
  };
  const missing = preview?.missing_fields ?? [];
  const currentListing = preview?.listing ?? listing;
  const listingChanged =
    !!preview &&
    (preview.listing.address !== listing.address ||
      preview.listing.weekly_rent !== listing.weekly_rent);
  return (
    <Modal
      title="Select this property and start follow-up?"
      open
      onCancel={() => !saving && onClose()}
      width={560}
      styles={{
        body: { maxHeight: "calc(100dvh - 230px)", overflowY: "auto" },
      }}
      okText={
        error && pending.current
          ? "Retry confirmation and follow-up"
          : "Confirm and start follow-up"
      }
      cancelText="Keep comparing"
      confirmLoading={saving}
      onOk={() => void save()}
      okButtonProps={{ disabled: loading || !preview }}
      cancelButtonProps={{ disabled: saving }}
      closable={!saving}
      mask={{ closable: !saving }}
    >
      <Typography.Title level={5}>{currentListing.address}</Typography.Title>
      <p>
        <strong>AUD {currentListing.weekly_rent}/week</strong>
      </p>
      {listingChanged && (
        <Alert
          type="warning"
          showIcon
          title="Listing details changed. Check the current address and weekly rent before confirming."
        />
      )}
      {loading ? (
        <Spin />
      ) : (
        preview && (
          <>
            <p>
              Start follow-up with your current rental needs. Existing
              recommendations are retained.
            </p>
            <ul className="assistant-proposal-summary">
              {preview.summary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {replacing && (
              <Alert
                type="info"
                title={`This will replace your current follow-up property: ${replacing}.Favorites are retained.`}
              />
            )}
            {!!missing.length && (
              <>
                <p>
                  Complete only the details below. Your existing criteria are
                  retained:
                </p>
                <Form
                  form={form}
                  layout="vertical"
                  disabled={saving || !!pending.current}
                >
                  {missing.includes("budget_period") && (
                    <Form.Item
                      name="budget_period"
                      label="Budget period"
                      rules={[{ required: true }]}
                    >
                      <Select options={[{ value: "week", label: "Weekly" }]} />
                    </Form.Item>
                  )}
                  {missing.includes("budget_scope") && (
                    <Form.Item
                      name="budget_scope"
                      label="Budget pricing basis"
                      rules={[{ required: true }]}
                    >
                      <Select
                        options={[
                          { value: "whole_property", label: "Whole property" },
                          { value: "per_person", label: "Per person" },
                          { value: "per_room", label: "Per room" },
                        ]}
                      />
                    </Form.Item>
                  )}
                  {missing.includes("commute_mode") && (
                    <Form.Item
                      name="commute_mode"
                      label="Commute mode"
                      rules={[{ required: true }]}
                    >
                      <Select options={commuteModes} />
                    </Form.Item>
                  )}
                  {missing.includes("commute_max_minutes") && (
                    <Form.Item
                      name="commute_max_minutes"
                      label="Maximum one-way commute (minutes)"
                      rules={[{ required: true }]}
                    >
                      <InputNumber min={1} max={240} precision={0} />
                    </Form.Item>
                  )}
                </Form>
              </>
            )}
          </>
        )
      )}
      {error && (
        <Alert
          type="error"
          showIcon
          title={error}
          action={
            <Button
              disabled={saving}
              onClick={() => {
                pending.current = null;
                setReload((v) => v + 1);
              }}
            >
              Load latest criteria
            </Button>
          }
        />
      )}
    </Modal>
  );
}
