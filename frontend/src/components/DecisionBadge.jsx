import Icon from "./Icon";
import { DECISION_META } from "../lib/decisions";
import "./Badges.css";

export default function DecisionBadge({ decision, size = "md" }) {
  const meta = DECISION_META[decision] ?? { label: decision, color: "var(--text-muted)", icon: "flag" };
  return (
    <span className={`badge badge-${size}`} style={{ "--badge-color": meta.color }}>
      <Icon name={meta.icon} size={size === "sm" ? 12 : 14} />
      {meta.label}
    </span>
  );
}
