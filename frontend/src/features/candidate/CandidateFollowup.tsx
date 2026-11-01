import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Button, Collapse, Drawer, Space, Tag } from "antd";
import {
  ArrowRightOutlined,
  MailOutlined,
  ExportOutlined,
} from "@ant-design/icons";
import { currentConfirmation, useCase } from "../../app/context";
import { downloadUrl } from "../../api/client";
import { housingCopy } from "../real-data/listingPresentation";
import InspectionEnquiry from "./InspectionEnquiry";
import { listingContactUrl } from "./enquiryTemplate";

const questions = [
  "Is the property still available, and when can I inspect it?",
  "What is the rent, is it paid weekly, monthly or fortnightly, and is it for the whole property, per room or per person?",
  "Which bills are included in the rent, and are there other charges?",
  "What are the move-in date, lease term and bond?",
  "Are all advertised bedrooms, bathrooms and car spaces included in this tenancy?",
  "What documents are needed to apply? Can you provide the proposed lease and the landlord or agent details?",
];
export default function CandidateFollowup({
  compact = false,
}: {
  compact?: boolean;
}) {
  const { current, go } = useCase();
  const [open, setOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const selection =
    current.selection?.data_mode === "real_listings" ? current.selection : null;
  const confirmation = currentConfirmation(current);
  const isCurrent = Boolean(
    selection &&
    confirmation &&
    selection.profile_version === confirmation.version &&
    selection.profile_fingerprint === confirmation.fingerprint,
  );
  const identity = JSON.stringify(selection);
  const sourceUrl = listingContactUrl(selection?.listing_snapshot.source_url);
  useEffect(() => {
    if (params.get("followup") === "1" && selection) {
      setOpen(true);
      const next = new URLSearchParams(params);
      next.delete("followup");
      setParams(next, { replace: true });
    }
  }, [params, setParams, identity]);
  if (!selection) return null;
  const contract = (mode: "draft" | "review") => {
    setOpen(false);
    go(`contract?mode=${mode}`);
  };
  return (
    <>
      <section
        className={`candidate-next ${compact ? "candidate-next-compact" : ""}`}
        data-testid="candidate-next"
      >
        <div className="candidate-next-copy">
          <span className="muted small">
            {compact
              ? "Current follow-up property"
              : "Property selected for follow-up"}
          </span>
          <strong>
            {String(selection.listing_snapshot.address ?? selection.listing_id)}
          </strong>
          {!compact && (
            <p className="muted">
              Contact the agent about a viewing, or continue to lease drafting
              and review.
            </p>
          )}
        </div>
        <Space wrap>
          <Button
            aria-label="Contact property agent"
            icon={<MailOutlined />}
            type={compact ? "default" : "primary"}
            onClick={() => setOpen(true)}
          >
            Contact property agent
          </Button>
          {!compact && (
            <>
              <Button disabled={!isCurrent} onClick={() => contract("draft")}>
                Generate lease draft
              </Button>
              <Button
                disabled={!isCurrent}
                onClick={() => contract("review")}
                aria-label="Review an existing contract"
                icon={<ArrowRightOutlined />}
              >
                Review an existing contract
              </Button>
            </>
          )}
        </Space>
        {!isCurrent && (
          <Alert
            type="warning"
            showIcon
            title="Previous follow-up property · Your needs have changed. Select a property again to continue."
          />
        )}
      </section>
      <Drawer
        title="Contact property agent"
        open={open}
        onClose={() => setOpen(false)}
        size={560}
        className="candidate-followup-drawer"
      >
        <div className="candidate-followup-heading">
          <h2>{String(selection.listing_snapshot.address)}</h2>
          <Space wrap>
            <Tag color="blue">
              Listed at AUD {String(selection.listing_snapshot.weekly_rent)}
              /week
            </Tag>
          </Space>
        </div>
        {sourceUrl ? (
          <Button
            type="primary"
            size="large"
            block
            aria-label="Open listing & contact property agent"
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            icon={<ExportOutlined />}
          >
            Open listing &amp; contact property agent
          </Button>
        ) : (
          <Alert
            type="info"
            showIcon
            title="The original listing link is unavailable."
          />
        )}
        <p className="muted small inspection-contact-note">
          View inspection times or contact the agent on the listing website.
          Bookings are arranged there.
        </p>
        <InspectionEnquiry
          key={`${current.case_id}:${selection.listing_id}`}
          address={String(
            selection.listing_snapshot.address ?? selection.listing_id,
          )}
        />
        <Collapse
          className="inspection-checklist"
          items={[
            {
              key: "checklist",
              label: "Inspection checklist",
              children: (
                <>
                  <ol className="candidate-questions">
                    {questions.map((q) => (
                      <li key={q}>{housingCopy(q)}</li>
                    ))}
                  </ol>
                  <a
                    href={downloadUrl(
                      `/cases/${current.case_id}/candidate-followup/questions`,
                    )}
                  >
                    Download enquiry checklist
                  </a>
                </>
              ),
            },
          ]}
        />
      </Drawer>
    </>
  );
}
