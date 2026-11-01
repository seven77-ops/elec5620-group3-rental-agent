import { useCallback, useEffect, useRef, useState } from "react";
import { App, Button, Empty, Tabs } from "antd";
import { getOperatorReviews, type OperatorReview } from "../api/operator";
import { Failure, Loading, PageTitle } from "../components/Common";
import HumanReviewItem from "./aftercare/HumanReviewItem";

export default function Operator() {
  const [items, setItems] = useState<OperatorReview[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState("pending");
  const generation = useRef(0);
  const { message } = App.useApp();
  const load = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true);
    try {
      const result = await getOperatorReviews();
      if (token === generation.current) {
        setItems(result.items);
        setError(null);
        return true;
      }
      return false;
    } catch (error) {
      if (token === generation.current) setError(error);
      return false;
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    return () => {
      generation.current++;
    };
  }, [load]);
  const saved = async () => {
    if (!(await load()))
      throw new Error(
        "Advice was saved. Refresh reports to view the latest queue.",
      );
    setTab("history");
    message.success("Review advice saved.");
  };
  const pending = (items ?? []).filter((item) => item.status === "open");
  const history = (items ?? []).filter((item) => item.status !== "open");
  const list = (records: OperatorReview[], label: string) => (
    <section aria-label={label}>
      {records.length ? (
        records.map((item) => (
          <HumanReviewItem
            key={`${item.kind}:${item.case_id}:${item.review_id}`}
            item={item}
            onSaved={saved}
            onReload={load}
          />
        ))
      ) : (
        <div className="panel">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              label === "Human review queue"
                ? "No reports awaiting review"
                : "No completed reviews yet"
            }
          />
        </div>
      )}
    </section>
  );
  return (
    <>
      <PageTitle
        title="Human review"
        description="Read reports and evidence, then leave your advice."
        extra={
          <Button onClick={() => void load()} loading={loading}>
            Refresh reports
          </Button>
        }
      />
      <Failure error={error} retry={() => void load()} />
      {items === null ? (
        loading ? (
          <Loading />
        ) : null
      ) : (
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: "pending",
              label: `Pending (${pending.length})`,
              children: list(pending, "Human review queue"),
            },
            {
              key: "history",
              label: `History (${history.length})`,
              children: list(history, "Review history"),
            },
          ]}
        />
      )}
    </>
  );
}
