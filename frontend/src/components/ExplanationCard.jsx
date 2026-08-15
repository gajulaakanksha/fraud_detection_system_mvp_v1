import Icon from "./Icon";
import { DECISION_META } from "../lib/decisions";
import "./ExplanationCard.css";

export default function ExplanationCard({ response }) {
  const meta = DECISION_META[response.decision_band] ?? { color: "var(--text-muted)", icon: "flag" };
  const factors = response.contributing_factors ?? [];

  return (
    <div className="explain-card" style={{ "--card-color": meta.color }}>
      <div className="explain-summary">
        <Icon name="sparkle" size={16} color={meta.color} />
        <p>{response.summary_reason}</p>
      </div>

      {factors.length > 0 && (
        <ul className="explain-reasons">
          {factors.map((text) => (
            <li key={text}>
              <Icon name="check" size={13} color="var(--text-muted)" />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="explain-action" style={{ "--action-color": meta.color }}>
        <div className="explain-action-icon">
          <Icon name={meta.icon} size={17} color={meta.color} />
        </div>
        <div className="explain-action-body">
          <span className="explain-action-label">Recommended action</span>
          <strong>{response.recommended_action.label}</strong>
          <p>{response.recommended_action.detail}</p>
        </div>
      </div>
    </div>
  );
}
