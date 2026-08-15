import Icon from "./Icon";
import "./StatTile.css";

export default function StatTile({ label, value, sublabel, accent, icon, color }) {
  return (
    <div className="stat-tile" style={color ? { "--tile-color": color } : undefined}>
      {icon && (
        <div className="stat-icon">
          <Icon name={icon} size={16} color={color ?? "var(--brand)"} />
        </div>
      )}
      <div className="stat-label">{label}</div>
      <div className="stat-value tabular" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {sublabel && <div className="stat-sublabel">{sublabel}</div>}
    </div>
  );
}
