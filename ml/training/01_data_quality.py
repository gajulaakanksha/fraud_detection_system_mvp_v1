"""Stage 01 -- Data Quality / Data Understanding.

Before touching a model: is the data what we think it is? Missing values,
duplicate IDs, class balance, amount distributions by label, date coverage.
This is what catches "the generator produced a bug" before it costs a week
of modeling time.

Usage (from ml/training/):
    python 01_data_quality.py --csv ../../valli_securepay_10lakh_transactions.csv
"""
import argparse
import json

import numpy as np
import pandas as pd

from common import ARTIFACTS_DIR, RAW_COLUMNS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()

    print(f"Reading {args.csv} ...")
    df = pd.read_csv(args.csv, usecols=RAW_COLUMNS, parse_dates=["transaction_time"])
    print(f"  {len(df):,} rows, {len(df.columns)} columns")

    report = {}

    # Missing values
    missing = df.isna().sum()
    report["missing_values"] = {c: int(n) for c, n in missing[missing > 0].items()}
    print(f"Columns with missing values: {report['missing_values'] or 'none'}")

    # Duplicate IDs
    dupe_ids = int(df["transaction_id"].duplicated().sum())
    report["duplicate_transaction_ids"] = dupe_ids
    print(f"Duplicate transaction_id count: {dupe_ids}")

    # Class balance
    report["fraud_rate_overall"] = float(df["fraud_label"].mean())
    report["fraud_type_counts"] = df.loc[df["fraud_label"] == 1, "fraud_type"].value_counts().to_dict()
    print(f"Overall fraud rate: {report['fraud_rate_overall']:.4%}")
    print("Fraud type breakdown:")
    for ft, n in report["fraud_type_counts"].items():
        print(f"  {ft:<24s} {n:,}")

    # Amount distribution by label
    amt_stats = df.groupby("fraud_label")["amount"].describe()
    report["amount_stats_by_label"] = json.loads(amt_stats.to_json())
    print("\nAmount stats by label:")
    print(amt_stats)

    # Date coverage
    report["date_range"] = {
        "min": str(df["transaction_time"].min()),
        "max": str(df["transaction_time"].max()),
        "span_days": int((df["transaction_time"].max() - df["transaction_time"].min()).days),
    }
    print(f"\nDate range: {report['date_range']}")

    # Categorical cardinality sanity check (guards against a runaway
    # one-hot blow-up later if the data doesn't match what we expect)
    cat_cols = ["channel", "merchant_category", "country", "customer_home_country", "ip_country"]
    report["categorical_cardinality"] = {c: int(df[c].nunique()) for c in cat_cols}
    print(f"\nCategorical cardinality: {report['categorical_cardinality']}")

    # Negative/zero amounts, impossible values
    report["non_positive_amounts"] = int((df["amount"] <= 0).sum())
    report["negative_ages_or_counts"] = {
        "device_age_days": int((df["device_age_days"] < 0).sum()),
        "account_age_days": int((df["account_age_days"] < 0).sum()),
        "transactions_last_10_minutes": int((df["transactions_last_10_minutes"] < 0).sum()),
    }
    print(f"\nNon-positive amounts: {report['non_positive_amounts']}")
    print(f"Negative age/count sanity check: {report['negative_ages_or_counts']}")

    out_path = ARTIFACTS_DIR / "01_data_quality_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
