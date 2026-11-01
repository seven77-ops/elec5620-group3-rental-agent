import { Alert, Button, Collapse, Descriptions, Empty, Space, Tag } from "antd";
import type { Dict } from "../../api/types";
import { JsonDetails } from "../../components/Common";
import {
  evidenceKind,
  missingTenancyDetails,
  tenancySource,
} from "./presentation";

export default function TenancyDetails({
  tenancy,
  evidence,
  editable,
  onEdit,
  onAddEvidence,
}: {
  tenancy: Dict;
  evidence: Dict[];
  editable: boolean;
  onEdit: () => void;
  onAddEvidence: () => void;
}) {
  const rooms = (tenancy.rooms ?? []) as Dict[];
  const inventory = (tenancy.inventory ?? []) as Dict[];
  const missing = missingTenancyDetails(tenancy);
  const booleanLabel = (value: unknown) =>
    value == null ? "Not confirmed" : value ? "Yes" : "None";
  const listStatus =
    tenancy.furnished === false
      ? "Not required"
      : !inventory.length
        ? "Missing information"
        : tenancy.inventory_confirmed
          ? "Checked"
          : "To be checked";
  return (
    <div className="aftercare-details">
      <header>
        <Tag color={missing.length ? "gold" : "blue"}>
          {missing.length
            ? `Missing ${missing.length}  items`
            : "Information complete"}
        </Tag>
        <h2>{String(tenancy.address || "Lease address not entered")}</h2>
        <p className="muted">
          {tenancySource(tenancy.source_ref)} · Information version{" "}
          {String(tenancy.source_version ?? 1)}
        </p>
        <Space wrap>
          <Button type="primary" disabled={!editable} onClick={onEdit}>
            Complete lease details
          </Button>
          <Button onClick={onAddEvidence}>Register information</Button>
        </Space>
      </header>
      {missing.length > 0 && (
        <Alert
          type="info"
          showIcon
          title="This information is still needed"
          description={missing.join(", ")}
        />
      )}
      <section aria-label="Property overview">
        <h3>Property overview</h3>
        <Descriptions
          column={1}
          size="small"
          items={[
            {
              key: "jurisdiction",
              label: "Location",
              children:
                tenancy.jurisdiction === "NSW"
                  ? "New South Wales (NSW)"
                  : String(tenancy.jurisdiction || "Not entered"),
            },
            {
              key: "type",
              label: "Lease type",
              children:
                tenancy.tenancy_type === "standard_residential"
                  ? "Standard residential tenancy"
                  : String(tenancy.tenancy_type || "Not entered"),
            },
            {
              key: "carpet",
              label: "Carpet",
              children: booleanLabel(tenancy.carpeted),
            },
            {
              key: "outdoor",
              label: "Outdoor area",
              children: booleanLabel(tenancy.outdoor),
            },
            {
              key: "furnished",
              label: "Included furniture",
              children: booleanLabel(tenancy.furnished),
            },
            {
              key: "inventory",
              label: "Furniture inventory",
              children: listStatus,
            },
          ]}
        />
      </section>
      <section aria-label="Room details">
        <h3>Room details{rooms.length ? ` · ${rooms.length}  rooms` : ""}</h3>
        {rooms.length ? (
          <Space wrap>
            {rooms.map((r, i) => (
              <Tag key={String(r.id ?? i)}>
                {String(r.name || "Unnamed room")}
              </Tag>
            ))}
          </Space>
        ) : (
          <p className="aftercare-empty">No rooms added</p>
        )}
      </section>
      <section aria-label="Furniture inventory">
        <h3>Furniture inventory</h3>
        {tenancy.furnished === false ? (
          <p className="muted">
            The property is unfurnished. No inventory is required.
          </p>
        ) : inventory.length ? (
          <div>
            {inventory.map((item, i) => {
              const room = rooms.find((r) => r.id === item.room_id);
              return (
                <div
                  className="aftercare-inventory-item"
                  key={String(item.id ?? i)}
                >
                  <strong>{String(item.name || "Unnamed furniture")}</strong>
                  <span>{String(room?.name || "Room to be confirmed")}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="aftercare-empty">No furniture inventory added</p>
        )}
      </section>
      <section aria-label="Registered information">
        <div className="section-heading">
          <h3>Registered information · {evidence.length} documents</h3>
          <Button size="small" onClick={onAddEvidence}>
            Register information
          </Button>
        </div>
        <p className="muted small">
          Only names, locations, and summaries are registered here. Contents
          have not been verified.
        </p>
        {evidence.length ? (
          evidence.map((e, i) => (
            <article
              className="aftercare-evidence-card"
              key={String(e.evidence_id ?? i)}
            >
              <Tag>{evidenceKind(e.kind)}</Tag>
              <p>{String(e.summary || "No summary entered")}</p>
              <small>
                Document location: {String(e.source_ref || "Not entered")} ·
                Version {String(e.source_version ?? 1)}
              </small>
            </article>
          ))
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No registered information"
          />
        )}
      </section>
      <Collapse
        ghost
        size="small"
        items={[
          {
            key: "raw",
            label: "View original information",
            children: <JsonDetails value={{ tenancy, evidence }} />,
          },
        ]}
      />
    </div>
  );
}
