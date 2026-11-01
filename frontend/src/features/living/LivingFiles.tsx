import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Select, Space, Tag, Upload } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { getLivingAttachments, uploadLivingAttachment } from "../../api/living";
import type { LivingAttachment, LivingRecord } from "../../api/living";
import { newRequestId } from "../../api/client";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";
const purposes: Record<LivingAttachment["purpose"], string> = {
  repair: "Repair photos or documents",
  receipt: "Receipt",
  moveout: "Move-out documents",
};
const allowedTypes = new Set(["image/jpeg", "image/png", "application/pdf"]);
export default function LivingFiles({
  caseId,
  repairs,
}: {
  caseId: string;
  repairs: LivingRecord["repairs"];
}) {
  const [items, setItems] = useState<LivingAttachment[]>([]),
    [file, setFile] = useState<File | null>(null);
  const [purpose, setPurpose] = useState<LivingAttachment["purpose"]>("repair"),
    [repairId, setRepairId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState<unknown>(null);
  const generation = useRef(0),
    action = useAction();
  const load = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getLivingAttachments(caseId);
      if (generation.current === token) setItems(result.items);
    } catch (error) {
      if (generation.current === token) setError(error);
    } finally {
      if (generation.current === token) setLoading(false);
    }
  }, [caseId]);
  useEffect(() => {
    setFile(null);
    setRepairId(null);
    setPurpose("repair");
    setItems([]);
    action.clear();
    void load();
    return () => {
      generation.current++;
    };
  }, [load]);
  const upload = () => {
    if (!file || action.busy || loading || action.error) return;
    const token = generation.current,
      requestId = newRequestId(),
      chosen = file,
      chosenPurpose = purpose,
      chosenRepair = repairId;
    void action.run(async () => {
      try {
        await uploadLivingAttachment(
          caseId,
          chosen,
          chosenPurpose,
          chosenRepair,
          requestId,
        );
        if (generation.current !== token) return;
        const result = await getLivingAttachments(caseId);
        if (generation.current !== token) return;
        setItems(result.items);
        setFile(null);
        setError(null);
      } catch (error) {
        if (generation.current === token) throw error;
      }
    });
  };
  const frozen = action.busy || Boolean(action.error);
  return (
    <section
      className="living-files living-section"
      aria-label="Photo and receipt attachments"
    >
      <div className="living-section-heading">
        <div>
          <h2>Photos and receipts</h2>
        </div>
        <Button
          aria-label="Load attachments"
          loading={loading}
          disabled={action.busy}
          onClick={() => {
            action.clear();
            void load();
          }}
        >
          Load attachments
        </Button>
      </div>
      {Boolean(error || action.error) && (
        <>
          <Failure error={error || action.error} />
          {Boolean(action.error) && (
            <Space wrap>
              <Button
                aria-label="Retry original file upload"
                loading={action.busy}
                onClick={() => void action.retry()}
              >
                Retry original file upload
              </Button>
              <Button disabled={action.busy} onClick={() => action.clear()}>
                Cancel this upload
              </Button>
            </Space>
          )}
        </>
      )}
      <div className="living-file-controls">
        <label htmlFor="living-file-purpose">Attachment purpose</label>
        <Select
          id="living-file-purpose"
          aria-label="Attachment purpose"
          value={purpose}
          disabled={frozen}
          onChange={setPurpose}
          options={Object.entries(purposes).map(([value, label]) => ({
            value,
            label,
          }))}
        />
        <label htmlFor="living-file-repair">Link repair (optional)</label>
        <Select
          id="living-file-repair"
          aria-label="Link repair (optional)"
          value={repairId}
          disabled={frozen}
          allowClear
          placeholder="Do not link a specific repair"
          onChange={(id) => setRepairId(id || null)}
          options={repairs.map((repair) => ({
            value: repair.repair_id,
            label: repair.title,
          }))}
        />
      </div>
      <Space wrap>
        <Upload
          accept=".jpg,.jpeg,.png,.pdf"
          multiple={false}
          maxCount={1}
          showUploadList={false}
          disabled={frozen}
          beforeUpload={(candidate) => {
            if (!allowedTypes.has(candidate.type)) {
              setFile(null);
              setError("Choose a JPEG, PNG, or PDF file.");
              return false;
            }
            if (candidate.size === 0 || candidate.size > 10 * 1024 * 1024) {
              setFile(null);
              setError("Choose a non-empty file no larger than 10 MiB.");
              return false;
            }
            setFile(candidate);
            setError(null);
            return false;
          }}
        >
          <Button
            aria-label="Choose photo or PDF"
            icon={<UploadOutlined aria-hidden="true" />}
            disabled={frozen}
          >
            Choose photo or PDF
          </Button>
        </Upload>
        <Button
          type="primary"
          aria-label="Upload and save attachment"
          disabled={!file || frozen || loading}
          loading={action.busy}
          onClick={upload}
        >
          Upload and save attachment
        </Button>
      </Space>
      {file && (
        <p className="living-file-picked">
          Ready to upload: {file.name} · {(file.size / 1024).toFixed(1)} KiB{" "}
          <Button
            size="small"
            type="text"
            disabled={frozen}
            onClick={() => setFile(null)}
          >
            Remove selected file
          </Button>
        </p>
      )}
      <p className="living-note">
        JPEG, PNG, and PDF supported, up to 10 MiB each. Select a file and then
        upload it. Files are not sent to an agent, provider, or AI.
      </p>
      {!items.length && !loading && (
        <p className="muted small">No attachments uploaded yet.</p>
      )}
      <div className="living-attachment-list">
        {items.map((item) => (
          <article key={item.attachment_id} className="living-attachment">
            <div>
              <a
                href={item.download_url}
                download={item.filename}
                aria-label={`Download ${item.filename}`}
              >
                {item.filename}
              </a>
              <p>
                {purposes[item.purpose]} · {(item.size_bytes / 1024).toFixed(1)}{" "}
                KiB · {new Date(item.created_at).toLocaleString("en-AU")}
              </p>
              {item.repair_id && (
                <small>
                  Linked repair:
                  {repairs.find((repair) => repair.repair_id === item.repair_id)
                    ?.title || "Repair record"}
                </small>
              )}
            </div>
            <Tag>Uploaded by user · Unverified</Tag>
          </article>
        ))}
      </div>
    </section>
  );
}
