import { useState } from "react";
import { Button, Empty, Input, Pagination, Select, Tabs } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import type { Utility, UtilityPlan } from "../../api/living";
import { UtilityPlanCard } from "./UtilityPlans";
import "./utilityPlanBrowser.css";

const categories: Record<Utility, string> = {
  electricity: "Electricity",
  gas: "Gas",
  internet: "Internet",
  water: "Water",
};
const pageSize = 4;

export default function UtilityPlanBrowser({
  plans,
}: {
  plans: UtilityPlan[];
}) {
  const [category, setCategory] = useState<Utility | "all">("all");
  const [network, setNetwork] = useState("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const categoryPlans = plans.filter(
    (p) => category === "all" || p.category === category,
  );
  const networks = [
    ...new Set(categoryPlans.map((p) => p.network_label).filter(Boolean)),
  ];
  const term = query.trim().toLocaleLowerCase();
  const matching = categoryPlans.filter(
    (p) =>
      (network === "all" || p.network_label === network) &&
      (!term ||
        `${p.name} ${p.network_label}`.toLocaleLowerCase().includes(term)),
  );
  const reset = () => {
    setCategory("all");
    setNetwork("all");
    setQuery("");
    setPage(1);
  };
  const items = [
    { key: "all", label: `All (${plans.length})` },
    ...Object.entries(categories)
      .filter(([key]) => plans.some((p) => p.category === key))
      .map(([key, label]) => ({
        key,
        label: `${label} (${plans.filter((p) => p.category === key).length})`,
      })),
  ];
  return (
    <section className="provider-plan-browser" aria-label="Plans and pricing">
      {items.length > 2 && (
        <Tabs
          activeKey={category}
          items={items}
          onChange={(key) => {
            setCategory(key as Utility | "all");
            setNetwork("all");
            setPage(1);
          }}
        />
      )}
      <div className="provider-plan-toolbar">
        <Input
          aria-label="Search plans"
          prefix={<SearchOutlined />}
          placeholder="Search plan name or network"
          allowClear
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
        />
        {networks.length > 1 && (
          <Select
            aria-label="Filter network"
            value={network}
            options={[
              { value: "all", label: "All networks" },
              ...networks.map((value) => ({ value, label: value })),
            ]}
            onChange={(value) => {
              setNetwork(value);
              setPage(1);
            }}
          />
        )}
      </div>
      <div className="provider-plan-results">
        <span>
          Total <strong>{matching.length}</strong> plans
        </span>
        {(category !== "all" || network !== "all" || query) && (
          <Button type="link" size="small" onClick={reset}>
            Reset filters
          </Button>
        )}
      </div>
      {categoryPlans.some(
        (p) => p.category === "electricity" || p.category === "gas",
      ) &&
        categoryPlans
          .filter((p) => p.category === "electricity" || p.category === "gas")
          .every((p) => p.pricing.gst_basis === "inclusive_10_percent") && (
          <p className="provider-energy-note">
            Energy rates include GST and show base prices before discounts.
            Different networks and billing methods are shown separately.
          </p>
        )}
      {matching.length ? (
        <>
          <div className="provider-plan-grid">
            {matching
              .slice((page - 1) * pageSize, page * pageSize)
              .map((plan) => (
                <UtilityPlanCard key={plan.id} plan={plan} compact />
              ))}
          </div>
          <div
            className="provider-plan-pagination"
            aria-label="Plan pagination"
          >
            <Pagination
              current={page}
              total={matching.length}
              pageSize={pageSize}
              showSizeChanger={false}
              hideOnSinglePage
              size="small"
              responsive
              onChange={setPage}
            />
          </div>
        </>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="No plans match the filters"
        >
          <Button onClick={reset}>Clear filters</Button>
        </Empty>
      )}
    </section>
  );
}
