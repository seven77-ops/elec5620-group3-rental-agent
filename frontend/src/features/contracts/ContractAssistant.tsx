import KnowledgePanel from "../knowledge/KnowledgePanel";
import { lazy, Suspense } from "react";
import { Tabs } from "antd";
import { useSearchParams } from "react-router-dom";
import { useCase } from "../../app/context";
import { PageTitle, Loading } from "../../components/Common";
import Contract from "../Contract";
const LeaseDraft = lazy(() => import("./LeaseDraft"));
export default function ContractAssistant() {
  const { config, current } = useCase();
  const [params, setParams] = useSearchParams();
  if (config.mode !== "real_listings") return <Contract />;
  const mode = ["draft", "review"].includes(params.get("mode") ?? "")
    ? params.get("mode")!
    : current.reviews.length
      ? "review"
      : "draft";
  return (
    <>
      <PageTitle title="Contract assistant" extra={<KnowledgePanel />} />
      <Tabs
        activeKey={mode}
        onChange={(key) => setParams({ mode: key })}
        destroyOnHidden
        items={[
          {
            key: "draft",
            label: "Generate lease draft",
            children: (
              <Suspense fallback={<Loading />}>
                <LeaseDraft />
              </Suspense>
            ),
          },
          {
            key: "review",
            label: "Upload contract for review",
            children: <Contract embedded />,
          },
        ]}
      />
    </>
  );
}
