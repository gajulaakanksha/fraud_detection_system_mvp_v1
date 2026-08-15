"""Stage 03 -- Time-based Train / Validation / Test Split + Feature Engineering.

TIME-BASED, not random-stratified. Transactions are sorted by
transaction_time and split 70/15/15 into train/val/test. A random split lets
a model "see the future" (two transactions from the same fraud ring 10
minutes apart could land on opposite sides of a random split), which
inflates offline metrics relative to what the model actually faces in
production: it only ever scores transactions after everything it trained on.

Usage (from ml/training/, after 01 and 02 have run clean):
    python 03_prepare_data.py --csv ../../valli_securepay_10lakh_transactions.csv
"""
import argparse
import json

import pandas as pd

from common import (
    ARTIFACTS_DIR, BINARY_FEATURES, CATEGORICAL_FEATURES, DATA_DIR, EVAL_ONLY,
    NUMERIC_FEATURES, RAW_COLUMNS, TARGET, engineer_features,
)


def time_split(df: pd.DataFrame, train_frac=0.70, val_frac=0.15):
    df = df.sort_values("transaction_time").reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {args.csv} ...")
    df = pd.read_csv(args.csv, usecols=RAW_COLUMNS, parse_dates=["transaction_time"])
    print(f"  {len(df):,} rows")

    df = engineer_features(df)

    keep_cols = NUMERIC_FEATURES + BINARY_FEATURES + CATEGORICAL_FEATURES + [TARGET] + EVAL_ONLY
    keep_cols = list(dict.fromkeys(keep_cols))  # amount is in both NUMERIC_FEATURES and EVAL_ONLY
    df = df[keep_cols]

    train_df, val_df, test_df = time_split(df)

    for name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        path = DATA_DIR / f"{name}.parquet"
        split_df.to_parquet(path, index=False)
        fraud_rate = split_df[TARGET].mean()
        print(f"  {name}: {len(split_df):,} rows, fraud rate {fraud_rate:.4%}, "
              f"{split_df['transaction_time'].min()} -> {split_df['transaction_time'].max()}")

    meta = {
        "numeric_features": NUMERIC_FEATURES,
        "binary_features": BINARY_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "target": TARGET,
        "eval_only": EVAL_ONLY,
        "n_train": len(train_df),
        "n_val": len(val_df),
        "n_test": len(test_df),
        "train_fraud_rate": float(train_df[TARGET].mean()),
        "val_fraud_rate": float(val_df[TARGET].mean()),
        "test_fraud_rate": float(test_df[TARGET].mean()),
        "val_span_days": int((val_df["transaction_time"].max() - val_df["transaction_time"].min()).days) + 1,
        "test_span_days": int((test_df["transaction_time"].max() - test_df["transaction_time"].min()).days) + 1,
    }
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print("Done. Wrote train/val/test.parquet + meta.json")
    print("\nNOTE: test.parquet is not to be read again until stage 08_final_test_evaluation.py.")


if __name__ == "__main__":
    main()
