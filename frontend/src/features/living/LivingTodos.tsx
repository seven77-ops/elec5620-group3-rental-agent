import { useState } from "react";
import { Button } from "antd";
import type { LivingProvider, LivingRecord } from "../../api/living";
interface Todo {
  key: string;
  title: string;
  note: string;
  label: string;
  tab: string;
  repair?: string;
  booking?: string;
}
export default function LivingTodos({
  record,
  providers,
  go,
}: {
  record: LivingRecord;
  providers: LivingProvider[];
  go: (tab: string, repair?: string, booking?: string) => void;
}) {
  const [all, setAll] = useState(false);
  const todos: Todo[] = [];
  for (const repair of record.repairs) {
    if (repair.status !== "resolved")
      todos.push({
        key: repair.repair_id,
        title: repair.title,
        note:
          repair.status === "prepared"
            ? "Contact the responsible person or record that you have contacted them"
            : "Record replies and progress",
        label: `Handle repair: ${repair.title}`,
        tab: "repairs",
        repair: repair.repair_id,
      });
  }
  const today = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Australia/Sydney",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  for (const booking of record.bookings) {
    if (
      booking.status === "considering" ||
      booking.status === "contacted" ||
      (booking.status === "booked" &&
        (!booking.service_date || booking.service_date >= today))
    ) {
      const provider = providers.find(
        (item) => item.id === booking.provider_id,
      );
      todos.push({
        key: booking.booking_id,
        title: provider?.name || "Service record",
        note:
          booking.status === "booked"
            ? `View your recorded booking ${booking.service_date ? ` · ${booking.service_date}` : " and check the service date"}`
            : "Check the quote received and service date",
        label: `Handle service: ${provider?.name || "Service record"}`,
        tab: "services",
        booking: booking.booking_id,
      });
    }
  }
  if (record.profile.move_out_date)
    todos.push({
      key: "moveout",
      title: "Move-out plan",
      note: `Expected move-out date entered: ${record.profile.move_out_date}`,
      label: "View move-out tasks",
      tab: "moveout",
    });
  if (
    (record.profile.address || record.repairs.length) &&
    !record.profile.agent_email &&
    !record.profile.agent_phone
  )
    todos.push({
      key: "contacts",
      title: "Add agent or landlord contact details",
      note: "Enter an email or phone number for repair contact",
      label: "Add contact",
      tab: "contacts",
    });
  if (!todos.length) return null;
  return (
    <section className="living-todos" aria-label="To-do items">
      <div className="living-todos-heading">
        <h2>
          To-do items <small>{todos.length} items</small>
        </h2>
        {todos.length > 5 && (
          <Button
            type="text"
            size="small"
            onClick={() => setAll((value) => !value)}
          >
            {all ? "Collapse to-do items" : "View all to-do items"}
          </Button>
        )}
      </div>
      {todos.length ? (
        <ul>
          {(all ? todos : todos.slice(0, 5)).map((todo) => (
            <li key={todo.key}>
              <button
                aria-label={todo.label}
                onClick={() => go(todo.tab, todo.repair, todo.booking)}
              >
                <div>
                  <strong>{todo.title}</strong>
                  <span>{todo.note}</span>
                </div>
                <span aria-hidden="true">↗</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No items awaiting follow-up.</p>
      )}
    </section>
  );
}
