"""Stage 08 -- Final Untouched Test Evaluation.

Everything up to this point -- model selection, threshold tuning, band
policy, champion selection -- happened on validation data only. test.parquet
has not been read since stage 03 created it. This is the one and only time
it gets touched: load the LOCKED champion model + LOCKED thresholds from
champion.json, score test, report final numbers. These are the numbers that
represent expected production performance; nothing downstream of this may
feed back into model or threshold choices (that would be the same leakage
this whole staged setup exists to avoid).

Usage (from ml/training/, after 07_business_value_simulation.py):
    python 08_final_test_evaluation.py
"""
import json

from common import (
    ARTIFACTS_DIR, calibration_report, dollar_capture, fraud_type_recall,
    load_scores, pr_auc, precision_at_k, precision_at_threshold, recall_at_fpr,
    roc_auc, weekly_stability,
)
from importlib import import_module

sim_module = import_module("07_business_value_simulation")


def main() -> None:
    champion = json.loads((ARTIFACTS_DIR / "champion.json").read_text())
    name = champion["champion_model"]
    policy = champion["policy"]
    op_threshold = policy["manual_review"]["threshold"]

    print(f"LOCKED CHAMPION: {name}")
    print("Reading test.parquet for the first and only time in this pipeline.\n")

    test = load_scores(name, "test")
    y = test["fraud_label"].to_numpy()
    scores = test["score"].to_numpy()
    amount = test["amount"].to_numpy()

    metrics = {
        "pr_auc": pr_auc(y, scores),
        "roc_auc": roc_auc(y, scores),
        "recall_at_fpr_1pct": recall_at_fpr(y, scores, 0.01),
        "recall_at_fpr_5pct": recall_at_fpr(y, scores, 0.05),
        "recall_at_fpr_10pct": recall_at_fpr(y, scores, 0.10),
        "precision_at_operating_point": precision_at_threshold(y, scores, op_threshold),
        "precision_at_k_1000": precision_at_k(y, scores, 1000),
        "dollar_capture_at_operating_point": dollar_capture(y, scores, amount, op_threshold),
        "calibration": calibration_report(y, scores),
        "fraud_type_recall_at_operating_point": fraud_type_recall(y, scores, test["fraud_type"].to_numpy(), op_threshold),
        "weekly_stability": weekly_stability(test),
    }

    business_value = sim_module.simulate(y, scores, amount, policy)

    print(f"PR-AUC:  {metrics['pr_auc']:.4f}")
    print(f"ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"Recall @ FPR=1%:  {metrics['recall_at_fpr_1pct']['recall']:.3f}")
    print(f"Recall @ FPR=5%:  {metrics['recall_at_fpr_5pct']['recall']:.3f}")
    print(f"Recall @ FPR=10%: {metrics['recall_at_fpr_10pct']['recall']:.3f}")
    print(f"Precision @ manual_review threshold: {metrics['precision_at_operating_point']['precision']:.3f}")
    print(f"Dollar recall @ manual_review threshold: {metrics['dollar_capture_at_operating_point']['dollar_recall']:.3f}")
    print(f"Brier score: {metrics['calibration']['brier_score']:.4f}")
    print("\nFraud-type recall @ operating point:")
    for ft, r in metrics["fraud_type_recall_at_operating_point"].items():
        print(f"  {ft:<24s} {r:.3f}" if r is not None else f"  {ft:<24s} n/a")

    print(f"\nBusiness value simulation on test set:")
    print(f"  Total fraud value: ${business_value['total_fraud_value']:,.0f}")
    print(f"  Value prevented:   ${business_value['total_value_prevented']:,.0f}")
    print(f"  Friction cost:     ${business_value['total_friction_cost']:,.0f}")
    print(f"  NET VALUE:         ${business_value['net_value']:,.0f}")
    print(f"  Improvement over do-nothing baseline: ${business_value['improvement_over_do_nothing']:,.0f}")

    report = {"champion_model": name, "policy": policy, "test_metrics": metrics, "business_value": business_value}
    (ARTIFACTS_DIR / "FINAL_test_report.json").write_text(json.dumps(report, indent=2))
    print("\nWrote ml/artifacts/FINAL_test_report.json")


if __name__ == "__main__":
    main()
