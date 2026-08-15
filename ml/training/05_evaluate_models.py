"""Stage 05 -- Model Evaluation (validation set only).

Computes, for each of the four trained models: PR-AUC, ROC-AUC, Recall @
fixed FPR (1%/5%/10% -- comparing all models at the SAME operating point,
not each at its own self-serving threshold), Precision @ operating point,
Precision @ K, Dollar Recall / Dollar Capture (+ dollar-weighted false
positive burden), Calibration (Brier score + reliability curve), Latency /
Throughput, and Temporal (weekly) stability. Fraud-type coverage is reported
at the FPR=5% operating point, matching the blueprint's stated FPR target.

This stage produces a ranked comparison but does NOT pick a final champion
by itself -- see 07_business_value_simulation.py, which folds in dollar
economics and policy constraints before that call is made.

Usage (from ml/training/, after 04_train_models.py):
    python 05_evaluate_models.py
"""
import json

import pandas as pd

from common import (
    ARTIFACTS_DIR, MODEL_NAMES, calibration_report, dollar_capture,
    fraud_type_recall, load_scores, load_split, pr_auc, precision_at_k,
    precision_at_threshold, recall_at_fpr, roc_auc, weekly_stability,
)

FPR_OPERATING_POINT = 0.05  # matches blueprint's "single-digit FPR" target


def evaluate_model(name: str) -> dict:
    val = load_scores(name, "val")
    y = val["fraud_label"].to_numpy()
    scores = val["score"].to_numpy()
    amount = val["amount"].to_numpy()

    recall_at_1 = recall_at_fpr(y, scores, 0.01)
    recall_at_5 = recall_at_fpr(y, scores, 0.05)
    recall_at_10 = recall_at_fpr(y, scores, 0.10)

    op_threshold = recall_at_5["threshold"]
    precision_op = precision_at_threshold(y, scores, op_threshold)
    dollars = dollar_capture(y, scores, amount, op_threshold)
    fraud_types = fraud_type_recall(y, scores, val["fraud_type"].to_numpy(), op_threshold)
    calib = calibration_report(y, scores)
    weekly = weekly_stability(val)

    metrics = {
        "pr_auc": pr_auc(y, scores),
        "roc_auc": roc_auc(y, scores),
        "recall_at_fpr_1pct": recall_at_1,
        "recall_at_fpr_5pct": recall_at_5,
        "recall_at_fpr_10pct": recall_at_10,
        "precision_at_operating_point_fpr5pct": precision_op,
        "precision_at_k_1000": precision_at_k(y, scores, 1000),
        "precision_at_k_5000": precision_at_k(y, scores, 5000),
        "dollar_capture_at_operating_point": dollars,
        "calibration": calib,
        "fraud_type_recall_at_operating_point": fraud_types,
        "weekly_stability": weekly,
        "weekly_pr_auc_std": float(pd.Series([w["pr_auc"] for w in weekly]).std()) if weekly else None,
    }
    return metrics


def main() -> None:
    all_results = {}
    for name in MODEL_NAMES:
        print(f"\n=== {name} ===")
        m = evaluate_model(name)
        all_results[name] = m
        print(f"  PR-AUC={m['pr_auc']:.4f}  ROC-AUC={m['roc_auc']:.4f}")
        print(f"  Recall@FPR=1%:  {m['recall_at_fpr_1pct']['recall']:.3f}")
        print(f"  Recall@FPR=5%:  {m['recall_at_fpr_5pct']['recall']:.3f}")
        print(f"  Recall@FPR=10%: {m['recall_at_fpr_10pct']['recall']:.3f}")
        print(f"  Precision@op(FPR=5%): {m['precision_at_operating_point_fpr5pct']['precision']:.3f}")
        print(f"  Precision@K=1000: {m['precision_at_k_1000']['precision']:.3f}")
        print(f"  Dollar recall @op: {m['dollar_capture_at_operating_point']['dollar_recall']:.3f}"
              f"  (FP $ burden: {m['dollar_capture_at_operating_point']['false_positive_dollar_burden']:.0f})")
        print(f"  Brier score: {m['calibration']['brier_score']:.4f}")
        print(f"  Weekly PR-AUC std: {m['weekly_pr_auc_std']:.4f}" if m["weekly_pr_auc_std"] is not None else "  Weekly stability: n/a")
        print("  Fraud-type recall @op:")
        for ft, r in m["fraud_type_recall_at_operating_point"].items():
            print(f"    {ft:<24s} {r:.3f}" if r is not None else f"    {ft:<24s} n/a")

    # Comparison table across the headline metrics
    print("\n\n=== COMPARISON (validation set) ===")
    header = f"{'model':<22s}{'PR-AUC':>9s}{'ROC-AUC':>9s}{'Rec@5%FPR':>11s}{'Prec@op':>9s}{'$Recall':>9s}{'Brier':>8s}"
    print(header)
    for name, m in all_results.items():
        print(f"{name:<22s}{m['pr_auc']:>9.4f}{m['roc_auc']:>9.4f}"
              f"{m['recall_at_fpr_5pct']['recall']:>11.3f}"
              f"{m['precision_at_operating_point_fpr5pct']['precision']:>9.3f}"
              f"{m['dollar_capture_at_operating_point']['dollar_recall']:>9.3f}"
              f"{m['calibration']['brier_score']:>8.4f}")

    ranked = sorted(all_results.items(), key=lambda kv: -kv[1]["pr_auc"])
    print(f"\nRanked by PR-AUC: {' > '.join(n for n, _ in ranked)}")

    (ARTIFACTS_DIR / "05_evaluation_report.json").write_text(json.dumps(all_results, indent=2))
    print("\nWrote ml/artifacts/05_evaluation_report.json")
    print("NOTE: latency benchmark runs separately in 05b_latency_benchmark.py (needs raw models, not just scores).")


if __name__ == "__main__":
    main()
