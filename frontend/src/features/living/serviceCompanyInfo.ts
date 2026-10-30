import type { LivingProvider } from "../../api/living";

// Concise company facts from the existing sourced service directory.
// Enquiry instructions and booking caveats stay out of the company introduction.
const introductions: Record<string, string> = {
  "two-men-and-a-truck": "Provides moving services in Sydney.",
  grace:
    "Has a Seven Hills branch in Sydney and provides moving and storage services.",
  kent: "Provides residential moving and storage services.",
  "men-that-move":
    "Provides furniture and residential moving, plus reusable moving box hire.",
  holloway:
    "Provides local and interstate moving, packing, unpacking, and storage, with a Sydney office in Wolli Creek.",
  "removal-brothers":
    "Provides house and apartment moving, packing, storage, and interstate transport.",
  moveworx:
    "Provides local and interstate furniture moving, packing, and storage.",
  optimove:
    "Provides residential furniture moving, full packing, and furniture assembly.",
  "man-and-his-van":
    "Provides furniture, house, and office moving, moving boxes, and storage.",
  nuss: "Provides local, interstate, and international moving, packing, and storage.",
  "chess-moving":
    "Has a Sydney branch in Blacktown and provides residential, interstate, and international moving and storage.",
  citymove: "Provides house, apartment, and office moving.",
  "simply-maid": "Provides end-of-lease cleaning in Sydney.",
  "fantastic-cleaners": "Provides regular and end-of-lease cleaning.",
  "calibre-cleaning": "Provides regular and end-of-lease cleaning in Sydney.",
  maid2match: "Provides regular and one-off residential cleaning.",
  "absolute-domestics":
    "Provides regular, one-off, and end-of-lease home cleaning, matching customers with local cleaners.",
  "this-is-neat":
    "Specialises in end-of-lease and move-in/move-out cleaning, without regular housekeeping or office cleaning.",
  "maid-for-you": "Provides regular, one-off, and end-of-lease home cleaning.",
  maid2go: "Provides regular, deep, and end-of-lease cleaning.",
  "1800-cleaner": "Provides home, deep, window, and carpet cleaning.",
  "jims-cleaning":
    "Provides specialist carpet steam cleaning, stain treatment, and upholstery cleaning.",
  "call-the-cleaners":
    "Based in Rhodes, Sydney, and provides regular, deep, apartment, and end-of-lease home cleaning.",
  "clean-australia":
    "Provides house, apartment, end-of-lease, carpet steam, and window cleaning.",
};

export const serviceCompanyIntro = (provider: LivingProvider) =>
  introductions[provider.id] ||
  `${provider.name} provides ${provider.categories.includes("removalist") ? "moving" : "cleaning"} services.`;
