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
  if (value.startsWith("review:") || value.startsWith("contract-review:"))
    return "合同复核预填";
  if (value.startsWith("selected-listing:")) return "已选房源预填";
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

// Agent 4 generates English titles; known ones are shown in Chinese, user edits stay as typed.
const taskTitles: Record<string, string> = {
  "Locate incoming condition records; record missing evidence":
    "查找入住时的房屋状况记录；缺失时补充说明",
  "Check and clean carpet as appropriate; document existing marks":
    "检查并按需清洁地毯，记录已有痕迹",
  "Clear belongings and tidy the supplied outdoor areas":
    "清理室外区域的个人物品并整理",
  "Verify supplied furniture inventory and discrepancies":
    "核对房东提供的家具清单及差异",
  "Arrange final meter readings and close or transfer electricity, gas and internet accounts":
    "安排最终抄表，关闭或转移电、气、网络账户",
  "Remove belongings and arrange personal service/address changes":
    "搬走个人物品，办理邮件转寄和地址变更",
  "Prepare final inspection photos and compare available condition records":
    "准备退租检查照片，并与入住记录对照",
  "Arrange key return and retain a dated receipt": "交还钥匙并保留注明日期的收据",
  "Check the bond refund claim on Rental Bonds Online and record its reference":
    "在 Rental Bonds Online 核对押金退款申请并记录编号",
  "Check your bond record; record any actual outcome yourself":
    "查看押金记录；实际结果请自行登记",
};
export function taskTitle(value: Json | undefined): string {
  if (typeof value !== "string") return "未命名任务";
  if (Object.hasOwn(taskTitles, value)) return taskTitles[value];
  const room = /^Clean (.+) and record its condition$/.exec(value);
  if (room) return `清洁「${room[1]}」并记录状况`;
  const item = /^Check supplied inventory: (.+)$/.exec(value);
  if (item) return `核对房东提供的家具：${item[1]}`;
  return value;
}

const gapTexts: Record<string, string> = {
  "Baseline condition report unavailable: supply records or document current condition.":
    "没有入住时的房屋状况报告：请补充记录，或在交钥匙前全面拍照记录现状。",
};
export function planNotes(plan: Dict): string[] {
  const gaps = ((plan.evidence_gaps as string[]) ?? []).map(
    (g) => gapTexts[g] ?? g,
  );
  const questions = ((plan.clarification_requests as string[]) ?? []).flatMap(
    (q) => clarificationMessages(q),
  );
  return [...questions, ...gaps];
}

/** Sydney wall-clock text for an ISO instant, e.g. 2026-11-14 09:00 AEDT. */
export function sydneyTime(value: Json | undefined, withTime = true): string {
  if (typeof value !== "string" || !value) return "未提供";
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return value;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-AU", {
      timeZone: "Australia/Sydney",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZoneName: "short",
    })
      .formatToParts(instant)
      .map((p) => [p.type, p.value]),
  );
  const day = `${parts.year}-${parts.month}-${parts.day}`;
  return withTime ? `${day} ${parts.hour}:${parts.minute} ${parts.timeZoneName}` : day;
}

/** Today's calendar date in Sydney as YYYY-MM-DD. */
export function sydneyToday(): string {
  return sydneyTime(new Date().toISOString(), false);
}

/** ISO instant for a Sydney wall-clock date and time, with the offset in force then. */
export function sydneyIso(date: string, time = "09:00"): string {
  const probe = new Date(`${date}T${time}:00Z`);
  const name =
    new Intl.DateTimeFormat("en-US", {
      timeZone: "Australia/Sydney",
      timeZoneName: "longOffset",
    })
      .formatToParts(probe)
      .find((p) => p.type === "timeZoneName")?.value ?? "GMT+10:00";
  const offset = name.replace("GMT", "") || "+00:00";
  return `${date}T${time}:00${offset}`;
}
