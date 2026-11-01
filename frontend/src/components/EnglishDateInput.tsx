import { DatePicker } from "antd";
import enGB from "antd/es/date-picker/locale/en_GB";
import dayjs from "dayjs";

// Keep the ISO string contract of existing forms, while fixing the displayed
// language independently of the browser/OS's native date-input language.
export default function EnglishDateInput({
  value,
  onChange,
  mode = "date",
  min,
  max,
  ...props
}: {
  value?: string | null;
  onChange?: (value: string) => void;
  mode?: "date" | "datetime" | "time";
  min?: string;
  max?: string;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
}) {
  const parsed = value
    ? dayjs(mode === "time" ? `2000-01-01T${value}` : value)
    : null;
  const storedFormat =
    mode === "datetime"
      ? "YYYY-MM-DDTHH:mm"
      : mode === "time"
        ? "HH:mm"
        : "YYYY-MM-DD";
  const displayedFormat =
    mode === "datetime"
      ? "DD/MM/YYYY HH:mm"
      : mode === "time"
        ? "HH:mm"
        : "DD/MM/YYYY";
  return (
    <DatePicker
      {...props}
      locale={enGB}
      picker={mode === "time" ? "time" : "date"}
      showTime={mode === "datetime" ? { format: "HH:mm" } : false}
      needConfirm={false}
      format={[displayedFormat, storedFormat]}
      placeholder={displayedFormat}
      value={parsed?.isValid() ? parsed : null}
      minDate={min ? dayjs(min) : undefined}
      maxDate={max ? dayjs(max) : undefined}
      onChange={(selected) =>
        onChange?.(dayjs.isDayjs(selected) ? selected.format(storedFormat) : "")
      }
      style={{ width: "100%" }}
    />
  );
}
