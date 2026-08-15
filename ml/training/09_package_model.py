"""Stage 09 -- Package the locked champion for serving.

Bundles the fitted preprocessor, the champion model, the exact feature
column order, and the locked decision thresholds into one artifact so the
backend's model_loader has a single file to load and can't accidentally
pair a model with the wrong preprocessor or stale thresholds.

Usage (from ml/training/, after 07_business_value_simulation.py):
    python 09_package_model.py
"""
import json

import joblib

from common import ALL_FEATURES, ARTIFACTS_DIR


def main() -> None:
    champion = json.loads((ARTIFACTS_DIR / "champion.json").read_text())
    model_name = champion["champion_model"]

    model = joblib.load(ARTIFACTS_DIR / f"{model_name}.pkl")
    preprocessor = joblib.load(ARTIFACTS_DIR / "preprocessor.pkl")
    eval_report = json.loads((ARTIFACTS_DIR / "05_evaluation_report.json").read_text())
    final_report = json.loads((ARTIFACTS_DIR / "FINAL_test_report.json").read_text())
    output_feature_names = json.loads((ARTIFACTS_DIR / "feature_names.json").read_text())

    package = {
        "model_name": model_name,
        "version_tag": f"{model_name}-v1.0-2026-08",
        "model": model,
        "preprocessor": preprocessor,
        "feature_columns": ALL_FEATURES,           # raw input columns, pre-preprocessing
        "output_feature_names": output_feature_names,  # post-preprocessing (what SHAP explains)
        "policy": champion["policy"],
        "test_pr_auc": final_report["test_metrics"]["pr_auc"],
        "val_pr_auc": eval_report[model_name]["pr_auc"],
    }

    out_path = ARTIFACTS_DIR / f"model_package_{model_name}.pkl"
    joblib.dump(package, out_path)
    print(f"Packaged {model_name} -> {out_path}")
    print(f"  version_tag: {package['version_tag']}")
    print(f"  test PR-AUC: {package['test_pr_auc']:.4f}")
    print(f"  thresholds: step_up={champion['policy']['step_up_auth']['threshold']:.4f}  "
          f"manual_review={champion['policy']['manual_review']['threshold']:.4f}  "
          f"decline={champion['policy']['decline']['threshold']:.4f}")


if __name__ == "__main__":
    main()
