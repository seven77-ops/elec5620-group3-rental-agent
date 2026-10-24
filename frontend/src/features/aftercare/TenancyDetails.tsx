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
    value == null ? "尚未确认" : value ? "有" : "无";
  const listStatus =
    tenancy.furnished === false
      ? "无需填写"
      : !inventory.length
        ? "待补充清单"
        : tenancy.inventory_confirmed
          ? "已核对"
          : "待核对";
  return (
    <div className="aftercare-details">
      <header>
        <Tag color={missing.length ? "gold" : "blue"}>
          {missing.length ? `待补充 ${missing.length} 项` : "资料已齐备"}
        </Tag>
        <h2>{String(tenancy.address || "租约地址尚未填写")}</h2>
        <p className="muted">
          {tenancySource(tenancy.source_ref)} · 资料版本{" "}
          {String(tenancy.source_version ?? 1)}
        </p>
        <Space wrap>
          <Button type="primary" disabled={!editable} onClick={onEdit}>
            补充租约资料
          </Button>
          <Button onClick={onAddEvidence}>登记资料</Button>
        </Space>
      </header>
      {missing.length > 0 && (
        <Alert
          type="info"
          showIcon
          title="还需要这些信息"
          description={missing.join("、")}
        />
      )}
      <section aria-label="房屋概览">
        <h3>房屋概览</h3>
        <Descriptions
          column={1}
          size="small"
          items={[
            {
              key: "jurisdiction",
              label: "所在地区",
              children:
                tenancy.jurisdiction === "NSW"
                  ? "新南威尔士州（NSW）"
                  : String(tenancy.jurisdiction || "尚未填写"),
            },
            {
              key: "type",
              label: "租约类型",
              children:
                tenancy.tenancy_type === "standard_residential"
                  ? "标准住宅租约"
                  : String(tenancy.tenancy_type || "尚未填写"),
            },
            {
              key: "carpet",
              label: "地毯",
              children: booleanLabel(tenancy.carpeted),
            },
            {
              key: "outdoor",
              label: "室外区域",
              children: booleanLabel(tenancy.outdoor),
            },
            {
              key: "furnished",
              label: "随房家具",
              children: booleanLabel(tenancy.furnished),
            },
            { key: "inventory", label: "家具清单", children: listStatus },
          ]}
        />
      </section>
      <section aria-label="房间信息">
        <h3>房间信息{rooms.length ? ` · ${rooms.length} 间` : ""}</h3>
        {rooms.length ? (
          <Space wrap>
            {rooms.map((r, i) => (
              <Tag key={String(r.id ?? i)}>
                {String(r.name || "未命名房间")}
              </Tag>
            ))}
          </Space>
        ) : (
          <p className="aftercare-empty">尚未添加房间</p>
        )}
      </section>
      <section aria-label="家具清单">
        <h3>家具清单</h3>
        {tenancy.furnished === false ? (
          <p className="muted">房屋不带家具，无需填写清单。</p>
        ) : inventory.length ? (
          <div>
            {inventory.map((item, i) => {
              const room = rooms.find((r) => r.id === item.room_id);
              return (
                <div
                  className="aftercare-inventory-item"
                  key={String(item.id ?? i)}
                >
                  <strong>{String(item.name || "未命名家具")}</strong>
                  <span>{String(room?.name || "所属房间待确认")}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="aftercare-empty">尚未添加家具清单</p>
        )}
      </section>
      <section aria-label="已登记资料">
        <div className="section-heading">
          <h3>已登记资料 · {evidence.length} 份</h3>
          <Button size="small" onClick={onAddEvidence}>
            登记资料
          </Button>
        </div>
        <p className="muted small">
          这里只登记资料名称、位置与摘要，内容尚未核实。
        </p>
        {evidence.length ? (
          evidence.map((e, i) => (
            <article
              className="aftercare-evidence-card"
              key={String(e.evidence_id ?? i)}
            >
              <Tag>{evidenceKind(e.kind)}</Tag>
              <p>{String(e.summary || "尚未填写摘要")}</p>
              <small>
                资料位置：{String(e.source_ref || "尚未填写")} · 版本{" "}
                {String(e.source_version ?? 1)}
              </small>
            </article>
          ))
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无登记资料"
          />
        )}
      </section>
      <Collapse
        ghost
        size="small"
        items={[
          {
            key: "raw",
            label: "查看原始资料",
            children: <JsonDetails value={{ tenancy, evidence }} />,
          },
        ]}
      />
    </div>
  );
}
