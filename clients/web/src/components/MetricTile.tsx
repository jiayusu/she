export function MetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric-tile">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      <span className="metric-detail">{detail}</span>
    </div>
  );
}
