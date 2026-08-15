"""Risk level is a pure score-descriptive banding (low/medium/high/critical),
independent of decision_band -- decision_band is action-oriented and folds in
rule overrides (band_resolver.py), risk_level is not.

Single Python source of truth for the cutoffs. report_service.py's SQL `case()`
needs the same three numbers as a query predicate (SQL can't call into this
function), so it imports RISK_LEVEL_CUTOFFS from here rather than repeating
the literals -- if these are ever retuned, there's exactly one place to edit
for the Python side, and the SQL side is built from the same values instead
of a second hardcoded copy.
"""

RISK_LEVEL_CUTOFFS = (25, 50, 75)  # low < 25, medium < 50, high < 75, else critical


def risk_level_from_score(risk_score: float) -> str:
    low, medium, high = RISK_LEVEL_CUTOFFS
    if risk_score < low:
        return "low"
    if risk_score < medium:
        return "medium"
    if risk_score < high:
        return "high"
    return "critical"
