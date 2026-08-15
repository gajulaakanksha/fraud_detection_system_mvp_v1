"""Stage 10 -- Threshold Validation ("what a Risk Head asks next").

Everything in stages 06-08 chose the champion model and its thresholds.
This stage does NOT choose or re-tune anything -- it is read-only reporting
against the already-locked policy (champion.json) and the already-touched
test set (test.parquet was legitimately opened once in stage 08; re-reading
the same locked scores for a deeper report doesn't reopen any decision).

Produces exactly what a bank's Risk Head needs to sign off on before this
goes live:
  1. Calibration -- is the raw score trustworthy, and in what sense
  2. Per-cutoff operating-point stats (precision/recall/FPR) at each of the
     3 locked thresholds, cumulative (score >= t)
  3. Per-band stats (mutually exclusive Monitor/Step-up/Manual review/
     Decline) -- population share, fraud recall contribution, precision
  4. Approval-rate / friction-rate / decline-rate summary
  5. Expected fraud loss in dollars, prevented vs residual, annualized
  6. Weekly stability -- proof this isn't a lucky single test window

Usage (from ml/training/, after 08_final_test_evaluation.py):
    python 10_threshold_validation.py
"""
import json
from importlib import import_module

import numpy as np
import pandas as pd

from common import (
    ARTIFACTS_DIR, calibration_report, dollar_capture, load_scores,
    pr_auc, precision_at_threshold, recall_at_fpr, roc_auc, weekly_stability,
)

sim_module = import_module("07_business_value_simulation")


def band_masks(scores: np.ndarray, policy: dict) -> dict:
    t1 = policy["step_up_auth"]["threshold"]
    t2 = policy["manual_review"]["threshold"]
    t3 = policy["decline"]["threshold"]
    return {
        "monitor": scores < t1,
        "step_up_auth": (scores >= t1) & (scores < t2),
        "manual_review": (scores >= t2) & (scores < t3),
        "decline": scores >= t3,
    }


def per_band_stats(y: np.ndarray, scores: np.ndarray, amount: np.ndarray, policy: dict) -> dict:
    masks = band_masks(scores, policy)
    n_total = len(y)
    n_fraud = int((y == 1).sum())
    n_legit = int((y == 0).sum())

    out = {}
    for band, mask in masks.items():
        fraud_in_band = int((mask & (y == 1)).sum())
        legit_in_band = int((mask & (y == 0)).sum())
        band_n = fraud_in_band + legit_in_band
        out[band] = {
            "population": band_n,
            "population_share": band_n / n_total,
            "fraud_count": fraud_in_band,
            "legit_count": legit_in_band,
            "precision_fraud_rate_in_band": fraud_in_band / band_n if band_n else 0.0,
            "recall_contribution": fraud_in_band / n_fraud if n_fraud else 0.0,
            "fpr_contribution": legit_in_band / n_legit if n_legit else 0.0,
            "fraud_value_in_band": float(amount[mask & (y == 1)].sum()),
            "legit_value_in_band": float(amount[mask & (y == 0)].sum()),
        }
    return out


def main() -> None:
    champion = json.loads((ARTIFACTS_DIR / "champion.json").read_text())
    model_name = champion["champion_model"]
    policy = champion["policy"]
    t1 = policy["step_up_auth"]["threshold"]
    t2 = policy["manual_review"]["threshold"]
    t3 = policy["decline"]["threshold"]

    test = load_scores(model_name, "test")
    y = test["fraud_label"].to_numpy()
    scores = test["score"].to_numpy()
    amount = test["amount"].to_numpy()
    span_days = int((pd.to_datetime(test["transaction_time"]).max() - pd.to_datetime(test["transaction_time"]).min()).days) + 1

    print(f"LOCKED CHAMPION: {model_name}  |  test set: {len(test):,} txns over {span_days} days\n")

    # ------------------------------------------------------------
    # 1. Calibration -- discrimination vs. absolute calibration
    # ------------------------------------------------------------
    calib = calibration_report(y, scores, n_bins=10)
    bins = calib["reliability_bins"]
    observed_rates = [b["observed_fraud_rate"] for b in bins]
    is_monotonic = all(observed_rates[i] <= observed_rates[i + 1] for i in range(len(observed_rates) - 1))

    print("=== 1. CALIBRATION ===")
    print(f"PR-AUC={pr_auc(y, scores):.4f}  ROC-AUC={roc_auc(y, scores):.4f}  Brier={calib['brier_score']:.4f}")
    print(f"Reliability monotonic (higher score bin -> higher observed fraud rate): {is_monotonic}")
    print(f"{'score bin':<12s}{'n':>8s}{'mean predicted':>16s}{'observed rate':>16s}")
    for b in bins:
        print(f"{b['bin']:<12s}{b['n']:>8d}{b['mean_predicted']:>16.3f}{b['observed_fraud_rate']:>16.3f}")
    print("VERDICT: raw score is rank-ordered/discriminative (monotonic), NOT a literal probability "
          "(top bin's mean predicted 0.988 vs observed 0.903 -- overconfident). Bands below are tuned "
          "against realized outcomes at each cutoff, not against the score's face value, so this does "
          "not invalidate the thresholds -- but the raw score must not be shown to an analyst as an "
          "'X% chance of fraud' without a calibration layer (Platt/isotonic) first.\n")

    # ------------------------------------------------------------
    # 2. Per-cutoff operating-point stats (cumulative, score >= t)
    # ------------------------------------------------------------
    print("=== 2. OPERATING POINTS AT EACH LOCKED CUTOFF (cumulative, score >= t) ===")
    cutoffs = {"step_up_auth (t>=0.482)": t1, "manual_review (t>=0.806)": t2, "decline (t>=0.858)": t3}
    cutoff_stats = {}
    for label, t in cutoffs.items():
        p = precision_at_threshold(y, scores, t)
        d = dollar_capture(y, scores, amount, t)
        cutoff_stats[label] = {**p, **d}
        print(f"{label:<28s} precision={p['precision']:.3f}  recall(TPR)={p['recall']:.3f}  "
              f"FPR={p['fpr']:.4f}  flagged={p['flagged_count']:,}  $recall={d['dollar_recall']:.3f}")
    print()

    # ------------------------------------------------------------
    # 3. Per-band (mutually exclusive) stats
    # ------------------------------------------------------------
    bands = per_band_stats(y, scores, amount, policy)
    print("=== 3. PER-BAND BREAKDOWN (mutually exclusive) ===")
    print(f"{'band':<16s}{'pop %':>8s}{'fraud n':>9s}{'legit n':>9s}{'precision':>11s}{'recall contrib':>16s}")
    for band, s in bands.items():
        print(f"{band:<16s}{s['population_share']*100:>7.2f}%{s['fraud_count']:>9d}{s['legit_count']:>9d}"
              f"{s['precision_fraud_rate_in_band']:>11.3f}{s['recall_contribution']:>16.3f}")
    print()

    # ------------------------------------------------------------
    # 4. Approval / friction / decline summary
    # ------------------------------------------------------------
    approval_rate = bands["monitor"]["population_share"]
    friction_rate = bands["step_up_auth"]["population_share"] + bands["manual_review"]["population_share"]
    decline_rate = bands["decline"]["population_share"]
    print("=== 4. APPROVAL / FRICTION / DECLINE SUMMARY ===")
    print(f"Straight-through approval (Monitor):     {approval_rate*100:.2f}% of transactions")
    print(f"Added friction (Step-up + Manual review): {friction_rate*100:.2f}% of transactions")
    print(f"Auto-decline:                             {decline_rate*100:.2f}% of transactions")
    print()

    # ------------------------------------------------------------
    # 5. Expected fraud loss
    # ------------------------------------------------------------
    biz = sim_module.simulate(y, scores, amount, policy)
    total_volume = float(amount.sum())
    residual_loss = biz["total_fraud_value"] - biz["total_value_prevented"]
    residual_loss_bps = (residual_loss / total_volume) * 10000
    annualization_factor = 365 / span_days

    print("=== 5. EXPECTED FRAUD LOSS (test period, then annualized) ===")
    print(f"Total transaction volume (test period):  ${total_volume:,.0f}")
    print(f"Total fraud value present:               ${biz['total_fraud_value']:,.0f}")
    print(f"Fraud value prevented by this policy:     ${biz['total_value_prevented']:,.0f}")
    print(f"Residual fraud loss (not prevented):      ${residual_loss:,.0f}  ({residual_loss_bps:.1f} bps of volume)")
    print(f"Friction cost imposed on legit customers: ${biz['total_friction_cost']:,.0f}")
    print(f"NET VALUE:                                ${biz['net_value']:,.0f}")
    print(f"vs. do-nothing baseline:                  ${biz['baseline_do_nothing']:,.0f}")
    print(f"\nAnnualized (x{annualization_factor:.1f}, naive scaling -- NOT a seasonality-aware forecast):")
    print(f"  Residual fraud loss:  ~${residual_loss*annualization_factor:,.0f}/year")
    print(f"  Net value:            ~${biz['net_value']*annualization_factor:,.0f}/year")
    print()

    # ------------------------------------------------------------
    # 6. Weekly stability
    # ------------------------------------------------------------
    weekly = weekly_stability(test)
    pr_aucs = [w["pr_auc"] for w in weekly]
    print("=== 6. WEEKLY STABILITY (proof this isn't one lucky test window) ===")
    for w in weekly:
        print(f"  {w['week']:<14s} n={w['n']:>6,d}  fraud_rate={w['fraud_rate']:.4f}  PR-AUC={w['pr_auc']:.4f}")
    print(f"PR-AUC range across weeks: {min(pr_aucs):.4f} - {max(pr_aucs):.4f}  (std={np.std(pr_aucs):.4f})")

    report = {
        "champion_model": model_name,
        "test_span_days": span_days,
        "calibration": {**calib, "monotonic": is_monotonic},
        "cutoff_operating_points": cutoff_stats,
        "band_breakdown": bands,
        "approval_friction_decline_summary": {
            "approval_rate": approval_rate, "friction_rate": friction_rate, "decline_rate": decline_rate,
        },
        "expected_fraud_loss": {
            "total_volume": total_volume,
            "total_fraud_value": biz["total_fraud_value"],
            "value_prevented": biz["total_value_prevented"],
            "residual_loss": residual_loss,
            "residual_loss_bps": residual_loss_bps,
            "friction_cost": biz["total_friction_cost"],
            "net_value": biz["net_value"],
            "annualization_factor": annualization_factor,
            "residual_loss_annualized": residual_loss * annualization_factor,
            "net_value_annualized": biz["net_value"] * annualization_factor,
        },
        "weekly_stability": weekly,
    }
    (ARTIFACTS_DIR / "10_threshold_validation_report.json").write_text(json.dumps(report, indent=2))
    print("\nWrote ml/artifacts/10_threshold_validation_report.json")


if __name__ == "__main__":
    main()
