"""Deterministic rules evaluated alongside the model score (blueprint
Section 3.5's hybrid design). These give (a) explainability independent of
SHAP, (b) a way to hard-force a Decline regardless of model score for
"critical"-severity rules (none configured by default -- this dataset has
no sanctioned-country/OFAC list; the mechanism is here for when one exists),
and (c) an audit story: "declined because rule Y fired," not just "the
model said so."
"""
from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from app.models.rule import Rule


@dataclass
class RuleHit:
    rule: Rule
    detail: dict


def evaluate_rules(db: Session, feature_row: pd.DataFrame) -> list[RuleHit]:
    row = feature_row.iloc[0]
    active_rules = {r.rule_code: r for r in db.query(Rule).filter(Rule.is_active.is_(True)).all()}
    hits: list[RuleHit] = []

    def fire(code: str, detail: dict) -> None:
        rule = active_rules.get(code)
        if rule is not None:
            hits.append(RuleHit(rule=rule, detail=detail))

    if row["transaction_country"] != row["customer_home_country"]:
        fire("CROSS_BORDER_TRANSACTION", {
            "transaction_country": row["transaction_country"], "customer_home_country": row["customer_home_country"],
        })

    if row["ip_country"] != row["customer_home_country"]:
        fire("IP_COUNTRY_MISMATCH", {
            "ip_country": row["ip_country"], "customer_home_country": row["customer_home_country"],
        })

    if row["ip_country"] != row["transaction_country"]:
        fire("TRANSACTION_COUNTRY_MISMATCH", {
            "ip_country": row["ip_country"], "transaction_country": row["transaction_country"],
        })

    if bool(row["is_new_device"]):
        fire("NEW_DEVICE", {})

    high_risk_rule = active_rules.get("HIGH_RISK_CUSTOMER")
    threshold = (high_risk_rule.config or {}).get("risk_score_threshold", 70) if high_risk_rule else 70
    if row["customer_risk_score"] >= threshold:
        fire("HIGH_RISK_CUSTOMER", {"customer_risk_score": float(row["customer_risk_score"]), "threshold": threshold})

    amount_rule = active_rules.get("AMOUNT_ABOVE_2X_BASELINE")
    multiplier = (amount_rule.config or {}).get("multiplier", 2.0) if amount_rule else 2.0
    if row["amount_to_avg_ratio"] >= multiplier:
        fire("AMOUNT_ABOVE_2X_BASELINE", {"amount_to_avg_ratio": float(row["amount_to_avg_ratio"]), "multiplier": multiplier})

    return hits
