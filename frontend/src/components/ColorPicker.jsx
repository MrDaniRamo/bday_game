// A row of color swatches. Colors another team already uses are disabled.
export default function ColorPicker({ colors, taken, value, onChange }) {
  return (
    <div className="swatches" role="radiogroup" aria-label="Team color">
      {colors.map((color) => {
        const isTaken = taken.includes(color);
        return (
          <button
            key={color}
            type="button"
            role="radio"
            aria-checked={value === color}
            aria-label={isTaken ? `${color} (taken)` : color}
            className={`swatch ${value === color ? "picked" : ""}`}
            style={{ background: color }}
            disabled={isTaken}
            onClick={() => onChange(color)}
          />
        );
      })}
    </div>
  );
}
