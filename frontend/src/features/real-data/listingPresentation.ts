// Display language only: persisted source records and user messages stay intact.
export const housingCopy = (text: string) =>
  text
    .replaceAll("广告周租", "周租")
    .replaceAll("原广告", "原始房源")
    .replaceAll("广告", "房源");

export const propertyTypes: Record<string, string> = {
  apartment: "公寓",
  house: "独立屋",
  townhouse: "联排住宅",
  terrace: "排屋",
  studio: "Studio · 开放式户型",
  duplex: "双拼住宅",
  villa: "别墅式住宅",
};
export const furnishingTypes: Record<string, string> = {
  furnished: "带家具",
  unfurnished: "不带家具",
  partly_furnished: "部分家具",
};

// Only recognizable property attributes are shown. Navigation snippets and the
// extractor's “Unverified feature” marker must never become housing amenities.
const features: Record<string, string> = {
  "built in wardrobes": "入墙衣柜",
  "built-in wardrobes": "入墙衣柜",
  "built-in robes": "入墙衣柜",
  "built in robes": "入墙衣柜",
  "air conditioning": "空调",
  "air-conditioner": "空调",
  "air conditioning system": "空调",
  intercom: "对讲门禁",
  "intercom system": "对讲门禁",
  "audio intercom": "对讲门禁",
  "audio-visual intercom": "可视对讲",
  dishwasher: "洗碗机",
  "secure parking": "安全停车位",
  balcony: "阳台",
  "balcony / deck": "阳台 / 露台",
  deck: "露台",
  "close to shops": "邻近商店",
  "close to transport": "邻近公共交通",
  "close to schools": "邻近学校",
  "close to parklands": "邻近公园",
  "close to hospital": "邻近医院",
  floorboards: "木地板",
  ensuite: "套内浴室",
  "ensuite(s)": "套内浴室",
  "internal laundry": "室内洗衣区",
  "pets allowed": "可申请养宠物",
  "car parking - basement": "地下停车位",
  "car parking - surface": "地面停车位",
  "security access": "门禁系统",
  "security building": "门禁楼宇",
  "security system": "安防系统",
  "alarm system": "报警系统",
  "swimming pool": "游泳池",
  "swimming pool - in ground": "游泳池",
  "in ground pool": "游泳池",
  pool: "游泳池",
  gym: "健身房",
  "lift installed": "电梯",
  study: "书房",
  "study nook": "学习角",
  furnished: "带家具",
  unfurnished: "不带家具",
  gas: "燃气设施",
  "gas appliances": "燃气设备",
  "outdoor entertainment area": "户外活动区",
  "outdoor entertainment": "户外活动区",
  "outdoor entertaining": "户外活动区",
  bath: "浴缸",
  bathtub: "浴缸",
  "garden / courtyard": "花园 / 庭院",
  courtyard: "庭院",
  garden: "花园",
  "fully fenced": "围栏",
  heating: "暖气",
  "broadband internet access": "宽带接入设施",
  "broadband internet available": "宽带接入设施",
  "nbn connected": "NBN 接入设施",
  "openable windows": "可开启窗户",
  "reverse cycle air conditioning": "冷暖空调",
  "split-system air conditioning": "分体空调",
  "ducted air conditioning": "中央空调",
  "ducted air-conditioning": "中央空调",
  "ducted cooling": "管道制冷",
  "ducted heating": "管道暖气",
  "remote garage": "遥控车库",
  carpeted: "地毯",
  "area views": "周边景观",
  "city views": "城市景观",
  "water views": "水景",
  "district views": "周边景观",
  "north facing": "朝北",
  "ground floor": "底层",
  "double glazed windows": "双层玻璃窗",
  "solar panels": "太阳能板",
  spa: "水疗设施",
  "indoor spa": "室内水疗设施",
  "storage cage": "储物笼",
  shed: "储物棚",
  "cable or satellite": "有线 / 卫星接入设施",
  "fireplace(s)": "壁炉",
  "communal bbq area": "公共烧烤区",
  "communal rooftop": "公共屋顶区",
  "disabled access": "无障碍通道",
  "separate dining room": "独立餐厅",
  "renovated bathroom": "翻新浴室",
  "renovated kitchen": "翻新厨房",
  "luxury bathroom": "浴室配置",
  "luxury kitchen": "厨房配置",
  "energy efficient appliances": "节能电器",
  "water efficient appliances": "节水电器",
  "water efficient fixtures": "节水装置",
  "wall / ceiling insulation": "墙体 / 天花隔热",
  "tennis court": "网球场",
  penthouse: "顶层户型",
  "electric hotwater": "电热水系统",
  "rainwater storage tank": "雨水储水罐",
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
