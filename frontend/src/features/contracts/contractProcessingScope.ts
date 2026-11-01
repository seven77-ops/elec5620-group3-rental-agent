export function contractProcessingScope(
  selection: { profile_version: number; data_mode?: unknown } | null,
  confirmedVersion: number | undefined,
) {
  if (!selection)
    return { scope: "document" as const, allowed: true, synthetic: false };
  return {
    scope: "selection",
    allowed: Boolean(
      selection && selection.profile_version === confirmedVersion,
    ),
    synthetic: selection?.data_mode !== "real_listings",
  };
}
