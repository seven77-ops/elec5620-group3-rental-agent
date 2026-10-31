import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Checkbox, Space } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useCase, currentConfirmation } from "../app/context";
import { api, downloadUrl, newRequestId, post } from "../api/client";
import type { Review } from "../api/types";
import { Failure } from "../components/Common";
import { contractProcessingScope } from "./contracts/contractProcessingScope";
import { useAction } from "../components/useAction";
export default function ContractUpload({
  onReview,
  onConsentChange,
  revision,
}: {
  onReview: (r: Review) => void;
  onConsentChange: () => void;
  revision: number;
}) {
  const { current, config, refresh } = useCase();
  const { message } = App.useApp();
  const action = useAction();
  const [consentCheck, setConsentCheck] = useState(false);
  const [consent, setConsent] = useState<string | null>(null);
  const [synthetic, setSynthetic] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const input = useRef<HTMLInputElement>(null);
  const real = current.selection?.data_mode === "real_listings";
  const {
    scope,
    allowed: selectionCurrent,
    synthetic: syntheticOnly,
  } = contractProcessingScope(
    current.selection,
    currentConfirmation(current)?.version,
  );
  const actualContract = !syntheticOnly;
  useEffect(() => {
    let valid = true;
    setLoading(true);
    api<{
      consents: {
        consent_id: string;
        active: boolean;
        selection_current: boolean;
        scope?: "selection" | "document";
      }[];
    }>(`/cases/${current.case_id}/contract-consents`)
      .then((r) => {
        if (valid) {
          setConsent(
            r.consents
              .filter(
                (c) =>
                  c.active &&
                  c.selection_current &&
                  (c.scope ?? "selection") === scope,
              )
              .at(-1)?.consent_id ?? null,
          );
          setLoadError(null);
        }
      })
      .catch((e) => {
        if (valid) setLoadError(e);
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [current.case_id, current.selection, revision, scope]);
  const agree = () =>
    void action.run(async () => {
      const r = await post<{ consent_id: string }>(
        `/cases/${current.case_id}/contract-consents`,
        { confirmed: true, scope },
      );
      setConsent(r.consent_id);
      onConsentChange();
      message.success(
        actualContract
          ? "Contract processing consent recorded. You can now select a contract."
          : "Contract processing consent recorded. You can now select a synthetic contract.",
      );
    });
  const revoke = () => {
    const id = consent;
    void action.run(async () => {
      await post(`/cases/${current.case_id}/contract-consents`, {
        confirmed: false,
        consent_id: id,
      });
      setConsent(null);
      setConsentCheck(false);
      setFile(null);
      if (input.current) input.current.value = "";
      onConsentChange();
      message.success("Consent for further contract processing revoked.");
    });
  };
  const upload = () => {
    if (!file || !consent) return;
    const chosen = file,
      consentId = consent,
      requestId = newRequestId();
    void action.run(async () => {
      const r = await api<{ review: Review; newly_created: boolean }>(
        `/cases/${current.case_id}/contract-reviews`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-Consent-Id": consentId,
            "X-Request-Id": requestId,
            "X-Filename": encodeURIComponent(chosen.name),
          },
          body: chosen,
        },
      );
      onReview(r.review);
      await refresh();
      onConsentChange();
      message.success(
        r.newly_created
          ? "Contract review results saved."
          : "Review results from the original request restored.",
      );
    });
  };
  return (
    <section className="panel upload-panel">
      <h2>Upload your contract</h2>
      <p className="muted">
        Upload a PDF, Word document or text file. We will highlight key details
        and items that need checking. AI assistance is optional.
      </p>
      <Failure
        error={action.error || loadError}
        retry={loadError ? onConsentChange : action.retry}
        showDetails={false}
      />
      {loading ? (
        <p role="status">Checking your permission…</p>
      ) : !consent ? (
        <>
          <Checkbox
            checked={consentCheck}
            onChange={(e) => setConsentCheck(e.target.checked)}
          >
            {scope === "document"
              ? "I agree to process this uploaded contract independently, without linking it to a property."
              : "I agree to process this contract for this review and understand this consent is separate from property selection."}
          </Checkbox>
          <div className="consent-actions">
            <Button
              type="primary"
              aria-label="Agree to process this contract"
              disabled={
                !consentCheck || !selectionCurrent || Boolean(loadError)
              }
              loading={action.busy}
              onClick={agree}
            >
              Agree to process this contract
            </Button>
          </div>
        </>
      ) : (
        <>
          <Alert
            type="success"
            showIcon
            title="Ready to upload"
            action={
              <Button size="small" disabled={action.busy} onClick={revoke}>
                Revoke consent
              </Button>
            }
          />
          <div className="upload-controls">
            <input
              ref={input}
              type="file"
              aria-label={
                actualContract ? "Select contract" : "Select synthetic contract"
              }
              accept=".txt,.docx,.pdf"
              disabled={action.busy}
              onChange={(e) => {
                const chosen = e.target.files?.[0] ?? null;
                if (chosen && chosen.size > 2_000_000) {
                  message.error(
                    "The file exceeds 2,000,000 bytes. Please provide a smaller contract file.",
                  );
                  e.target.value = "";
                  return;
                }
                setFile(chosen);
              }}
            />
            <Button
              aria-label={
                actualContract
                  ? "Choose contract file"
                  : "Choose synthetic contract file"
              }
              icon={<UploadOutlined />}
              onClick={() => input.current?.click()}
              disabled={action.busy}
            >
              {actualContract ? "Select contract" : "Select synthetic contract"}
            </Button>
            <span className="break-word">
              {file?.name ?? "No file selected"}
            </span>
          </div>
          <Checkbox
            checked={synthetic}
            onChange={(e) => setSynthetic(e.target.checked)}
          >
            {actualContract
              ? "I confirm I am authorised to submit this contract for review."
              : "I confirm this is a synthetic demo contract."}
          </Checkbox>
          <div className="consent-actions">
            <Button
              type="primary"
              aria-label="Upload and review"
              disabled={!file || !synthetic || !selectionCurrent}
              onClick={upload}
              loading={action.busy}
            >
              Upload and review
            </Button>
          </div>
        </>
      )}
      <p className="muted small">
        PDF, DOCX or TXT · Up to 2 MB · {real ? 30 : 10} pages for text PDFs.
        Scanned PDFs: up to 10 pages; clear text works best.
      </p>
      {syntheticOnly && (
        <Space wrap>
          <span className="muted">Download synthetic samples:</span>
          {config.agreement_examples.map((e) => (
            <a key={e.id} href={downloadUrl(`/demo-agreements/${e.id}`)}>
              {e.id === "normal"
                ? "Standard contract"
                : "Rent conflict contract"}
            </a>
          ))}
        </Space>
      )}
    </section>
  );
}
