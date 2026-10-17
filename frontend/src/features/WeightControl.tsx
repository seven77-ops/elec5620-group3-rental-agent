import { InputNumber, Slider } from "antd";

/** One form field with two synchronized, keyboard-accessible input methods. */
export default function WeightControl({
  value = 0,
  onChange,
  id,
  dimension,
}: {
  value?: number;
  onChange?: (value: number) => void;
  id?: string;
  dimension: string;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 100px",
        gap: 16,
        alignItems: "center",
      }}
    >
      <Slider
        id={`${id}-slider`}
        ariaLabelForHandle={`${dimension}权重滑块`}
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(next) => onChange?.(next)}
        tooltip={{ formatter: (next) => `${Math.round((next ?? 0) * 100)}%` }}
      />
      <InputNumber
        id={id}
        aria-label={`${dimension}权重数值`}
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(next) => onChange?.(next ?? 0)}
      />
    </div>
  );
}
