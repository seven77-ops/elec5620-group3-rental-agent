import { useEffect, useState } from "react";
import { Alert, Descriptions, Select } from "antd";
import { api } from "../api/client";
import type { Review } from "../api/types";
import {
  EvidenceDrawer,
  Failure,
  JsonDetails,
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
        description="Saved field corrections, human decisions, and generated questions are preserved separately. Historical questions are no longer current."
      />
      <Failure error={error} />
      <Select
        className="full-width"
        aria-label="Select review snapshot"
        value={chosen}
        onChange={setChosen}
        options={history.map((h, i) => ({
          value: h.snapshot_id,
          label: `Record ${i + 1} · Field version v${h.review.version} · ${h.review.status}`,
        }))}
      />
      {snapshot && (
        <>
          <h3>
            <Status value={snapshot.status} />
            Field version v{snapshot.version}
          </h3>
          <Descriptions
            column={1}
            items={Object.entries(snapshot.fields).map(([key, f]) => ({
              key,
              label: label(key),
              children: text(f.value),
            }))}
          />
          <h3>Findings and questions at the time</h3>
          <JsonDetails
            value={{
              findings: snapshot.findings,
              questions: snapshot.questions,
            }}
          />
          <h3>Version evidence</h3>
          <JsonDetails
            value={{
              snapshot_id: chosen,
              events: snapshot.events,
              revisions: snapshot.revisions,
            }}
          />
        </>
      )}
    </EvidenceDrawer>
  );
}
