"""Stage 02 -- Leakage Analysis.

For each candidate feature, in isolation: how well does it predict fraud on
its own? A univariate AUC near 1.0 on a single feature is the classic
fingerprint of leakage (the feature encodes the label some way it shouldn't
-- e.g. a field only populated post-decision). Legitimate strong signals
(is_new_device correlating with account_takeover) will show up elevated but
well short of ~1.0; anything above LEAKAGE_AUC_THRESHOLD gets flagged for a
human look before it's allowed near a model.

Categorical features are scored by fraud-rate-encoding each category (the
category's own observed fraud rate stands in as its "prediction"), then
computing AUC against that -- same idea, applied through the natural
encoding a tree model would learn.

Usage (from ml/training/):
    python 02_leakage_analysis.py --csv ../../valli_securepay_10lakh_transactions.csv
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from common import (
    ARTIFACTS_DIR, BINARY_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES,
    RAW_COLUMNS, TARGET, engineer_features,
)

LEAKAGE_AUC_THRESHOLD = 0.97


def univariate_auc(y_true: np.ndarray, values: np.ndarray) -> float:
    auc = roc_auc_score(y_true, values)
    return max(auc, 1 - auc)  # direction-agnostic: catches inverse leakage too


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()

    print(f"Reading {args.csv} ...")
    df = pd.read_csv(args.csv, usecols=RAW_COLUMNS, parse_dates=["transaction_time"])
    df = engineer_features(df)
    y = df[TARGET].to_numpy()

    results = []
    for col in NUMERIC_FEATURES + BINARY_FEATURES:
        auc = univariate_auc(y, df[col].to_numpy())
        results.append({"feature": col, "type": "numeric/binary", "univariate_auc": auc})

    for col in CATEGORICAL_FEATURES:
        rate_map = df.groupby(col)[TARGET].transform("mean")
        auc = univariate_auc(y, rate_map.to_numpy())
        results.append({"feature": col, "type": "categorical (rate-encoded)", "univariate_auc": auc})

    results.sort(key=lambda r: -r["univariate_auc"])

    print(f"\n{'feature':<38s} {'type':<26s} {'AUC':>6s}")
    for r in results:
        flag = "  <-- FLAGGED (possible leakage)" if r["univariate_auc"] > LEAKAGE_AUC_THRESHOLD else ""
        print(f"{r['feature']:<38s} {r['type']:<26s} {r['univariate_auc']:.4f}{flag}")

    flagged = [r for r in results if r["univariate_auc"] > LEAKAGE_AUC_THRESHOLD]
    report = {
        "leakage_auc_threshold": LEAKAGE_AUC_THRESHOLD,
        "results": results,
        "flagged_features": flagged,
        "verdict": "no leakage flagged -- clear to proceed" if not flagged else "REVIEW REQUIRED before training",
    }
    out_path = ARTIFACTS_DIR / "02_leakage_analysis_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['verdict']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
