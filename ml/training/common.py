"""Shared feature spec, data loading, and metric functions used by every
numbered stage script (01_... through 08_...). Keeping this in one place is
what makes the four-model comparison apples-to-apples: every stage computes
metrics the same way regardless of which model produced the scores.
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve

DATA_DIR = Path("../data/processed")
ARTIFACTS_DIR = Path("../artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAMES = ["logistic_regression", "random_forest", "xgboost", "lightgbm"]

NUMERIC_FEATURES = [
    "amount", "amount_to_avg_ratio", "device_age_days", "account_age_days",
    "transactions_last_10_minutes", "failed_attempts_last_24_hours",
    "days_since_last_transaction", "session_duration_seconds",
    "merchant_risk_score", "customer_risk_score",
]
BINARY_FEATURES = [
    "is_new_device", "is_new_beneficiary", "is_cross_border",
    "is_ip_merchant_country_mismatch",
]
CATEGORICAL_FEATURES = [
    "channel", "merchant_category", "customer_home_country",
    "transaction_country", "ip_country",
]
ALL_FEATURES = NUMERIC_FEATURES + BINARY_FEATURES + CATEGORICAL_FEATURES
EVAL_ONLY = ["fraud_type", "amount", "transaction_time", "transaction_id"]
TARGET = "fraud_label"

RAW_COLUMNS = [
    "transaction_id", "customer_id", "amount", "currency", "transaction_time",
    "merchant_id", "merchant_category", "country", "customer_home_country",
    "device_age_days", "account_age_days", "transactions_last_10_minutes",
    "failed_attempts_last_24_hours", "average_transaction_amount", "is_new_device",
    "is_new_beneficiary", "ip_country", "merchant_risk_score", "customer_risk_score",
    "channel", "session_duration_seconds", "days_since_last_transaction",
    "fraud_label", "fraud_type",
]

# Business cost assumptions -- placeholders pending real Risk/Compliance
# input, used consistently across leakage/eval/policy/business-value stages.
ACTION_FP_COST = {"step_up_auth": 2.0, "manual_review": 15.0, "decline": 50.0}
# Assumed fraud-prevention efficacy per action -- a block stops ~all fraud in
# it, manual review catches most but not all, step-up deters some fraudsters
# but plenty complete OTP/2FA anyway, monitor stops nothing.
ACTION_PREVENTION_EFFICACY = {"decline": 1.00, "manual_review": 0.90, "step_up_auth": 0.40, "monitor": 0.0}
ANALYST_REVIEWS_PER_DAY_CAPACITY = 1000       # 5 analysts x 200 reviews/day, placeholder
MAX_ALERT_VOLUME_SHARE = 0.10                 # step_up+manual_review+decline <= 10% of daily volume, placeholder


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"country": "transaction_country"})
    df["amount_to_avg_ratio"] = df["amount"] / df["average_transaction_amount"].clip(lower=1.0)
    df["is_cross_border"] = (df["ip_country"] != df["customer_home_country"]).astype(int)
    df["is_ip_merchant_country_mismatch"] = (df["ip_country"] != df["transaction_country"]).astype(int)
    df["is_new_device"] = df["is_new_device"].astype(int)
    df["is_new_beneficiary"] = df["is_new_beneficiary"].astype(int)
    for col in ["device_age_days", "days_since_last_transaction", "session_duration_seconds"]:
        df[col] = df[col].fillna(df[col].median())
    return df


def load_split(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / f"{name}.parquet")


def load_scores(model_name: str, split: str) -> pd.DataFrame:
    return pd.read_parquet(ARTIFACTS_DIR / f"{model_name}_{split}_scores.parquet")


# ------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------

def pr_auc(y_true, scores) -> float:
    return float(average_precision_score(y_true, scores))


def roc_auc(y_true, scores) -> float:
    return float(roc_auc_score(y_true, scores))


def recall_at_fpr(y_true, scores, target_fpr: float) -> dict:
    fpr, tpr, thresholds = roc_curve(y_true, scores)
    idx = np.searchsorted(fpr, target_fpr, side="right") - 1
    idx = max(idx, 0)
    return {"target_fpr": target_fpr, "actual_fpr": float(fpr[idx]), "recall": float(tpr[idx]),
            "threshold": float(thresholds[idx])}


def precision_at_threshold(y_true, scores, threshold: float) -> dict:
    y_true = np.asarray(y_true)
    flagged = scores >= threshold
    tp = (flagged & (y_true == 1)).sum()
    fp = (flagged & (y_true == 0)).sum()
    fn = ((~flagged) & (y_true == 1)).sum()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (y_true == 0).sum() if (y_true == 0).sum() else 0.0
    return {"threshold": float(threshold), "precision": float(precision), "recall": float(recall),
            "fpr": float(fpr), "flagged_count": int(flagged.sum())}


def precision_at_k(y_true, scores, k: int) -> dict:
    order = np.argsort(-scores)[:k]
    y_top = np.asarray(y_true)[order]
    precision = y_top.mean() if len(y_top) else 0.0
    return {"k": k, "precision": float(precision), "fraud_caught_in_top_k": int(y_top.sum())}


def dollar_capture(y_true, scores, amount, threshold: float) -> dict:
    y_true = np.asarray(y_true)
    amount = np.asarray(amount)
    flagged = scores >= threshold
    total_fraud_value = amount[y_true == 1].sum()
    caught_fraud_value = amount[flagged & (y_true == 1)].sum()
    missed_fraud_value = amount[(~flagged) & (y_true == 1)].sum()
    fp_dollar_burden = amount[flagged & (y_true == 0)].sum()
    return {
        "threshold": float(threshold),
        "total_fraud_value": float(total_fraud_value),
        "value_captured": float(caught_fraud_value),
        "value_missed": float(missed_fraud_value),
        "dollar_recall": float(caught_fraud_value / total_fraud_value) if total_fraud_value else 0.0,
        "false_positive_dollar_burden": float(fp_dollar_burden),
    }


def calibration_report(y_true, scores, n_bins: int = 10) -> dict:
    y_true = np.asarray(y_true)
    brier = float(brier_score_loss(y_true, scores))
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.clip(np.digitize(scores, bin_edges) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = bin_idx == b
        if mask.sum() == 0:
            continue
        rows.append({
            "bin": f"{bin_edges[b]:.1f}-{bin_edges[b+1]:.1f}",
            "n": int(mask.sum()),
            "mean_predicted": float(scores[mask].mean()),
            "observed_fraud_rate": float(y_true[mask].mean()),
        })
    return {"brier_score": brier, "reliability_bins": rows}


def fraud_type_recall(y_true, scores, fraud_type, threshold: float) -> dict:
    fraud_type = np.asarray(fraud_type)
    y_true = np.asarray(y_true)
    flagged = scores >= threshold
    out = {}
    for ft in sorted(set(fraud_type[y_true == 1])):
        mask = (y_true == 1) & (fraud_type == ft)
        out[ft] = float(flagged[mask].mean()) if mask.sum() else None
    return out


def weekly_stability(df: pd.DataFrame, time_col="transaction_time", y_col="fraud_label", score_col="score") -> list:
    d = df.copy()
    d["week"] = pd.to_datetime(d[time_col]).dt.to_period("W").astype(str)
    rows = []
    for week, g in d.groupby("week"):
        if g[y_col].nunique() < 2:
            continue
        rows.append({"week": week, "n": len(g), "fraud_rate": float(g[y_col].mean()),
                      "pr_auc": pr_auc(g[y_col], g[score_col])})
    return rows


def latency_benchmark(model, preprocessor, sample_df: pd.DataFrame, n: int = 1000) -> dict:
    X = preprocessor.transform(sample_df[ALL_FEATURES].iloc[:n])
    # warm-up
    for i in range(20):
        model.predict_proba(X[i:i + 1])

    single_row_times_ms = []
    for i in range(n):
        t0 = time.perf_counter()
        model.predict_proba(X[i:i + 1])
        single_row_times_ms.append((time.perf_counter() - t0) * 1000)
    single_row_times_ms = np.array(single_row_times_ms)

    t0 = time.perf_counter()
    model.predict_proba(X)
    batch_elapsed = time.perf_counter() - t0

    return {
        "single_row_p50_ms": float(np.percentile(single_row_times_ms, 50)),
        "single_row_p95_ms": float(np.percentile(single_row_times_ms, 95)),
        "single_row_p99_ms": float(np.percentile(single_row_times_ms, 99)),
        "batch_n": n,
        "batch_elapsed_s": float(batch_elapsed),
        "batch_throughput_rows_per_sec": float(n / batch_elapsed) if batch_elapsed > 0 else None,
    }
