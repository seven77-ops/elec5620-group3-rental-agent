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
      <PageTitle
        title="合同助手"
        description="没有合同，先准备草稿；已有合同，上传核对。"
      />
      <Tabs
        activeKey={mode}
        onChange={(key) => setParams({ mode: key })}
        destroyOnHidden
        items={[
          {
            key: "draft",
            label: "生成租约草稿",
            children: (
              <Suspense fallback={<Loading />}>
                <LeaseDraft />
              </Suspense>
            ),
          },
          {
            key: "review",
            label: "上传合同复核",
            children: <Contract embedded />,
          },
        ]}
      />
    </>
  );
}
