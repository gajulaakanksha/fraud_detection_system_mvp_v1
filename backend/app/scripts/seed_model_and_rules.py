"""Seed model_versions, rules, and decision_thresholds from the locked
Phase 1 champion (ml/artifacts/champion.json + model_package_*.pkl).

Deliberately re-runnable: clears and re-inserts each table so re-running
after retraining picks up new thresholds/model version cleanly.

Usage (from backend/):
    python -m app.scripts.seed_model_and_rules
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.db.session import SessionLocal
from app.models.decision_threshold import DecisionThreshold
from app.models.model_version import ModelVersion
from app.models.rule import Rule

ML_ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "ml" / "artifacts"

# Where model_loader.py should load the packaged model from at runtime.
# Both unset (the default) -> the local file this script is looking at right now.
# Both set -> s3://{bucket}/{key}. The bucket rarely changes and is set once
# per deployment; the key is the explicit-version lever -- MODEL_S3_KEY must
# name a specific pinned artifact (e.g. "model-artifacts/xgboost_v1.2.0.pkl"),
# never a mutable "latest.pkl" that gets overwritten in place. That's what
# keeps "which model made this decision" (model_versions.version_tag ->
# artifact_uri) an answerable, audit-trail question after the fact.
MODEL_S3_BUCKET = os.environ.get("MODEL_S3_BUCKET")
MODEL_S3_KEY = os.environ.get("MODEL_S3_KEY")
if bool(MODEL_S3_BUCKET) != bool(MODEL_S3_KEY):
    raise SystemExit("Set both MODEL_S3_BUCKET and MODEL_S3_KEY, or neither -- not just one.")
MODEL_ARTIFACT_URI_OVERRIDE = f"s3://{MODEL_S3_BUCKET}/{MODEL_S3_KEY}" if MODEL_S3_BUCKET else None

# Rule set from the blueprint's Phase 1 plan (Section 3.5 / Phase 1 bullet).
# None are marked "critical" by default -- this dataset has no sanctioned-
# country/OFAC list to hard-override on. The mechanism exists in
# band_resolver.py for whenever that data source is wired in; "high"
# severity rules can still bump a MONITOR verdict up to STEP_UP_AUTH.
RULES = [
    {
        "rule_code": "CROSS_BORDER_TRANSACTION",
        "description": "Merchant's country differs from the customer's home country.",
        "severity": "medium",
        "config": {},
    },
    {
        "rule_code": "IP_COUNTRY_MISMATCH",
        "description": "Customer's IP country differs from their home country.",
        "severity": "medium",
        "config": {},
    },
    {
        "rule_code": "TRANSACTION_COUNTRY_MISMATCH",
        "description": "Customer's IP country differs from the merchant/transaction country.",
        "severity": "high",
        "config": {},
    },
    {
        "rule_code": "NEW_DEVICE",
        "description": "This device has not been seen with this customer before.",
        "severity": "medium",
        "config": {},
    },
    {
        "rule_code": "HIGH_RISK_CUSTOMER",
        "description": "Customer's persisted risk score is at or above threshold.",
        "severity": "high",
        "config": {"risk_score_threshold": 70},
    },
    {
        "rule_code": "AMOUNT_ABOVE_2X_BASELINE",
        "description": "Transaction amount is at or above 2x this customer's average.",
        "severity": "medium",
        "config": {"multiplier": 2.0},
    },
]


def main() -> None:
    champion = json.loads((ML_ARTIFACTS_DIR / "champion.json").read_text())
    policy = champion["policy"]
    model_name = champion["champion_model"]
    final_report = json.loads((ML_ARTIFACTS_DIR / "FINAL_test_report.json").read_text())

    db = SessionLocal()
    try:
        # decision_thresholds has no dependents -- safe to wipe and recreate.
        db.query(DecisionThreshold).delete()
        # rules does have a dependent (rule_hits, on past scored decisions --
        # deliberately no cascade delete, since that's the audit trail per
        # NFR3). Upsert by rule_code instead of delete+recreate so existing
        # rule ids -- and the history that references them -- survive.
        existing_rules = {r.rule_code: r for r in db.query(Rule).all()}
        for r in RULES:
            row = existing_rules.get(r["rule_code"])
            if row is None:
                db.add(Rule(**r))
            else:
                row.description = r["description"]
                row.severity = r["severity"]
                row.config = r["config"]
                row.is_active = True
        db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).update({"is_active": False})

        # Derived from the pinned S3 key when one's given, so two different
        # artifacts (e.g. a rollback to an older xgboost_v1.1.0.pkl) never
        # collide under the same version_tag and silently keep the old
        # artifact_uri on re-seed -- see the upsert-by-version_tag logic
        # below, and the module docstring on MODEL_S3_KEY.
        version_tag = f"{model_name}-{Path(MODEL_S3_KEY).stem}" if MODEL_S3_KEY else f"{model_name}-v1.0-2026-08"
        artifact_uri = MODEL_ARTIFACT_URI_OVERRIDE or str(
            (ML_ARTIFACTS_DIR / f"model_package_{model_name}.pkl").resolve()
        )
        existing = db.query(ModelVersion).filter(ModelVersion.version_tag == version_tag).one_or_none()
        if existing is None:
            mv = ModelVersion(
                version_tag=version_tag,
                artifact_uri=artifact_uri,
                pr_auc=round(final_report["test_metrics"]["pr_auc"], 4),
                is_active=True,
            )
            db.add(mv)
        else:
            existing.is_active = True
            existing.artifact_uri = artifact_uri
            existing.pr_auc = round(final_report["test_metrics"]["pr_auc"], 4)

        # policy_version tags this exact set of 4 band rows so a Decision can
        # record which generation of thresholds produced its band, independent
        # of model_version_id -- thresholds can be retuned (FR5) without a
        # retrain, and each retune gets a new tag here.
        policy_version = f"policy-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"

        # Score bands stored 0-100 (schema's risk_score is 0-100); policy
        # thresholds from the ML pipeline are the model's raw 0-1 output
        # (a risk score, not a calibrated probability -- see
        # decision_engine/explainability.py).
        step_up_t = policy["step_up_auth"]["threshold"] * 100
        manual_t = policy["manual_review"]["threshold"] * 100
        decline_t = policy["decline"]["threshold"] * 100
        bands = [
            ("monitor", 0.0, step_up_t, "No action; log for the Overview dashboard."),
            ("step_up_auth", step_up_t, manual_t, "Route to step-up authentication (OTP/2FA) before completing."),
            ("manual_review", manual_t, decline_t, "Route to analyst queue for manual review before completing."),
            ("decline", decline_t, 100.0, "Decline the transaction."),
        ]
        for band, lo, hi, action in bands:
            db.add(DecisionThreshold(
                band=band, min_score=round(lo, 2), max_score=round(hi, 2),
                recommended_action=action, policy_version=policy_version,
            ))

        db.commit()
        print(f"Seeded model_versions (active: {version_tag}), {len(RULES)} rules, "
              f"{len(bands)} decision thresholds (policy_version={policy_version}).")
        for band, lo, hi, _ in bands:
            print(f"  {band:<14s} [{lo:6.2f}, {hi:6.2f})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
