import type { UtilityPlan } from "../../api/living";
import "./utilityPlans.css";
const categories = {
  electricity: "电力",
  gas: "燃气",
  internet: "网络",
  water: "供水",
};
const states = {
  current: "官方价格参考",
  expired: "已过有效期",
  stale: "资料待更新",
  not_yet_effective: "尚未生效",
};
export function UtilityPlanCard({
  plan,
  compact = false,
}: {
  plan: UtilityPlan;
  compact?: boolean;
}) {
  const energy = plan.category === "electricity" || plan.category === "gas";
  return (
    <article
      className={`utility-plan${compact ? " is-compact" : ""}`}
      data-plan-id={plan.id}
    >
      <div className="utility-plan-heading">
        <span>{categories[plan.category]}</span>
        <span>{states[plan.status]}</span>
      </div>
      <h4>{plan.name}</h4>
      {plan.network_label && (
        <p className="utility-plan-network">{plan.network_label}</p>
      )}
      <p
        className={`utility-plan-price${compact && energy ? " is-energy" : ""}`}
      >
        {compact && energy
          ? plan.price_summary.split("；")[0]
          : plan.price_summary}
      </p>
      <div className="utility-plan-highlights">
        {plan.pricing_lines.slice(1, 3).map((line, i) => (
          <p key={i}>{line}</p>
        ))}
      </div>
      <details className="utility-plan-details">
        <summary>计价详情与适用条件</summary>
        {compact && energy && <p>{plan.price_summary}</p>}
        {plan.pricing_lines.slice(3).map((line, i) => (
          <p key={i}>{line}</p>
        ))}
        {plan.pricing.technology?.length ? (
          <p>适用接入技术：{plan.pricing.technology.join(" / ")}</p>
        ) : null}
        <ul>
          {plan.conditions.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
        {!!plan.pricing.fees?.length && (
          <p>
            其他费用项目：
            {plan.pricing.fees
              .map((f) => `${f.type}${f.amount ? ` AUD ${f.amount}` : ""}`)
              .join("；")}
            。按发生条件及税费说明核对，未计入基础费用。
          </p>
        )}
        {plan.external_plan_id && (
          <p>官方方案编号：{plan.external_plan_id.split("@")[0]}</p>
        )}
        <p>具体楼栋接入、开户资格和最终报价仍需向供应商确认。</p>
        {compact && <PlanSources plan={plan} />}
      </details>
      {!compact && <PlanSources plan={plan} />}
    </article>
  );
}
function PlanSources({ plan }: { plan: UtilityPlan }) {
  return (
    <div className="utility-plan-sources">
      <a href={plan.source_url} target="_blank" rel="noopener noreferrer">
        官方套餐与费率 ↗
      </a>
      {plan.pricing.tenancy_source_url && (
        <a
          href={plan.pricing.tenancy_source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          NSW费用责任说明 ↗
        </a>
      )}
      <span>
        采集 {plan.observed_at.slice(0, 10)}
        {plan.valid_to ? ` · 有效至 ${plan.valid_to.slice(0, 10)}` : ""}
      </span>
    </div>
  );
}
export default function UtilityPlans({ plans }: { plans?: UtilityPlan[] }) {
  if (!plans?.length) return null;
  return (
    <section className="utility-plan-list" aria-label="套餐与计价">
      {plans.slice(0, 2).map((plan) => (
        <UtilityPlanCard key={plan.id} plan={plan} />
      ))}
      {plans.length > 2 && (
        <details className="utility-plan-more">
          <summary>查看其余 {plans.length - 2} 个套餐 / 费率方案</summary>
          {plans.slice(2).map((plan) => (
            <UtilityPlanCard key={plan.id} plan={plan} />
          ))}
        </details>
      )}
    </section>
  );
}
