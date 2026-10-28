import type { LivingProvider } from "../../api/living";

// Concise company facts from the existing sourced service directory.
// Enquiry instructions and booking caveats stay out of the company introduction.
const introductions: Record<string, string> = {
  "two-men-and-a-truck": "提供悉尼搬运服务。",
  grace: "在悉尼 Seven Hills 设有分公司，提供搬运和储存服务。",
  kent: "提供住宅搬运与储存服务。",
  "men-that-move": "提供家具和住宅搬运，以及可重复使用的搬家箱租借服务。",
  holloway:
    "提供本地及跨州搬家、打包拆包和仓储服务，悉尼办公室位于 Wolli Creek。",
  "removal-brothers": "提供住宅和公寓搬运、打包、仓储及跨州运输服务。",
  moveworx: "提供本地与跨州家具搬运、打包和仓储服务。",
  optimove: "提供住宅家具搬运、全程打包及家具组装服务。",
  "man-and-his-van": "提供家具、住宅及办公室搬运、搬家箱和仓储服务。",
  nuss: "提供本地、跨州及国际搬运，以及打包和仓储服务。",
  "chess-moving":
    "悉尼分部位于 Blacktown，提供住宅、跨州及国际搬运和仓储服务。",
  citymove: "提供住宅、公寓及办公室搬运服务。",
  "simply-maid": "提供悉尼退租清洁服务。",
  "fantastic-cleaners": "提供日常及退租清洁服务。",
  "calibre-cleaning": "提供悉尼日常及退租清洁服务。",
  maid2match: "提供住宅定期及一次性清洁服务。",
  "absolute-domestics":
    "提供住宅日常、一次性及退租清洁，由机构匹配当地清洁人员。",
  "this-is-neat": "专注退租及搬入搬出清洁，不提供普通日常家政或办公室清洁。",
  "maid-for-you": "提供住宅日常、一次性及退租清洁服务。",
  maid2go: "提供日常、深度及退租清洁服务。",
  "1800-cleaner": "提供住宅清洁、深度清洁、窗户及地毯清洁服务。",
  "jims-cleaning": "提供地毯蒸汽清洁、污渍处理及布艺等专业清洁服务。",
  "call-the-cleaners":
    "在悉尼 Rhodes 设点，提供住宅日常、深度、公寓及退租清洁服务。",
  "clean-australia": "提供住宅、公寓、退租、地毯蒸汽及窗户清洁服务。",
};

export const serviceCompanyIntro = (provider: LivingProvider) =>
  introductions[provider.id] ||
  `${provider.name}提供${provider.categories.includes("removalist") ? "搬运" : "清洁"}服务。`;
