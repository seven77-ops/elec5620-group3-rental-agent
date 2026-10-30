import { useEffect, useState } from "react";
import { Button, Modal, Spin } from "antd";
import { downloadUrl } from "../../api/client";
import { leaseRoot } from "../../api/leaseDraft";
import type { LeaseDraft } from "../../api/leaseDraft";
import { Failure } from "../../components/Common";

/** Displays one immutable saved version; opening a preview never saves fields. */
export default function LeasePdfPreview({
  draft,
  onClose,
}: {
  draft: LeaseDraft;
  onClose: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const endpoint = downloadUrl(
    leaseRoot(draft.case_id) +
      `/${encodeURIComponent(draft.draft_id)}/pdf?version=${draft.version}`,
  );
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let resource: string | undefined;
    setUrl(null);
    setError(null);
    setLoading(true);
    const deadline = window.setTimeout(() => controller.abort(), 30_000);
    void (async () => {
      try {
        const response = await fetch(endpoint, { signal: controller.signal });
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(
            body?.error?.message ??
              "Contract preview unavailable. Please retry.",
          );
        }
        const blob = await response.blob();
        if (
          !response.headers.get("content-type")?.includes("application/pdf") ||
          (await blob.slice(0, 5).text()) !== "%PDF-"
        )
          throw new Error(
            "The returned file is not a valid PDF. Reload the preview.",
          );
        if (active) {
          resource = URL.createObjectURL(blob);
          setUrl(resource);
        }
      } catch (e) {
        if (active)
          setError(
            controller.signal.aborted
              ? new Error("Contract preview timed out. Please retry.")
              : e,
          );
      } finally {
        window.clearTimeout(deadline);
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(deadline);
      if (resource) URL.revokeObjectURL(resource);
    };
  }, [endpoint, attempt]);
  return (
    <Modal
      open
      title={`Contract preview · v${draft.version}`}
      onCancel={onClose}
      width={1040}
      className="lease-pdf-modal"
      footer={[
        <Button key="back" onClick={onClose}>
          Return to form
        </Button>,
        <Button key="download" type="primary" href={endpoint}>
          Download this PDF version
        </Button>,
      ]}
    >
      <p className="muted small">
        Confirmed details have been entered in the official NSW template.
        Missing items and signature fields remain blank.
      </p>
      <Failure error={error} />
      {Boolean(error) && (
        <Button onClick={() => setAttempt((v) => v + 1)}>Reload preview</Button>
      )}
      {loading && (
        <div className="lease-pdf-loading" role="status">
          <Spin />
          <span>Filling and loading contract…</span>
        </div>
      )}
      {url && (
        <iframe
          src={`${url}#view=FitH`}
          title={`Completed contract draft v${draft.version}`}
          className="lease-pdf-frame"
        />
      )}
      <p className="muted small">
        Unsigned draft · Download the PDF if your browser cannot display it.
      </p>
    </Modal>
  );
}
