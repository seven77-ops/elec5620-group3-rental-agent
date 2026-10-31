import { useEffect, useState } from "react";
import { Alert, Descriptions, Select } from "antd";
import { api } from "../api/client";
import type { Review } from "../api/types";
import {
  EvidenceDrawer,
  Failure,
  label,
  Status,
  text,
} from "../components/Common";
export default function ReviewHistory({
  reviewId,
  open,
  onClose,
}: {
  reviewId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<
    { snapshot_id: string; review: Review }[]
  >([]);
  const [chosen, setChosen] = useState<string>();
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!open) return;
    let valid = true;
    setHistory([]);
    setError(null);
    api<{ history: { snapshot_id: string; review: Review }[] }>(
      `/contract-reviews/${reviewId}/history`,
    )
      .then((r) => {
        if (valid) {
          setHistory(r.history);
          setChosen(r.history.at(-1)?.snapshot_id);
        }
      })
      .catch((e) => {
        if (valid) setError(e);
      });
    return () => {
      valid = false;
    };
  }, [reviewId, open]);
  const snapshot = history.find((h) => h.snapshot_id === chosen)?.review;
  return (
    <EvidenceDrawer title="Review history" open={open} onClose={onClose}>
      <Alert
        type="info"
        title="Historical snapshots are read-only"
        description="See earlier saved reviews and their findings here. Return to the current review before making changes."
      />
      <Failure error={error} showDetails={false} />
      <Select
        className="full-width"
        aria-label="Select review snapshot"
        value={chosen}
        onChange={setChosen}
        options={history.map((h, i) => ({
          value: h.snapshot_id,
          label: `Record ${i + 1} · Version ${h.review.version} · ${h.review.status}`,
        }))}
      />
      {snapshot && (
        <>
          <h3>
            <Status value={snapshot.status} />
            Version {snapshot.version}
          </h3>
          <Descriptions
            column={1}
            items={Object.entries(snapshot.fields).map(([key, f]) => ({
              key,
              label: label(key),
              children: text(f.value),
            }))}
          />
          <h3>Items to check at the time</h3>
          {snapshot.findings.length ? (
            snapshot.findings.map((finding, index) => (
              <article className="finding" key={index}>
                <strong>{text(finding.title)}</strong>
                <p>{text(finding.reason)}</p>
              </article>
            ))
          ) : (
            <p>No issues were listed in this saved review.</p>
          )}
          {Array.isArray(snapshot.questions) &&
            snapshot.questions.length > 0 && (
              <>
                <h3>Questions prepared at the time</h3>
                {snapshot.questions.map((question, index) => (
                  <p key={index}>{text(question.text)}</p>
                ))}
              </>
            )}
        </>
      )}
    </EvidenceDrawer>
  );
}
