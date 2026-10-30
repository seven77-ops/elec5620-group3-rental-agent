import { App, Button, Input, Tag } from "antd";
import {
  CheckCircleOutlined,
  QuestionCircleOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import type { AssistantMessage } from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import {
  housingCopy,
  recommendationCopy,
} from "../real-data/listingPresentation";
import "./taskResults.css";
import ListingActions from "../favorites/ListingActions";

function Points({ label, items }: { label: string; items: string[] }) {
  return items.length ? (
    <div className="task-points">
      <strong>{label}</strong>
      <ul>
        {items.map((text, i) => (
          <li key={i}>{recommendationCopy(text)}</li>
        ))}
      </ul>
    </div>
  ) : null;
}
export default function TaskResults({
  message,
  onView,
  onSave,
  disabled,
}: {
  message: AssistantMessage;
  onView?: (listing: HousingAd) => void;
  onSave?: (listing: HousingAd) => void;
  disabled?: boolean;
}) {
  const { message: toast } = App.useApp();
  const comparison = message.comparison,
    enquiry = message.enquiry,
    checks = message.verification_checklist;
  const sharedChecks =
    comparison?.items[0]?.to_verify.filter((text) =>
      comparison.items.every((item) => item.to_verify.includes(text)),
    ) ?? [];
  const extraChecks =
    checks?.items.filter((text) => !sharedChecks.includes(text)) ?? [];
  return (
    <div className="assistant-task-results">
      {message.task_steps?.length ? (
        <ol className="task-steps" aria-label="This task">
          {message.task_steps.map((step, index) => (
            <li key={index}>
              {step.status === "completed" ? (
                <CheckCircleOutlined />
              ) : (
                <QuestionCircleOutlined />
              )}
              <div>
                <strong>{step.label}</strong>
                <small>{housingCopy(step.detail)}</small>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
      {comparison && (
        <section
          className="task-result-card"
          aria-label="Personalised housing comparison"
        >
          <h3>Compared against your needs</h3>
          <p className="muted small">{housingCopy(comparison.basis)}</p>
          <p>{recommendationCopy(comparison.summary)}</p>
          <div className="task-comparison-grid">
            {comparison.items.map((item) => {
              const listing = message.listings.find(
                (row) => row.listing_id === item.listing_id,
              );
              return (
                <article key={item.listing_id} className="task-comparison-item">
                  {comparison.recommended_listing_id === item.listing_id && (
                    <Tag color="blue">Consider first</Tag>
                  )}
                  <h4>{listing?.address ?? item.listing_id}</h4>
                  {listing && (
                    <p className="task-comparison-facts">
                      <strong>AUD {listing.weekly_rent}/week</strong>
                      <br />
                      {listing.bedroom_label} bed · {listing.bathrooms} bath ·{" "}
                      {listing.car_spaces} car spaces
                    </p>
                  )}
                  <Points label="Matches your needs" items={item.matches} />
                  <Points label="Trade-offs" items={item.tradeoffs} />
                  {listing && (
                    <div className="task-result-actions">
                      <Button size="small" onClick={() => onView?.(listing)}>
                        Listing details
                      </Button>
                      <ListingActions
                        listing={listing}
                        onSelect={onSave}
                        disabled={disabled}
                      />
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}
      {enquiry && (
        <section
          className="task-result-card"
          aria-label="Inspection enquiry draft"
        >
          <div className="task-result-heading">
            <h3>Inspection enquiry draft</h3>
            <Tag>Not sent</Tag>
          </div>
          <p>{enquiry.address}</p>
          <strong className="task-enquiry-subject">{enquiry.subject}</strong>
          <Input.TextArea
            aria-label="Inspection enquiry"
            value={enquiry.body}
            readOnly
            autoSize={{ minRows: 4, maxRows: 12 }}
          />
          <Points label="Suggested checks" items={enquiry.questions} />
          <div className="task-result-actions">
            <Button
              aria-label="Copy inspection enquiry"
              icon={<CopyOutlined />}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `${enquiry.subject}\n\n${enquiry.body}`,
                  );
                  toast.success("Inspection enquiry copied.");
                } catch {
                  toast.info("Select and copy the text in the box above.");
                }
              }}
            >
              Copy inspection enquiry
            </Button>
            {message.listings.find(
              (listing) => listing.listing_id === enquiry.listing_id,
            ) && (
              <Button
                size="small"
                onClick={() =>
                  onView?.(
                    message.listings.find(
                      (listing) => listing.listing_id === enquiry.listing_id,
                    )!,
                  )
                }
              >
                Listing details
              </Button>
            )}
          </div>
        </section>
      )}
      {checks &&
      extraChecks.length &&
      ((!comparison && !message.task_steps?.length) || Boolean(enquiry)) ? (
        <section
          className="task-result-card task-verification"
          aria-label="Verification checklist"
        >
          <h3>{checks.title}</h3>
          <ul>
            {extraChecks.map((text, i) => (
              <li key={i}>{housingCopy(text)}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
