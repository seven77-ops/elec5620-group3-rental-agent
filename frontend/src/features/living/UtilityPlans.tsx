import type { UtilityPlan } from "../../api/living";
import "./utilityPlans.css";
const categories = {
  electricity: "Electricity",
  gas: "Gas",
  internet: "Internet",
  water: "Water",
};
const states = {
  current: "Official pricing reference",
  expired: "Expired",
  stale: "Information needs updating",
  not_yet_effective: "Not yet effective",
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
          ? plan.price_summary.split(/[;；]/)[0]
          : plan.price_summary}
      </p>
      <div className="utility-plan-highlights">
        {plan.pricing_lines.slice(1, 3).map((line, i) => (
          <p key={i}>{line}</p>
        ))}
      </div>
      <details className="utility-plan-details">
        <summary>Pricing details and eligibility</summary>
        {compact && energy && <p>{plan.price_summary}</p>}
        {plan.pricing_lines.slice(3).map((line, i) => (
          <p key={i}>{line}</p>
        ))}
        {plan.pricing.technology?.length ? (
          <p>
            Applicable connection technology:{" "}
            {plan.pricing.technology.join(" / ")}
          </p>
        ) : null}
        <ul>
          {plan.conditions.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
        {!!plan.pricing.fees?.length && (
          <p>
            Other charges:
            {plan.pricing.fees
              .map((f) => `${f.type}${f.amount ? ` AUD ${f.amount}` : ""}`)
              .join("; ")}
            . Check triggering conditions and tax details. These are excluded
            from the base cost.
          </p>
        )}
        {plan.external_plan_id && (
          <p>Official plan ID: {plan.external_plan_id.split("@")[0]}</p>
        )}
        <p>
          Confirm building connectivity, account eligibility, and the final
          quote with the provider.
        </p>
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
        Official plans and rates ↗
      </a>
      {plan.pricing.tenancy_source_url && (
        <a
          href={plan.pricing.tenancy_source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          NSW utility cost responsibilities ↗
        </a>
      )}
      <span>
        Collected {plan.observed_at.slice(0, 10)}
        {plan.valid_to ? ` · Valid until ${plan.valid_to.slice(0, 10)}` : ""}
      </span>
    </div>
  );
}
export default function UtilityPlans({ plans }: { plans?: UtilityPlan[] }) {
  if (!plans?.length) return null;
  return (
    <section className="utility-plan-list" aria-label="Plans and pricing">
      {plans.slice(0, 2).map((plan) => (
        <UtilityPlanCard key={plan.id} plan={plan} />
      ))}
      {plans.length > 2 && (
        <details className="utility-plan-more">
          <summary>View remaining {plans.length - 2} plans / tariffs</summary>
          {plans.slice(2).map((plan) => (
            <UtilityPlanCard key={plan.id} plan={plan} />
          ))}
        </details>
      )}
    </section>
  );
}
