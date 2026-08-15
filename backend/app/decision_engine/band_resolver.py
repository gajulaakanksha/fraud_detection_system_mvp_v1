"""Combines model score + rule hits into the final decision band, reading
cutoffs from decision_thresholds (FR5: configurable without a deploy) rather
than hardcoding them.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.decision_engine.rules_engine import RuleHit
from app.models.decision_threshold import DecisionThreshold

BAND_ORDER = ["monitor", "step_up_auth", "manual_review", "decline"]


@dataclass
class BandResult:
    band: str
    recommended_action: str
    policy_version: str
    # "model_score" if band came straight from the score-vs-threshold lookup,
    # "rule_override" if a rule forced/bumped it -- lets a caller distinguish
    # "the model said so" from "a rule said so" instead of only ever seeing
    # the final band.
    source: str = "model_score"
    override_rule_code: str | None = None


def resolve_band(db: Session, risk_score_0_100: float, rule_hits: list[RuleHit]) -> BandResult:
    thresholds = {t.band: t for t in db.query(DecisionThreshold).all()}
    policy_version = next(iter(thresholds.values())).policy_version if thresholds else "unversioned"

    band = "decline"  # default if score exceeds every configured max_score
    for name in BAND_ORDER:
        t = thresholds.get(name)
        if t is None:
            continue
        if float(t.min_score) <= risk_score_0_100 < float(t.max_score) or (
            name == BAND_ORDER[-1] and risk_score_0_100 >= float(t.min_score)
        ):
            band = name
            break

    source = "model_score"
    override_rule_code = None

    # Hard override: a "critical"-severity rule always forces Decline,
    # regardless of model score (blueprint 3.5's auditable-override story).
    critical_hit = next((h for h in rule_hits if h.rule.severity == "critical"), None)
    high_hit = next((h for h in rule_hits if h.rule.severity == "high"), None)
    if critical_hit is not None and band != "decline":
        band = "decline"
        source = "rule_override"
        override_rule_code = critical_hit.rule.rule_code
    # A "high"-severity rule bumps a MONITOR verdict up one notch -- the
    # model alone doesn't get the last word when a real risk factor fired.
    elif band == "monitor" and high_hit is not None:
        band = "step_up_auth"
        source = "rule_override"
        override_rule_code = high_hit.rule.rule_code

    recommended_action = thresholds[band].recommended_action if band in thresholds else "Decline the transaction."
    return BandResult(
        band=band,
        recommended_action=recommended_action,
        policy_version=policy_version,
        source=source,
        override_rule_code=override_rule_code,
    )
