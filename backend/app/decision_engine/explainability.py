"""SHAP-based explainability: turns the model's raw feature contributions
into (a) a plain-English summary + bullet factors for the analyst-facing UI,
(b) a structured factor list a frontend can render without string-parsing,
and (c) the full technical payload for the "Technical detail" panel.

Uses shap.TreeExplainer, which is fast enough for tree models to run inline
in the request path rather than needing to be precomputed (per the blueprint's
architecture notes on keeping single-transaction latency low) -- provided the
explainer itself is built once and cached, not per request (see
model_loader.py; this was a real 3.3s latency bug in an earlier pass).

Template phrasing is written so that device_age_days and is_new_device can
never read as contradictory when both are top factors: is_new_device is
explicitly about *this customer's* history with the device; device_age_days
is explicitly about the device's history *overall*, regardless of customer.
A device can genuinely be both "new to this customer" and "old in general"
(e.g. a shared family device, or one previously used by someone else) --
that's a real, useful signal, not a bug, but the wording has to say so
instead of leaving it for the reader to reconcile.
"""
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

CATEGORICAL_BASES = ("channel", "merchant_category", "customer_home_country", "transaction_country", "ip_country")

# (positive_phrase, negative_phrase) -- shown when SHAP pushes risk up vs down.
REASON_TEMPLATES: dict[str, tuple[str, str]] = {
    "amount": ("The transaction amount is unusually high.", "The transaction amount is in a typical range."),
    "amount_to_avg_ratio": (
        "The amount is far above this customer's typical spending pattern.",
        "The amount is consistent with this customer's typical spending.",
    ),
    "device_age_days": (
        "This device is very new overall (first seen recently, regardless of customer).",
        "This device has a long history overall, though not necessarily with this specific customer.",
    ),
    "account_age_days": ("This is a relatively new account.", "This is a long-standing account."),
    "transactions_last_10_minutes": (
        "Multiple transactions happened in a short window.", "Transaction velocity is normal.",
    ),
    "failed_attempts_last_24_hours": (
        "There were recent failed authentication attempts.", "No recent failed authentication attempts.",
    ),
    "days_since_last_transaction": (
        "The gap since this customer's last transaction is unusual.", "Transaction timing is typical for this customer.",
    ),
    "session_duration_seconds": (
        "The session duration is atypical for this customer.", "Session duration was typical.",
    ),
    "merchant_risk_score": ("This merchant has an elevated risk profile.", "This merchant has a low risk profile."),
    "customer_risk_score": ("This customer has an elevated risk profile.", "This customer has a low risk profile."),
    "is_new_device": (
        "This specific device has never been linked to this customer before.",
        "This device has a known history with this customer specifically.",
    ),
    "is_new_beneficiary": ("This is a new payee for this customer.", "This is a recognized beneficiary."),
    "is_cross_border": (
        "The customer's IP location differs from their home country.", "The customer's IP matches their home country.",
    ),
    "is_ip_merchant_country_mismatch": (
        "The IP country doesn't match where the transaction is occurring.", "IP and transaction country match.",
    ),
}


@dataclass
class ContributingFactor:
    feature: str
    category: Literal["numeric", "binary", "categorical"]
    value: str | None  # the matched category value, only set for categorical features
    shap_value: float
    direction: Literal["increases_risk", "decreases_risk"]
    explanation: str


def _structure(output_name: str, shap_value: float) -> ContributingFactor:
    prefix, _, rest = output_name.partition("__")
    direction = "increases_risk" if shap_value > 0 else "decreases_risk"

    if prefix == "cat":
        for base in CATEGORICAL_BASES:
            if rest.startswith(base + "_"):
                value = rest[len(base) + 1:]
                label = base.replace("_", " ").capitalize()
                verb = "contributed to the elevated risk" if shap_value > 0 else "is typical / lower-risk"
                return ContributingFactor(
                    feature=base, category="categorical", value=value, shap_value=shap_value,
                    direction=direction, explanation=f"{label} ({value}) {verb}.",
                )
        return ContributingFactor(
            feature=rest, category="categorical", value=None, shap_value=shap_value,
            direction=direction, explanation=f"{rest} contributed to the risk assessment.",
        )

    category = "binary" if prefix == "bin" else "numeric"
    if rest in REASON_TEMPLATES:
        pos, neg = REASON_TEMPLATES[rest]
        explanation = pos if shap_value > 0 else neg
    else:
        explanation = f"{rest.replace('_', ' ').capitalize()} contributed to the risk assessment."
    return ContributingFactor(
        feature=rest, category=category, value=None, shap_value=shap_value,
        direction=direction, explanation=explanation,
    )


@dataclass
class Explanation:
    summary_reason: str
    contributing_factors: list[str]              # flat strings, for simple display
    contributing_factors_detail: list[ContributingFactor]  # structured, for a real frontend
    shap_values: dict[str, float]


def explain(shap_explainer, feature_row_transformed: np.ndarray, output_feature_names: list[str],
            risk_score_0_100: float, decision_band: str, top_n: int = 4) -> Explanation:
    raw = shap_explainer.shap_values(feature_row_transformed)

    values = raw[1][0] if isinstance(raw, list) else np.asarray(raw)[0]
    shap_values = {name: float(v) for name, v in zip(output_feature_names, values)}

    ranked = sorted(shap_values.items(), key=lambda kv: -abs(kv[1]))
    top_names = [name for name, _ in ranked[:top_n] if abs(shap_values[name]) > 1e-6]

    factors = [_structure(name, shap_values[name]) for name in top_names]
    contributing_factors = [f.explanation for f in factors]

    band_label = {
        "monitor": "LOW", "step_up_auth": "ELEVATED", "manual_review": "HIGH", "decline": "CRITICAL",
    }.get(decision_band, decision_band.upper())

    if factors:
        headline = contributing_factors[0][0].lower() + contributing_factors[0][1:]
        summary_reason = (
            f"This transaction was flagged as {band_label} risk (score {risk_score_0_100:.0f}/100), "
            f"mainly because {headline}"
        )
    else:
        summary_reason = f"This transaction scored {band_label} risk ({risk_score_0_100:.0f}/100), with no single dominant factor."

    return Explanation(
        summary_reason=summary_reason,
        contributing_factors=contributing_factors or ["No individual factor stood out; the score reflects a combination of small signals."],
        contributing_factors_detail=factors,
        shap_values=shap_values,
    )
