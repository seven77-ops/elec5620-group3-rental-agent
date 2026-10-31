import type { Review } from "../../api/types";

export function reviewSummary(review: Review) {
  if (review.status === "Awaiting Human Review")
    return {
      title: "This contract needs a closer look",
      description:
        "Check the highlighted issues and their original wording. A reviewer needs to assess them before you can prepare questions.",
    };
  if (review.status === "Awaiting Resubmission")
    return {
      title: "Check the document and try again",
      description:
        "Some information needs a clearer or corrected copy. Check the original, then edit the details or upload another copy.",
    };
  if (review.status === "Degraded Summary Only")
    return {
      title: "Only a limited review is available",
      description:
        "You can check the details extracted below. A full set of checks is not currently available.",
    };
  return {
    title: review.findings.length
      ? "There are details to check"
      : "No issues found in the checks completed",
    description:
      "Compare the details below with your contract. This review does not confirm that the contract is ready to sign.",
  };
}

export function contractValue(review: Review, key: string) {
  const value = review.fields[key]?.value;
  if (value === null || value === undefined || value === "")
    return "Not provided";
  if ((key === "rent_amount" || key === "bond") && typeof value === "number") {
    const bondQuote = review.fields.bond?.evidence?.quote?.match(
      /^(?:rental\s+)?bond\s*[:\-]\s*(AUD|USD|NZD|EUR|GBP|CAD|SGD|CNY)\s*\$?\s*([\d,]+(?:\.\d{1,2})?)/i,
    );
    const currency =
      key === "bond"
        ? bondQuote && Number(bondQuote[2].replaceAll(",", "")) === value
          ? bondQuote[1].toUpperCase()
          : undefined
        : review.fields.currency?.value;
    const amount = `${typeof currency === "string" ? currency : "Currency not specified"} ${value.toLocaleString("en-AU")}`;
    if (key === "bond") return amount;
    const period = { week: "week", fortnight: "fortnight", month: "month" }[
      String(review.fields.rent_period?.value)
    ];
    const scope = {
      whole_property: "Whole property",
      per_person: "Per person",
      per_room: "Per room",
    }[String(review.fields.rent_scope?.value)];
    return `${amount}${period ? ` / ${period}` : " · Period not specified"} · ${scope ?? "Pricing basis not specified"}`;
  }
  return String(value);
}
