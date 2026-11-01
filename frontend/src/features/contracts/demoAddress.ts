// Display aliases for the bundled fictional fixtures only. Never change saved
// facts, user addresses, source quotations or evidence used by contract checks.
export function demoAddress(value: unknown, selection: unknown): string {
  const address = String(value ?? "");
  if (!selection || typeof selection !== "object") return address;
  const packet = selection as Record<string, unknown>;
  const snapshot = packet.listing_snapshot as
    Record<string, unknown> | undefined;
  const match = /^虚构示例楼 ([1-9]|[12]\d|30) 号房（不存在的地址）$/.exec(
    address,
  );
  if (
    !match ||
    packet.data_mode !== "synthetic_demo" ||
    !snapshot ||
    snapshot.source !== "synthetic-fixture" ||
    snapshot.data_kind !== "synthetic" ||
    snapshot.listing_id !== packet.listing_id ||
    snapshot.source_listing_id !== `fixture-${match[1]}` ||
    snapshot.address !== address
  )
    return address;
  return `Fictional Example Building, Unit ${match[1]} (nonexistent demo address)`;
}
