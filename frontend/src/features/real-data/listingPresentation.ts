// Display language only: persisted source records and user messages stay intact.
// Only exact historical system labels are mapped; source and user text is intact.
const legacySystemCopy: Record<string, string> = {
  广告周租: "Advertised weekly rent",
  周租: "Weekly rent",
  原广告: "Original listing",
  原始房源: "Original listing",
  房源: "Listing",
  租房新计划: "New rental plan",
  记录回复与看房安排: "View inspection enquiry checklist",
  保存找房条件: "Save rental needs",
  我的租房需求: "My rental needs",
  选定并跟进: "Select and follow up",
  查看合同助手: "Open Contract assistant",
  进入租后服务: "Open Aftercare services",
};
export const housingCopy = (text: string) =>
  Object.hasOwn(legacySystemCopy, text) ? legacySystemCopy[text] : text;

// Older saved replies may still contain the retired recommendation footers.
// Match those exact notices; actual user requirements and questions are retained.
export function recommendationCopy(text: string) {
  const notices = [
    "这是房源标价预览，偏好尚未修改；在租状态、账单和计价对象仍需核实。",
    "这是广告标价预览，偏好尚未修改；在租状态、账单和计价对象仍需核实。",
    "是否仍在租、计价对象、账单、起租日期和通勤均待核实。",
    "计价对象、账单和在租状态待核实，不能据此认定个人总费用或实际性价比。",
  ];
  let result = text;
  for (const notice of notices) result = result.replaceAll(notice, "");
  return housingCopy(result)
    .replaceAll(
      "可以准备看房、记录中介回复或生成租约草稿",
      "Prepare an inspection or generate a lease draft",
    )
    .replaceAll(
      "可准备看房、记录中介回复，并进入合同流程",
      "Prepare an inspection and continue to the contract process",
    )
    .replaceAll(
      "可在房源跟进里记录中介回复；已有合同可直接复核。",
      "View the inspection enquiry checklist or go straight to lease drafting and review.",
    )
    .replace(/，先给你看\s*\d+\s*条/g, "")
    .replace(/；个人费用待核实|；计价对象待核实/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export const propertyTypes: Record<string, string> = {
  apartment: "Apartment",
  house: "House",
  townhouse: "Townhouse",
  terrace: "Terrace",
  studio: "Studio · Open-plan layout",
  duplex: "Duplex",
  villa: "Villa",
};
export const furnishingTypes: Record<string, string> = {
  furnished: "Furnished",
  unfurnished: "Unfurnished",
  partly_furnished: "Partly furnished",
};

// Only recognizable property attributes are shown. Navigation snippets and the
// extractor's “Unverified feature” marker must never become housing amenities.
const features: Record<string, string> = {
  "built in wardrobes": "Built-in wardrobes",
  "built-in wardrobes": "Built-in wardrobes",
  "built-in robes": "Built-in wardrobes",
  "built in robes": "Built-in wardrobes",
  "air conditioning": "Air conditioning",
  "air-conditioner": "Air conditioning",
  "air conditioning system": "Air conditioning",
  intercom: "Intercom",
  "intercom system": "Intercom",
  "audio intercom": "Intercom",
  "audio-visual intercom": "Audio-visual intercom",
  dishwasher: "Dishwasher",
  "secure parking": "Secure parking",
  balcony: "Balcony",
  "balcony / deck": "Balcony / deck",
  deck: "Deck",
  "close to shops": "Close to shops",
  "close to transport": "Close to public transport",
  "close to schools": "Close to schools",
  "close to parklands": "Close to parks",
  "close to hospital": "Close to hospital",
  floorboards: "Floorboards",
  ensuite: "Ensuite",
  "ensuite(s)": "Ensuite",
  "internal laundry": "Internal laundry",
  "pets allowed": "Pets subject to approval",
  "car parking - basement": "Basement parking",
  "car parking - surface": "Surface parking",
  "security access": "Security access",
  "security building": "Security building",
  "security system": "Security system",
  "alarm system": "Alarm system",
  "swimming pool": "Swimming pool",
  "swimming pool - in ground": "Swimming pool",
  "in ground pool": "Swimming pool",
  pool: "Swimming pool",
  gym: "Gym",
  "lift installed": "Lift",
  study: "Study",
  "study nook": "Study nook",
  furnished: "Furnished",
  unfurnished: "Unfurnished",
  gas: "Gas connection",
  "gas appliances": "Gas appliances",
  "outdoor entertainment area": "Outdoor entertaining area",
  "outdoor entertainment": "Outdoor entertaining area",
  "outdoor entertaining": "Outdoor entertaining area",
  bath: "Bath",
  bathtub: "Bath",
  "garden / courtyard": "Garden / courtyard",
  courtyard: "Courtyard",
  garden: "Garden",
  "fully fenced": "Fully fenced",
  heating: "Heating",
  "broadband internet access": "Broadband internet access",
  "broadband internet available": "Broadband internet access",
  "nbn connected": "NBN connection",
  "openable windows": "Openable windows",
  "reverse cycle air conditioning": "Reverse-cycle air conditioning",
  "split-system air conditioning": "Split-system air conditioning",
  "ducted air conditioning": "Ducted air conditioning",
  "ducted air-conditioning": "Ducted air conditioning",
  "ducted cooling": "Ducted cooling",
  "ducted heating": "Ducted heating",
  "remote garage": "Remote garage",
  carpeted: "Carpet",
  "area views": "Area views",
  "city views": "City views",
  "water views": "Water views",
  "district views": "Area views",
  "north facing": "North facing",
  "ground floor": "Ground floor",
  "double glazed windows": "Double-glazed windows",
  "solar panels": "Solar panels",
  spa: "Spa",
  "indoor spa": "Indoor spa",
  "storage cage": "Storage cage",
  shed: "Shed",
  "cable or satellite": "Cable / satellite connection",
  "fireplace(s)": "Fireplace",
  "communal bbq area": "Communal barbecue area",
  "communal rooftop": "Communal rooftop",
  "disabled access": "Accessible entrance",
  "separate dining room": "Separate dining room",
  "renovated bathroom": "Renovated bathroom",
  "renovated kitchen": "Renovated kitchen",
  "luxury bathroom": "Bathroom fittings",
  "luxury kitchen": "Kitchen fittings",
  "energy efficient appliances": "Energy-efficient appliances",
  "water efficient appliances": "Water-efficient appliances",
  "water efficient fixtures": "Water-efficient fixtures",
  "wall / ceiling insulation": "Wall / ceiling insulation",
  "tennis court": "Tennis court",
  penthouse: "Penthouse",
  "electric hotwater": "Electric hot-water system",
  "rainwater storage tank": "Rainwater tank",
};
export function knownLabel(
  labels: Record<string, string>,
  key?: string | null,
) {
  return key && Object.hasOwn(labels, key) ? labels[key] : undefined;
}
export function propertyFeatures(values: string[] = []) {
  return [
    ...new Set(
      values
        .map((value) =>
          knownLabel(
            features,
            value.trim().replace(/\*+$/, "").trim().toLowerCase(),
          ),
        )
        .filter(Boolean),
    ),
  ];
}

export const displayDate = (value?: string | null) =>
  value && /^\d{4}-\d{2}-\d{2}/.test(value)
    ? value.slice(0, 10).replaceAll("-", "/")
    : null;
