"""Stage 06 -- Economic Policy / Threshold Optimization.

Converts each model's raw score into a 4-band decision policy:
APPROVE (monitor, no friction) / STEP-UP AUTH / MANUAL REVIEW / DECLINE.

Method, per band boundary t (see common.ACTION_FP_COST for the cost inputs):
    net_value(t) = value_of_fraud_caught(score>=t) - fp_cost * count(legit flagged, score>=t)
Sweep candidate t on VALIDATION scores, pick the net-value-maximizing t,
subject to guardrails (never exceed the band's max FPR; flag, don't silently
accept, a TPR pinned near 100% -- that's a sign of a degenerate/too-low
threshold, not a win).

Two additional real-world constraints layered on top, because a threshold
that's optimal in isolation can still be operationally impossible:
  - REVIEW CAPACITY: the manual_review band's daily volume can't exceed what
    analysts can actually work (ANALYST_REVIEWS_PER_DAY_CAPACITY in common.py,
    a placeholder pending real staffing numbers). If the cost-optimal cutoff
    implies more volume than that, the threshold is raised until it fits.
  - ALERT VOLUME: total flagged volume (step_up + manual_review + decline)
    is capped at MAX_ALERT_VOLUME_SHARE of daily traffic, guarding against
    alert fatigue swamping the system with low-value flags.

Hard rule overrides (sanctioned-country hits, OFAC matches) are NOT part of
this sweep -- those bypass the score entirely per the blueprint's hybrid
rules+ML design (Section 3.5) and always resolve to DECLINE regardless of
what the model says.

Usage (from ml/training/, after 04_train_models.py):
    python 06_threshold_policy.py
"""
import json

import numpy as np
import pandas as pd

from common import (
    ACTION_FP_COST, ANALYST_REVIEWS_PER_DAY_CAPACITY, ARTIFACTS_DIR, DATA_DIR,
    MAX_ALERT_VOLUME_SHARE, MODEL_NAMES, load_scores,
)

ACTION_CONSTRAINTS = {
    "step_up_auth": {"fp_cost": ACTION_FP_COST["step_up_auth"], "max_fpr": 0.15, "max_tpr": 0.98},
    "manual_review": {"fp_cost": ACTION_FP_COST["manual_review"], "max_fpr": 0.05, "max_tpr": 0.98},
    "decline": {"fp_cost": ACTION_FP_COST["decline"], "max_fpr": 0.01, "max_tpr": 0.95},
}
MIN_TPR_FLOOR = 0.30  # below this, the system isn't doing its job -- flag, don't auto-fix


def sweep_threshold(y_true, scores, amount, fp_cost, max_fpr, max_tpr):
    n_legit = (y_true == 0).sum()
    n_fraud = (y_true == 1).sum()
    candidates = np.unique(np.quantile(scores, np.linspace(0, 1, 500)))

    rows = []
    for t in candidates:
        flagged = scores >= t
        tp = flagged & (y_true == 1)
        fp = flagged & (y_true == 0)
        tpr = tp.sum() / n_fraud if n_fraud else 0.0
        fpr = fp.sum() / n_legit if n_legit else 0.0
        value_caught = amount[tp].sum()
        net_value = value_caught - fp_cost * fp.sum()
        rows.append((t, tpr, fpr, value_caught, fp.sum(), net_value))
    df = pd.DataFrame(rows, columns=["threshold", "tpr", "fpr", "value_caught", "fp_count", "net_value"])

    feasible = df[(df["fpr"] <= max_fpr) & (df["tpr"] <= max_tpr)]
    fallback = False
    if feasible.empty:
        feasible = df[df["fpr"] <= max_fpr]
        fallback = True
    if feasible.empty:
        best = df.sort_values("threshold", ascending=False).iloc[0]
    else:
        best = feasible.loc[feasible["net_value"].idxmax()]

    return {
        "threshold": float(best["threshold"]), "tpr": float(best["tpr"]), "fpr": float(best["fpr"]),
        "value_caught": float(best["value_caught"]), "fp_count": int(best["fp_count"]),
        "net_value": float(best["net_value"]), "guardrail_fallback_used": fallback,
        "tpr_below_floor": bool(best["tpr"] < MIN_TPR_FLOOR),
    }


def threshold_for_band_count(scores, upper_bound_mask, target_count):
    """Smallest score t such that count(t <= score, upper_bound_mask) <= target_count."""
    candidates = scores[upper_bound_mask]
    if len(candidates) <= target_count:
        return float(candidates.min()) if len(candidates) else 0.0
    sorted_desc = np.sort(candidates)[::-1]
    return float(sorted_desc[target_count - 1])


def build_policy(y_true, scores, amount, span_days: int) -> dict:
    n = len(y_true)
    daily_volume = n / span_days

    decline = sweep_threshold(y_true, scores, amount, **ACTION_CONSTRAINTS["decline"])
    t3 = decline["threshold"]

    manual_review = sweep_threshold(y_true, scores, amount, **ACTION_CONSTRAINTS["manual_review"])
    band_mask = scores < t3
    band_count = int(((scores >= manual_review["threshold"]) & band_mask).sum())
    band_daily = band_count / span_days
    capacity_note = None
    if band_daily > ANALYST_REVIEWS_PER_DAY_CAPACITY:
        target_count = int(ANALYST_REVIEWS_PER_DAY_CAPACITY * span_days)
        t2_capacity = threshold_for_band_count(scores, band_mask, target_count)
        if t2_capacity > manual_review["threshold"]:
            capacity_note = (f"cost-optimal manual_review threshold implied {band_daily:.0f}/day, "
                              f"exceeding capacity ({ANALYST_REVIEWS_PER_DAY_CAPACITY}/day); raised threshold "
                              f"{manual_review['threshold']:.4f} -> {t2_capacity:.4f}")
            manual_review["threshold"] = t2_capacity
    t2 = manual_review["threshold"]

    step_up = sweep_threshold(y_true, scores, amount, **ACTION_CONSTRAINTS["step_up_auth"])
    total_flagged_daily = (scores >= step_up["threshold"]).sum() / span_days
    alert_note = None
    max_alert_volume = MAX_ALERT_VOLUME_SHARE * daily_volume
    if total_flagged_daily > max_alert_volume:
        target_count = int(max_alert_volume * span_days)
        t1_alert = threshold_for_band_count(scores, np.ones_like(scores, dtype=bool), target_count)
        if t1_alert > step_up["threshold"]:
            alert_note = (f"cost-optimal step_up threshold implied {total_flagged_daily:.0f}/day flagged total, "
                           f"exceeding alert-volume cap ({max_alert_volume:.0f}/day); raised threshold "
                           f"{step_up['threshold']:.4f} -> {t1_alert:.4f}")
            step_up["threshold"] = t1_alert
    t1 = min(step_up["threshold"], t2)  # preserve ordering; collapse band if capacity pushed t1 past t2
    if t1 < step_up["threshold"]:
        alert_note = (alert_note or "") + " | clamped to manual_review threshold to preserve band ordering"
    step_up["threshold"] = t1

    return {
        "step_up_auth": {**step_up, "capacity_note": alert_note},
        "manual_review": {**manual_review, "capacity_note": capacity_note},
        "decline": decline,
        "daily_volume_estimate": daily_volume,
    }


def main() -> None:
    meta = json.loads((DATA_DIR / "meta.json").read_text())
    span_days = meta["val_span_days"]

    all_policies = {}
    for name in MODEL_NAMES:
        val = load_scores(name, "val")
        y = val["fraud_label"].to_numpy()
        scores = val["score"].to_numpy()
        amount = val["amount"].to_numpy()

        policy = build_policy(y, scores, amount, span_days)
        all_policies[name] = policy

        print(f"\n=== {name} ===")
        for band in ["step_up_auth", "manual_review", "decline"]:
            b = policy[band]
            flag = "  ** TPR BELOW FLOOR **" if b["tpr_below_floor"] else ""
            print(f"  {band:<14s} t={b['threshold']:.4f}  TPR={b['tpr']:.3f}  FPR={b['fpr']:.3f}  "
                  f"net_value=${b['net_value']:,.0f}{flag}")
            if b.get("capacity_note"):
                print(f"    note: {b['capacity_note']}")

    (ARTIFACTS_DIR / "06_threshold_policy_report.json").write_text(json.dumps(all_policies, indent=2))
    print("\nWrote ml/artifacts/06_threshold_policy_report.json")


if __name__ == "__main__":
    main()
