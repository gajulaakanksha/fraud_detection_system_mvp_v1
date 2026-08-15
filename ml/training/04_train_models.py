"""Stage 04 -- Train Logistic Regression, Random Forest, XGBoost, LightGBM.

Same preprocessed features, same train split, for all four -- the only fair
way to compare them. Test-set scores are computed here (pure inference, no
decisions made from them) and stashed for stage 08; nothing before stage 08
is allowed to read test_scores.parquet.

Usage (from ml/training/, after 03_prepare_data.py):
    python 04_train_models.py
"""
import json
import time

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from common import ALL_FEATURES, ARTIFACTS_DIR, DATA_DIR, TARGET, pr_auc


def build_preprocessor() -> ColumnTransformer:
    from common import BINARY_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("bin", "passthrough", BINARY_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ]
    )


def main() -> None:
    meta = json.loads((DATA_DIR / "meta.json").read_text())

    train_df = pd.read_parquet(DATA_DIR / "train.parquet")
    val_df = pd.read_parquet(DATA_DIR / "val.parquet")
    test_df = pd.read_parquet(DATA_DIR / "test.parquet")
    print(f"Train {len(train_df):,} / Val {len(val_df):,} / Test {len(test_df):,} (test not evaluated until stage 08)")

    preprocessor = build_preprocessor()
    print("Fitting preprocessor on train ...")
    X_train = preprocessor.fit_transform(train_df[ALL_FEATURES])
    X_val = preprocessor.transform(val_df[ALL_FEATURES])
    X_test = preprocessor.transform(test_df[ALL_FEATURES])
    y_train = train_df[TARGET].to_numpy()
    y_val = val_df[TARGET].to_numpy()

    joblib.dump(preprocessor, ARTIFACTS_DIR / "preprocessor.pkl")
    (ARTIFACTS_DIR / "feature_names.json").write_text(
        json.dumps(list(preprocessor.get_feature_names_out()), indent=2)
    )

    neg, pos = np.bincount(y_train)
    scale_pos_weight = neg / pos
    print(f"Train class balance: {pos:,} fraud / {neg:,} legit (scale_pos_weight={scale_pos_weight:.2f})")

    models = {
        "logistic_regression": LogisticRegression(
            class_weight="balanced", max_iter=2000, solver="lbfgs", random_state=42,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=14, min_samples_leaf=5,
            class_weight="balanced_subsample", n_jobs=-1, random_state=42,
        ),
        "xgboost": XGBClassifier(
            n_estimators=400, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, tree_method="hist",
            eval_metric="aucpr", scale_pos_weight=scale_pos_weight,
            random_state=42, n_jobs=-1,
        ),
        "lightgbm": LGBMClassifier(
            n_estimators=400, max_depth=6, num_leaves=63, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight, random_state=42, n_jobs=-1, verbosity=-1,
        ),
    }

    results = {}
    for name, model in models.items():
        print(f"\nTraining {name} ...")
        t0 = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - t0
        print(f"  trained in {train_time:.1f}s")

        val_scores = model.predict_proba(X_val)[:, 1]
        test_scores = model.predict_proba(X_test)[:, 1]  # computed, not analyzed
        val_pr_auc = pr_auc(y_val, val_scores)
        print(f"  val PR-AUC={val_pr_auc:.4f}  (test PR-AUC withheld until stage 08)")

        joblib.dump(model, ARTIFACTS_DIR / f"{name}.pkl")

        for split_name, split_df, scores in [("val", val_df, val_scores), ("test", test_df, test_scores)]:
            out = split_df[meta["eval_only"] + [TARGET]].copy()
            out["score"] = scores
            out.to_parquet(ARTIFACTS_DIR / f"{name}_{split_name}_scores.parquet", index=False)

        results[name] = {"train_time_seconds": train_time, "val_pr_auc": val_pr_auc}

    (ARTIFACTS_DIR / "04_train_summary.json").write_text(json.dumps(results, indent=2))
    print("\nDone. Models + scored predictions written to ml/artifacts/")


if __name__ == "__main__":
    main()
