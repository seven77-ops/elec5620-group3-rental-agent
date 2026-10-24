import { App, Button, Input, Tag } from "antd";
import {
  CheckCircleOutlined,
  QuestionCircleOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import type { AssistantMessage } from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import { housingCopy } from "../real-data/listingPresentation";
import "./taskResults.css";

function Points({ label, items }: { label: string; items: string[] }) {
  return items.length ? (
    <div className="task-points">
      <strong>{label}</strong>
      <ul>
        {items.map((text, i) => (
          <li key={i}>{housingCopy(text)}</li>
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
  selectedListingId,
}: {
  message: AssistantMessage;
  onView?: (listing: HousingAd) => void;
  onSave?: (listing: HousingAd) => void;
  disabled?: boolean;
  selectedListingId?: string;
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
        <ol className="task-steps" aria-label="本次任务">
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
        <section className="task-result-card" aria-label="个性化房源比较">
          <h3>按你的需求比较</h3>
          <p className="muted small">{housingCopy(comparison.basis)}</p>
          <p>{housingCopy(comparison.summary)}</p>
          <div className="task-comparison-grid">
            {comparison.items.map((item) => {
              const listing = message.listings.find(
                (row) => row.listing_id === item.listing_id,
              );
              return (
                <article key={item.listing_id} className="task-comparison-item">
                  {comparison.recommended_listing_id === item.listing_id && (
                    <Tag color="blue">优先考虑</Tag>
                  )}
                  <h4>{listing?.address ?? item.listing_id}</h4>
                  {listing && (
                    <p className="task-comparison-facts">
                      <strong>AUD {listing.weekly_rent}/周</strong>
                      <br />
                      {listing.bedroom_label} 卧 · {listing.bathrooms} 卫 ·{" "}
                      {listing.car_spaces} 车位
                    </p>
                  )}
                  <Points label="符合的要求" items={item.matches} />
                  <Points label="需要取舍" items={item.tradeoffs} />
                  <Points
                    label="还需核实"
                    items={item.to_verify.filter(
                      (text) => !sharedChecks.includes(text),
                    )}
                  />
                  {listing && (
                    <div className="task-result-actions">
                      <Button size="small" onClick={() => onView?.(listing)}>
                        房源详情
                      </Button>
                      {selectedListingId === listing.listing_id ? (
                        <Tag color="blue">当前候选</Tag>
                      ) : (
                        <Button
                          size="small"
                          disabled={disabled}
                          onClick={() => onSave?.(listing)}
                        >
                          保存为候选
                        </Button>
                      )}
                      <a
                        href={listing.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        原始房源 ↗
                      </a>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
          <Points label="共同待核实事项" items={sharedChecks} />
        </section>
      )}
      {enquiry && (
        <section className="task-result-card" aria-label="看房询问草稿">
          <div className="task-result-heading">
            <h3>看房询问草稿</h3>
            <Tag>尚未发送</Tag>
          </div>
          <p>{enquiry.address}</p>
          <strong className="task-enquiry-subject">{enquiry.subject}</strong>
          <Input.TextArea
            aria-label="看房询问内容"
            value={enquiry.body}
            readOnly
            autoSize={{ minRows: 4, maxRows: 12 }}
          />
          <Points label="建议核实" items={enquiry.questions} />
          <div className="task-result-actions">
            <Button
              aria-label="复制看房询问"
              icon={<CopyOutlined />}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `${enquiry.subject}\n\n${enquiry.body}`,
                  );
                  toast.success("已复制看房询问。");
                } catch {
                  toast.info("请在上方文本框中选中并复制内容。");
                }
              }}
            >
              复制看房询问
            </Button>
            <a
              href={enquiry.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              查看原始房源 ↗
            </a>
          </div>
        </section>
      )}
      {checks && extraChecks.length ? (
        <section
          className="task-result-card task-verification"
          aria-label="待核实清单"
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
