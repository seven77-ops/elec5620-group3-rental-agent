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
            ? "联系负责人，或记录已联系的情况"
            : "记录对方回复与处理进展",
        label: `处理报修：${repair.title}`,
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
        title: provider?.name || "服务记录",
        note:
          booking.status === "booked"
            ? `查看自己记录的预约${booking.service_date ? ` · ${booking.service_date}` : "，核对服务日期"}`
            : "核对收到的报价和服务日期",
        label: `处理服务：${provider?.name || "服务记录"}`,
        tab: "services",
        booking: booking.booking_id,
      });
    }
  }
  if (record.profile.move_out_date)
    todos.push({
      key: "moveout",
      title: "退租计划",
      note: `已填写预计退租日期 ${record.profile.move_out_date}`,
      label: "查看退租事项",
      tab: "moveout",
    });
  if (
    (record.profile.address || record.repairs.length) &&
    !record.profile.agent_email &&
    !record.profile.agent_phone
  )
    todos.push({
      key: "contacts",
      title: "补充中介或房东联系方式",
      note: "填写邮箱或电话，方便报修联系",
      label: "填写联系人",
      tab: "contacts",
    });
  if (!todos.length) return null;
  return (
    <section className="living-todos" aria-label="待办事项">
      <div className="living-todos-heading">
        <h2>
          待办事项 <small>{todos.length} 项</small>
        </h2>
        {todos.length > 5 && (
          <Button
            type="text"
            size="small"
            onClick={() => setAll((value) => !value)}
          >
            {all ? "收起待办" : "查看全部待办"}
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
        <p className="muted">暂无待跟进事项。</p>
      )}
    </section>
  );
}
