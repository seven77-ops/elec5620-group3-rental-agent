import { useState } from "react";
import { createRoot } from "react-dom/client";
import EnglishDateInput from "../src/components/EnglishDateInput";

function Harness() {
  const [date, setDate] = useState("2026-11-16");
  const [datetime, setDatetime] = useState("2026-11-16T09:30");
  const [time, setTime] = useState("09:30");
  return (
    <main>
      <label htmlFor="bounded-date">Bounded date</label>
      <EnglishDateInput
        id="bounded-date"
        value={date}
        onChange={setDate}
        min="2026-11-10"
        max="2026-11-20"
      />
      <output data-testid="date-value">{date}</output>
      <label htmlFor="local-datetime">Local date and time</label>
      <EnglishDateInput
        id="local-datetime"
        mode="datetime"
        value={datetime}
        onChange={setDatetime}
      />
      <output data-testid="datetime-value">{datetime}</output>
      <label htmlFor="local-time">Time</label>
      <EnglishDateInput
        id="local-time"
        mode="time"
        value={time}
        onChange={setTime}
      />
      <output data-testid="time-value">{time}</output>
      <button>Outside field</button>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Harness />);
