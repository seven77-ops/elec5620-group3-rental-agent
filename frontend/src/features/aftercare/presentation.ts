import type { Dict, Json } from "../../api/types";

export function missingTenancyDetails(tenancy: Dict): string[] {
  const missing: string[] = [];
  if (!Array.isArray(tenancy.rooms) || !tenancy.rooms.length)
    missing.push("房间信息");
  for (const [key, label] of [
    ["carpeted", "是否有地毯"],
    ["outdoor", "是否有室外区域"],
    ["furnished", "是否带家具"],
  ])
    if (tenancy[key] == null) missing.push(label);
  if (tenancy.furnished === true) {
    if (!Array.isArray(tenancy.inventory) || !tenancy.inventory.length)
      missing.push("家具清单");
    else if (!tenancy.inventory_confirmed) missing.push("家具清单核对");
  }
  return missing;
}

export function tenancySource(value: Json | undefined): string {
  if (typeof value !== "string" || !value) return "尚未填写";
  if (value.startsWith("user-entered:")) return "用户填写";
  if (value.startsWith("review:")) return "合同复核预填";
  if (value.startsWith("synthetic://")) return "演示资料";
  return "已登记来源";
}

const evidenceLabels: Record<string, string> = {
  photo: "照片",
  receipt: "收据",
  condition_report: "房屋状况报告",
  deposit_record: "押金凭证",
  inspection_record: "验房记录",
  correspondence: "往来沟通",
  outcome: "结果记录",
  other: "其他资料",
};
export function evidenceKind(value: Json | undefined): string {
  return typeof value === "string" && Object.hasOwn(evidenceLabels, value)
    ? evidenceLabels[value]
    : "其他资料";
}

export function clarificationMessages(message: string): string[] {
  const messages: string[] = [];
  if (message.includes("Room layout is unknown"))
    messages.push("请添加房间信息，再安排各房间的清洁任务。");
  if (message.includes("whether carpeted"))
    messages.push("请确认房屋是否有地毯。");
  if (message.includes("whether outdoor"))
    messages.push("请确认是否有室外区域。");
  if (message.includes("whether the property is furnished"))
    messages.push("请确认房屋是否带家具。");
  if (message.includes("Furnished inventory"))
    messages.push("房屋带家具，请补充家具清单并核对内容。");
  if (message.includes("A bond reference or deposit record"))
    messages.push("请先补录押金编号，或关联一份押金凭证，再激活跟进。");
  return messages.length
    ? messages
    : ["请核对本次操作所需资料，补充完整后再继续。"];
}
