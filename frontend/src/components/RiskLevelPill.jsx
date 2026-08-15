import { RISK_LEVEL_META } from "../lib/decisions";
import "./Badges.css";

export default function RiskLevelPill({ level }) {
  const meta = RISK_LEVEL_META[level] ?? { label: level, color: "var(--text-muted)" };
  return (
    <span className="severity-pill">
      <span className="dot" style={{ "--dot-color": meta.color }} />
      {meta.label}
    </span>
  );
}
