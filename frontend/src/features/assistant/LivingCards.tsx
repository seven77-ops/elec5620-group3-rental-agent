import { Space, Tag } from "antd";
import UtilityPlans from "../living/UtilityPlans";
import type { LivingProvider } from "../../api/living";

export default function LivingCards({
  providers,
}: {
  providers: LivingProvider[];
}) {
  return (
    <div className="assistant-listings">
      {providers.map((provider) => (
        <article
          className="assistant-listing"
          key={provider.id}
          data-provider-id={provider.id}
        >
          <Tag color="blue">
            {provider.plans?.length ? "官方套餐参考" : "官方服务入口"}
          </Tag>
          <h3>{provider.name}</h3>
          <p className="muted">{provider.coverage}</p>
          <p>{provider.notes}</p>
          <UtilityPlans plans={provider.plans} />
          <Space wrap>
            <a
              href={provider.website}
              target="_blank"
              rel="noopener noreferrer"
            >
              公司网站 ↗
            </a>
            <a
              href={provider.contact_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              联系 / 询价 ↗
            </a>
            {provider.phone && (
              <a href={`tel:${provider.phone.replace(/[^+0-9]/g, "")}`}>
                {provider.phone}
              </a>
            )}
          </Space>
          <p className="muted small">
            <a
              href={provider.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {provider.plans?.length ? "联系信息来源" : "资料来源"}
            </a>{" "}
            · 核验 {provider.checked_on}
          </p>
        </article>
      ))}
    </div>
  );
}
