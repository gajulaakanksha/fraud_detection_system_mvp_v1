// Matches the backend's actual 4-band decision_band exactly (band_resolver.py
// / decision_thresholds table) -- lowercase, snake_case, no invented states.
export const DECISION_META = {
  monitor: { label: "Monitor", color: "var(--status-good)", icon: "eye" },
  step_up_auth: { label: "Step-up auth", color: "var(--status-warning)", icon: "shield" },
  manual_review: { label: "Manual review", color: "var(--status-serious)", icon: "flag" },
  decline: { label: "Decline", color: "var(--status-critical)", icon: "x" },
};

export const DECISION_ORDER = ["monitor", "step_up_auth", "manual_review", "decline"];

// Matches report_service.py's RISK_LEVEL_CASE exactly: <25 low, <50 medium,
// <75 high, else critical. Independent of decision_band -- see
// IMPLEMENTATION_NOTES.md Phase 3 for why the two are deliberately separate.
export const RISK_LEVEL_META = {
  low: { label: "Low", color: "var(--risk-low)" },
  medium: { label: "Medium", color: "var(--risk-medium)" },
  high: { label: "High", color: "var(--risk-high)" },
  critical: { label: "Critical", color: "var(--status-critical)" },
};

export const SEVERITY_META = {
  low: { label: "Low", color: "var(--status-good)" },
  medium: { label: "Medium", color: "var(--status-warning)" },
  high: { label: "High", color: "var(--status-serious)" },
  critical: { label: "Critical", color: "var(--status-critical)" },
};
