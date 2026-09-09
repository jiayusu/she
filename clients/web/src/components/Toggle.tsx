export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <span className="switch">
      <input
        type="checkbox"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="switch-track" />
      <span className="switch-thumb" />
    </span>
  );
}
