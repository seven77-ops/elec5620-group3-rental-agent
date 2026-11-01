import type { LivingProvider, LivingRecord } from "../../api/living";
export interface ProgressItem {
  id: string;
  title: string;
  status: string;
  tab: "repairs" | "services";
  repair?: string;
  booking?: string;
}
export function inProgressItems(
  record: LivingRecord,
  providers: LivingProvider[],
): ProgressItem[] {
  return [
    ...record.repairs
      .filter((repair) => repair.status !== "resolved")
      .map((repair) => ({
        id: repair.repair_id,
        title: repair.title,
        status: repair.status === "contacted" ? "Contacted" : "Draft prepared",
        tab: "repairs" as const,
        repair: repair.repair_id,
      })),
    ...record.bookings
      .filter((booking) => booking.status !== "completed")
      .map((booking) => ({
        id: booking.booking_id,
        title:
          providers.find((provider) => provider.id === booking.provider_id)
            ?.name ?? "Service record",
        status: {
          considering: "Considering",
          contacted: "Contacted",
          booked: "Booked",
          completed: "Completed",
        }[booking.status],
        tab: "services" as const,
        booking: booking.booking_id,
      })),
  ];
}
