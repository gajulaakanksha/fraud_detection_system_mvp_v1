import "./ChartCard.css";

export default function ChartCard({ title, subtitle, accent, children }) {
  return (
    <div className="chart-card" style={accent ? { "--card-accent": accent } : undefined}>
      <div className="chart-card-head">
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
