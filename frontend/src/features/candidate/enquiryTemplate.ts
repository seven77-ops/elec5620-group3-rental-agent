export interface EnquiryDetails {
  agentName?: string;
  preferredTime?: string;
  questions?: string;
}

export function prepareEnquiry(address: string, details: EnquiryDetails) {
  const name = details.agentName?.trim();
  const time = details.preferredTime?.trim();
  const questions = details.questions?.trim();
  return {
    subject: `Inspection enquiry: ${address}`,
    body: [
      name ? `Hi ${name},` : "Hi,",
      `I’m interested in ${address}. Is the property still available, and are there any upcoming inspections?`,
      time ? `I’m available ${time}.` : null,
      "Please let me know how to register for an inspection.",
      questions || null,
      "Thank you.",
    ]
      .filter((line) => line !== null)
      .join("\n\n"),
  };
}

export function listingContactUrl(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    return ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export function enquiryMailto(
  email: string,
  subject: string,
  body: string,
): string | null {
  const recipient = email.trim();
  // One explicit recipient only; punctuation cannot introduce extra headers.
  if (
    !/^[A-Za-z0-9.!#$%&'*+/=^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/.test(
      recipient,
    )
  )
    return null;
  const safeSubject = subject.replace(/[\r\n]+/g, " ");
  const encodedRecipient = encodeURIComponent(recipient)
    .replace(/%40/g, "@")
    .replace(/%2B/g, "+");
  return `mailto:${encodedRecipient}?subject=${encodeURIComponent(safeSubject)}&body=${encodeURIComponent(body)}`;
}
