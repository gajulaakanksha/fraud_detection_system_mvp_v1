"""Stage 05b -- Latency / Throughput benchmark.

Split out from 05_evaluate_models.py because this one needs the raw fitted
model + preprocessor + feature rows (not just the precomputed score parquet)
to time actual predict_proba calls -- single-row (simulating the real-time
scoring path, NFR1's P50<100ms/P95<300ms budget) and batch (simulating the
Phase 2 batch-scoring path).

Usage (from ml/training/, after 04_train_models.py):
    python 05b_latency_benchmark.py
"""
import json

import joblib
import pandas as pd

from common import ARTIFACTS_DIR, DATA_DIR, MODEL_NAMES, latency_benchmark


def main() -> None:
    preprocessor = joblib.load(ARTIFACTS_DIR / "preprocessor.pkl")
    val_df = pd.read_parquet(DATA_DIR / "val.parquet")

    results = {}
    for name in MODEL_NAMES:
        model = joblib.load(ARTIFACTS_DIR / f"{name}.pkl")
        bench = latency_benchmark(model, preprocessor, val_df, n=1000)
        results[name] = bench
        print(f"{name:<22s} P50={bench['single_row_p50_ms']:.2f}ms  "
              f"P95={bench['single_row_p95_ms']:.2f}ms  "
              f"P99={bench['single_row_p99_ms']:.2f}ms  "
              f"batch throughput={bench['batch_throughput_rows_per_sec']:.0f} rows/sec")

    (ARTIFACTS_DIR / "05b_latency_report.json").write_text(json.dumps(results, indent=2))
    print("\nWrote ml/artifacts/05b_latency_report.json")


if __name__ == "__main__":
    main()
