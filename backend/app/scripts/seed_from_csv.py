"""Backfill customers / merchants / devices / customer_devices from the
existing synthetic transaction dataset (Phase 0 of the MVP blueprint).

This is what fixes the is_new_device calibration bug: once this has run,
customer_devices holds real history so the Phase 1 feature builder can
answer "has this device been used by this customer before?" honestly,
instead of every transaction defaulting to is_new_device=True.

Note: this does NOT load the transactions table itself -- historical
transactions/decisions are out of Phase 0 scope; live transactions get
written by the scoring API starting in Phase 1.

Usage (run from the backend/ directory, with DATABASE_URL pointed at a
migrated database):
    python -m app.scripts.seed_from_csv --csv ../valli_securepay_10lakh_transactions.csv
    python -m app.scripts.seed_from_csv --csv ... --truncate   # wipe target tables first
"""
import argparse
import io

import pandas as pd

from app.db.session import engine

USECOLS = [
    "customer_id", "customer_home_country", "average_transaction_amount",
    "customer_risk_score", "account_age_days", "transaction_time",
    "merchant_id", "merchant_category", "country", "merchant_risk_score",
    "device_id",
]


def load_transactions(csv_path: str) -> pd.DataFrame:
    print(f"Reading {csv_path} ...")
    df = pd.read_csv(csv_path, usecols=USECOLS, parse_dates=["transaction_time"])
    print(f"  {len(df):,} rows loaded")
    return df


def build_customers(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("customer_id").agg(
        home_country=("customer_home_country", "first"),
        average_transaction_amount=("average_transaction_amount", "first"),
        customer_risk_score=("customer_risk_score", "mean"),
        account_age_days=("account_age_days", "first"),
        min_tx_time=("transaction_time", "min"),
    ).reset_index()
    # account_age_days is a customer-level constant in the generator; anchor
    # account_created_at off the earliest transaction we observed for them.
    g["account_created_at"] = g["min_tx_time"] - pd.to_timedelta(g["account_age_days"], unit="D")
    g["customer_risk_score"] = g["customer_risk_score"].round().clip(0, 100).astype(int)
    return g[[
        "customer_id", "home_country", "account_created_at",
        "average_transaction_amount", "customer_risk_score",
    ]]


def build_merchants(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("merchant_id").agg(
        merchant_category=("merchant_category", "first"),
        home_country=("country", "first"),
        merchant_risk_score=("merchant_risk_score", "mean"),
    ).reset_index()
    g["merchant_risk_score"] = g["merchant_risk_score"].round().clip(0, 100).astype(int)
    return g[["merchant_id", "merchant_category", "home_country", "merchant_risk_score"]]


def build_devices(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("device_id").agg(
        first_seen_at=("transaction_time", "min"),
        last_seen_at=("transaction_time", "max"),
    ).reset_index()
    return g[["device_id", "first_seen_at", "last_seen_at"]]


def build_customer_devices(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["customer_id", "device_id"]).agg(
        first_seen_at=("transaction_time", "min"),
        last_seen_at=("transaction_time", "max"),
    ).reset_index()
    return g[["customer_id", "device_id", "first_seen_at", "last_seen_at"]]


def copy_df(cursor, df: pd.DataFrame, table: str, columns: list[str]) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    col_list = ", ".join(columns)
    cursor.copy_expert(f"COPY {table} ({col_list}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to valli_securepay_10lakh_transactions.csv")
    parser.add_argument("--truncate", action="store_true", help="Truncate target tables before loading")
    args = parser.parse_args()

    df = load_transactions(args.csv)

    print("Aggregating customers ...")
    customers = build_customers(df)
    print(f"  {len(customers):,} distinct customers")

    print("Aggregating merchants ...")
    merchants = build_merchants(df)
    print(f"  {len(merchants):,} distinct merchants")

    print("Aggregating devices ...")
    devices = build_devices(df)
    print(f"  {len(devices):,} distinct devices")

    print("Aggregating customer_devices ...")
    customer_devices = build_customer_devices(df)
    print(f"  {len(customer_devices):,} distinct customer-device pairs")

    del df  # free the raw frame before touching the DB connection

    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        if args.truncate:
            print("Truncating customer_devices, devices, merchants, customers ...")
            cur.execute("TRUNCATE customer_devices, devices, merchants, customers CASCADE")

        print("Loading customers ...")
        copy_df(cur, customers, "customers", [
            "customer_id", "home_country", "account_created_at",
            "average_transaction_amount", "customer_risk_score",
        ])

        print("Loading merchants ...")
        copy_df(cur, merchants, "merchants", [
            "merchant_id", "merchant_category", "home_country", "merchant_risk_score",
        ])

        print("Loading devices ...")
        copy_df(cur, devices, "devices", ["device_id", "first_seen_at", "last_seen_at"])

        print("Loading customer_devices ...")
        copy_df(cur, customer_devices, "customer_devices", [
            "customer_id", "device_id", "first_seen_at", "last_seen_at",
        ])

        raw_conn.commit()
        print("Done.")
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


if __name__ == "__main__":
    main()
