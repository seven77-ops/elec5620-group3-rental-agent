import { useEffect, useRef, useState } from "react";
import { Alert, Button, Space } from "antd";
import { newRequestId } from "../../api/client";
import {
  uploadLivingAttachment,
  type LivingAttachment,
} from "../../api/living";
import ReviewEvidence from "./ReviewEvidence";

export interface EvidenceSelection {
  files: LivingAttachment[];
  busy: boolean;
  ready: boolean;
}
export const emptyEvidence: EvidenceSelection = {
  files: [],
  busy: false,
  ready: true,
};
interface Entry {
  id: string;
  file: File;
  saved?: LivingAttachment;
  error?: string;
  uploading?: boolean;
}
export default function ReviewEvidenceUpload({
  caseId,
  onChange,
  disabled = false,
}: {
  caseId: string;
  onChange: (value: EvidenceSelection) => void;
  disabled?: boolean;
}) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const active = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [selectionError, setSelectionError] = useState("");
  useEffect(() => {
    onChange({
      files: entries.flatMap((e) => (e.saved ? [e.saved] : [])),
      busy: entries.some((e) => e.uploading),
      ready: !selectionError && entries.every((e) => Boolean(e.saved)),
    });
  }, [entries, onChange, selectionError]);
  const upload = async (entry: Entry) => {
    setEntries((old) =>
      old.map((e) =>
        e.id === entry.id ? { ...e, error: undefined, uploading: true } : e,
      ),
    );
    try {
      const saved = await uploadLivingAttachment(
        caseId,
        entry.file,
        "moveout",
        null,
        entry.id,
      );
      setEntries((old) =>
        old.map((e) =>
          e.id === entry.id
            ? { ...e, saved, error: undefined, uploading: false }
            : e,
        ),
      );
    } catch (error) {
      setEntries((old) =>
        old.map((e) =>
          e.id === entry.id
            ? {
                ...e,
                error:
                  error instanceof Error
                    ? error.message
                    : "Upload failed. Retry this file.",
                uploading: false,
              }
            : e,
        ),
      );
    }
  };
  const busy = entries.some((e) => e.uploading);
  return (
    <div className="review-evidence-upload">
      <label htmlFor={`review-files-${caseId}`}>
        Evidence files (optional)
      </label>
      <p className="muted small">
        Photos, screenshots or PDF documents. Up to 10 files, 10 MB each.
      </p>
      <Button
        disabled={disabled || busy || entries.length >= 10}
        onClick={() => fileInput.current?.click()}
      >
        Upload files
      </Button>
      <input
        ref={fileInput}
        style={{ display: "none" }}
        id={`review-files-${caseId}`}
        aria-label="Add evidence files"
        type="file"
        multiple
        accept="image/jpeg,image/png,application/pdf"
        disabled={disabled || busy || entries.length >= 10}
        onChange={async (event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (active.current) return;
          if (files.length > 10 - entries.length) {
            setSelectionError("Choose up to 10 files for this report.");
            return;
          }
          setSelectionError("");
          const added = files.map((file) => ({
            id: newRequestId(),
            file,
            uploading: true,
          }));
          setEntries((old) => [...old, ...added]);
          active.current = true;
          try {
            for (const entry of added) await upload(entry);
          } finally {
            active.current = false;
          }
        }}
      />
      {selectionError && (
        <>
          <Alert type="error" title={selectionError} />
          <Button onClick={() => setSelectionError("")}>
            Keep current selection
          </Button>
        </>
      )}
      {entries.map((entry) => (
        <div className="review-upload-entry" key={entry.id}>
          {!entry.saved && (
            <span>
              {entry.file.name}
              {entry.uploading ? " · Uploading…" : ""}
            </span>
          )}
          {entry.error && <Alert type="error" title={entry.error} />}
          {!entry.uploading && (
            <Space wrap>
              {entry.error && (
                <Button
                  disabled={disabled || busy}
                  onClick={() => void upload(entry)}
                >
                  Retry upload
                </Button>
              )}
              <Button
                size="small"
                disabled={disabled || busy}
                onClick={() =>
                  setEntries((old) => old.filter((e) => e.id !== entry.id))
                }
                aria-label={`Remove ${entry.file.name}`}
              >
                Remove
              </Button>
            </Space>
          )}
        </div>
      ))}
      <ReviewEvidence
        files={entries.flatMap((e) => (e.saved ? [e.saved] : []))}
      />
    </div>
  );
}
