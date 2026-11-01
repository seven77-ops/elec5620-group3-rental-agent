const messages: Record<string, { title: string; message: string }> = {
  lease_ai_timeout: {
    title: "Contract extraction timed out",
    message:
      "Your source text and completed fields are preserved. Retry or process smaller sections.",
  },
  lease_ai_invalid_response: {
    title: "Some contract fields could not be extracted",
    message:
      "Your source text and completed fields are preserved. Please retry.",
  },
  unconfirmed_profile: {
    title: "Confirm your rental needs first",
    message:
      "Confirm your current rental needs before choosing a property and preparing a contract.",
  },
  selection_required: {
    title: "Choose a property first",
    message: "Save a property candidate before continuing.",
  },
  real_selection_required: {
    title: "Choose a property first",
    message: "Save a property candidate before continuing.",
  },
  stale_selection: {
    title: "Property selection needs updating",
    message:
      "Your rental needs have changed. Choose a property that meets your current needs.",
  },
  needs_clarification: {
    title: "More information is needed",
    message: "Complete the required information before continuing.",
  },
  version_conflict: {
    title: "Information has changed",
    message: "Load the latest information, check your input, and save again.",
  },
  stale_assistant_input: {
    title: "Conversation has changed",
    message: "Load the latest conversation before sending again.",
  },
  ai_not_configured: {
    title: "The assistant is temporarily unavailable",
    message:
      "Try again later or ask the project administrator to check the service configuration.",
  },
  ai_invalid_response: {
    title: "The assistant could not finish its response",
    message: "Retry this message. Your saved conversation is preserved.",
  },
  ai_timeout: {
    title: "The response is taking longer than expected",
    message: "Retry this message. Your saved conversation is preserved.",
  },
};
export function userError(
  code: string | undefined,
  message: string,
): { title: string; message: string } {
  if (code && Object.hasOwn(messages, code)) return messages[code];
  const readable = message.trim();
  const internal = /\b(?:INTERNAL|DEBUG|TRACEBACK|[A-Z][A-Z0-9]*_[A-Z0-9_]+|\w+Error|\w+Exception)\b|\n\s+at\s/;
  const safeEnglish = readable.length > 0 && readable.length <= 800 &&
    !/[\u3400-\u9fff\u0000-\u0008\u000b-\u001f]/.test(readable) && !internal.test(readable);
  return {
    title: "Unable to complete this action",
    message: safeEnglish
      ? readable
      : "Try again later or load the latest information to continue.",
  };
}
