import { useEffect, useRef, useState } from "react";
import { Alert, Button, Checkbox } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { api, newRequestId, post } from "../../api/client";
import { aiPost } from "../../api/ai";
import type { Review } from "../../api/types";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";

export default function ReviewUpload({
  caseId,
  onReviewed,
  onCancel,
}: {
  caseId: string;
  onReviewed: (review: Review, aiFailed: boolean) => Promise<void>;
  onCancel?: () => void;
}) {
  const action = useAction();
  const [file, setFile] = useState<File | null>(null);
  const [allowed, setAllowed] = useState(false);
  const [fileError, setFileError] = useState<string>();
  const [stage, setStage] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const upload = () => {
    if (!file || !allowed) return;
    const chosen = file;
    const uploadId = newRequestId();
    const analysisId = newRequestId();
    let consentId: string | undefined;
    let review: Review | undefined;
    void action.run(async () => {
      if (alive.current) setStage("Uploading contract…");
      if (!consentId) {
        const grant = await post<{ consent_id: string }>(
          `/cases/${caseId}/contract-consents`,
          { confirmed: true, scope: "document" },
        );
        consentId = grant.consent_id;
      }
      if (!review) {
        const saved = await api<{ review: Review }>(
          `/cases/${caseId}/contract-reviews`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/octet-stream",
              "X-Consent-Id": consentId,
              "X-Request-Id": uploadId,
              "X-Filename": encodeURIComponent(chosen.name),
            },
            body: chosen,
          },
        );
        review = saved.review;
      }
      if (alive.current) setStage("Analysing contract…");
      let aiFailed = false;
      try {
        await aiPost(`/contract-reviews/${review.review_id}/ai-analyses`, {
          request_id: analysisId,
          expected_version: review.version,
          allow_external_ai: true,
        });
      } catch {
        // Keep a readable document result even when the optional remote transport fails.
        aiFailed = true;
      }
      if (alive.current) await onReviewed(review, aiFailed);
    });
  };
  return (
    <section
      className="panel simple-contract-upload"
      aria-label="Upload contract for analysis"
    >
      <h2>Upload your contract</h2>
      <p>
        Upload a contract to check its details and see what needs attention.
      </p>
      <Failure
        error={action.error}
        retry={allowed ? action.retry : undefined}
        showDetails={false}
      />
      {fileError && <Alert type="error" title={fileError} showIcon />}
      <input
        ref={input}
        type="file"
        aria-label="Select contract"
        accept=".pdf,.docx,.txt"
        hidden
        disabled={action.busy}
        onChange={(event) => {
          const chosen = event.target.files?.[0] ?? null;
          setAllowed(false);
          action.clear();
          if (chosen && chosen.size > 2_000_000) {
            setFile(null);
            setFileError("Choose a file smaller than 2 MB.");
            event.target.value = "";
            return;
          }
          setFileError(undefined);
          setFile(chosen);
        }}
      />
      <div className="simple-contract-file">
        <Button
          icon={<UploadOutlined />}
          onClick={() => input.current?.click()}
          disabled={action.busy}
        >
          Select contract
        </Button>
        <span>{file?.name ?? "PDF, DOCX or TXT · Up to 2 MB"}</span>
      </div>
      <Checkbox
        checked={allowed}
        disabled={action.busy}
        onChange={(event) => setAllowed(event.target.checked)}
      >
        I am authorised to upload this contract and agree to send it to the AI
        service for review.
      </Checkbox>
      <div className="simple-contract-upload-actions">
        <Button
          type="primary"
          disabled={!file || !allowed}
          loading={action.busy}
          onClick={upload}
        >
          Upload and analyse
        </Button>
        {onCancel && (
          <Button disabled={action.busy} onClick={onCancel}>
            Back to results
          </Button>
        )}
        {action.busy && <span role="status">{stage}</span>}
      </div>
    </section>
  );
}
