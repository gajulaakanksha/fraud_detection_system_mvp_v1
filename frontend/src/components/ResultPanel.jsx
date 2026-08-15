import { useEffect, useState } from "react";
import RiskGauge from "./RiskGauge";
import DecisionBadge from "./DecisionBadge";
import ExplanationCard from "./ExplanationCard";
import Icon from "./Icon";
import { SEVERITY_META } from "../lib/decisions";
import "./ResultPanel.css";

function AnimatedBar({ pct }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setWidth(pct));
    return () => cancelAnimationFrame(raf);
  }, [pct]);
  return (
    <div className="factor-bar-track">
      <div className="factor-bar-fill" style={{ width: `${width}%` }} />
    </div>
  );
}

export default function ResultPanel({ response }) {
  const factorsDetail = response.contributing_factors_detail ?? [];
  const maxImportance = Math.max(0.01, ...factorsDetail.map((f) => Math.abs(f.shap_value)));

  return (
    <div className="result-panel">
      <div className="result-top">
        <RiskGauge score={response.risk_score} level={response.risk_level} />
        <div className="result-decision">
          <DecisionBadge decision={response.decision_band} />
          {response.band_source === "rule_override" && (
            <span className="rule-override-note" title={`Band forced/bumped by rule ${response.override_rule ?? ""}`}>
              <Icon name="flag" size={12} />
              Rule override{response.override_rule ? `: ${response.override_rule}` : ""}
            </span>
          )}
        </div>
      </div>

      <ExplanationCard response={response} />

      <details className="tech-details">
        <summary>
          <Icon name="chevronRight" size={14} className="tech-chevron" />
          Technical detail
        </summary>

        <div className="tech-details-body">
          {response.rule_hits.length > 0 && (
            <section className="result-section">
              <h4>Rule hits</h4>
              <ul className="rule-hit-list">
                {response.rule_hits.map((hit) => {
                  const meta = SEVERITY_META[hit.severity] ?? { label: "—", color: "var(--text-muted)" };
                  return (
                    <li key={hit.rule_code} title={hit.description}>
                      <span className="dot" style={{ "--dot-color": meta.color }} />
                      <span className="rule-id">{hit.rule_code}</span>
                      <span className="rule-severity" style={{ color: meta.color }}>
                        {meta.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {factorsDetail.length > 0 && (
            <section className="result-section">
              <h4>Top model factors (SHAP)</h4>
              <div className="factor-list">
                {factorsDetail.map((f) => (
                  <div className="factor-row" key={f.feature}>
                    <span className="factor-name">
                      {f.feature}
                      {f.value ? ` = ${f.value}` : ""}
                    </span>
                    <AnimatedBar pct={(Math.abs(f.shap_value) / maxImportance) * 100} />
                    <span
                      className="factor-importance tabular"
                      style={{ color: f.direction === "increases_risk" ? "var(--status-critical)" : "var(--status-good)" }}
                    >
                      {f.shap_value >= 0 ? "+" : ""}
                      {f.shap_value.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="result-section">
            <h4>Decision metadata</h4>
            <dl className="meta-grid">
              <div>
                <dt>Transaction ID</dt>
                <dd>{response.transaction_id}</dd>
              </div>
              <div>
                <dt>Risk score</dt>
                <dd className="tabular" title="A risk score, not a calibrated probability -- see decision_band for the actual decision.">
                  {response.risk_score.toFixed(2)} / 100
                </dd>
              </div>
              <div>
                <dt>Total processing time</dt>
                <dd className="tabular">{response.processing_time_ms} ms</dd>
              </div>
              {response.inference_time_ms != null && (
                <div>
                  <dt>&nbsp;&nbsp;-- inference</dt>
                  <dd className="tabular">{response.inference_time_ms} ms</dd>
                </div>
              )}
              {response.explainability_time_ms != null && (
                <div>
                  <dt>&nbsp;&nbsp;-- explainability</dt>
                  <dd className="tabular">{response.explainability_time_ms} ms</dd>
                </div>
              )}
              <div>
                <dt>Model version</dt>
                <dd>{response.model_version}</dd>
              </div>
              <div>
                <dt>Decision policy</dt>
                <dd>{response.policy_version}</dd>
              </div>
              <div>
                <dt>Band source</dt>
                <dd>
                  {response.band_source === "rule_override"
                    ? `Rule override (${response.override_rule ?? "unknown rule"})`
                    : "Model score"}
                </dd>
              </div>
              <div>
                <dt>Decided at</dt>
                <dd>{new Date(response.decided_at).toLocaleString()}</dd>
              </div>
            </dl>
          </section>
        </div>
      </details>
    </div>
  );
}
