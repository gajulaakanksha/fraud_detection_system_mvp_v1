"""Vectorized batch scoring (blueprint Section 3.4): loads the model once,
scores the whole chunk in one predict_proba/shap call each -- no per-row
Python loop for scoring, mirroring the vectorized approach already used in
gen_10lakh.py for data generation.

Reuses the exact same rule definitions, band-resolution logic, and
explanation templates as the single-transaction path (scoring_service.py /
rules_engine.py / band_resolver.py / explainability.py) so a transaction
scored via batch and one scored via /score can never silently diverge in
what counts as risky -- only *how* many rows get processed per DB round
trip differs.

Run by a separate `rq worker` process (app/workers/run_worker.py), not the
API process, so a large upload never blocks request handling.
"""
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import insert

from app.db.session import SessionLocal
from app.decision_engine import explainability, model_loader
from app.models.batch_job import BatchJob
from app.models.customer import Customer
from app.models.customer_device import CustomerDevice
from app.models.decision import Decision
from app.models.decision_threshold import DecisionThreshold
from app.models.device import Device
from app.models.merchant import Merchant
from app.models.rule import Rule
from app.models.rule_hit import RuleHit
from app.models.transaction import Transaction
from app.services import batch_service

CHUNK_SIZE = 5000
DEFAULT_RISK_SCORE = 20


def _parse_optional_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in batch_service.OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df["transaction_time"] = pd.to_datetime(df["transaction_time"], utc=True, errors="coerce")
    df["transactions_last_10_minutes"] = df["transactions_last_10_minutes"].fillna(0).astype(int)
    df["failed_attempts_last_24_hours"] = df["failed_attempts_last_24_hours"].fillna(0).astype(int)
    df["is_new_beneficiary"] = df["is_new_beneficiary"].fillna(False).astype(bool)
    return df


def _split_valid_and_quarantined(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    reasons = pd.Series([""] * len(df), index=df.index)
    bad = pd.Series(False, index=df.index)

    for col in batch_service.REQUIRED_COLUMNS:
        missing = df[col].isna()
        reasons = reasons.where(~missing, reasons + f"missing {col}; ")
        bad = bad | missing

    bad_amount = df["amount"].isna() | (pd.to_numeric(df["amount"], errors="coerce") <= 0)
    reasons = reasons.where(~bad_amount, reasons + "amount must be > 0; ")
    bad = bad | bad_amount

    bad_time = df["transaction_time"].isna()
    reasons = reasons.where(~bad_time, reasons + "invalid transaction_time; ")
    bad = bad | bad_time

    quarantined = df[bad].copy()
    quarantined["quarantine_reason"] = reasons[bad]
    valid = df[~bad].copy()
    return valid, quarantined


def _bulk_resolve_entities(db, df: pd.DataFrame) -> pd.DataFrame:
    """Mirrors feature_builder.resolve_history, but for a whole chunk at
    once: one IN-query per entity type instead of one query per row."""
    customer_ids = df["customer_id"].unique().tolist()
    existing_customers = {c.customer_id: c for c in db.query(Customer).filter(Customer.customer_id.in_(customer_ids)).all()}
    new_customer_rows = df[~df["customer_id"].isin(existing_customers)].drop_duplicates(subset="customer_id", keep="first")
    if not new_customer_rows.empty:
        db.execute(insert(Customer), [
            {
                "customer_id": r.customer_id,
                "home_country": r.customer_home_country,
                "account_created_at": r.transaction_time,
                "average_transaction_amount": r.average_transaction_amount if pd.notna(r.average_transaction_amount) else r.amount,
                "customer_risk_score": DEFAULT_RISK_SCORE,
            }
            for r in new_customer_rows.itertuples()
        ])
        db.flush()
        existing_customers.update({c.customer_id: c for c in db.query(Customer).filter(Customer.customer_id.in_(new_customer_rows["customer_id"])).all()})

    merchant_ids = df["merchant_id"].unique().tolist()
    existing_merchants = {m.merchant_id: m for m in db.query(Merchant).filter(Merchant.merchant_id.in_(merchant_ids)).all()}
    new_merchant_rows = df[~df["merchant_id"].isin(existing_merchants)].drop_duplicates(subset="merchant_id", keep="first")
    if not new_merchant_rows.empty:
        db.execute(insert(Merchant), [
            {
                "merchant_id": r.merchant_id,
                "merchant_category": r.merchant_category,
                "home_country": r.transaction_country,
                "merchant_risk_score": DEFAULT_RISK_SCORE,
            }
            for r in new_merchant_rows.itertuples()
        ])
        db.flush()
        existing_merchants.update({m.merchant_id: m for m in db.query(Merchant).filter(Merchant.merchant_id.in_(new_merchant_rows["merchant_id"])).all()})

    device_ids = df["device_id"].unique().tolist()
    existing_devices = {d.device_id: d for d in db.query(Device).filter(Device.device_id.in_(device_ids)).all()}
    new_device_ids = set(device_ids) - set(existing_devices)
    if new_device_ids:
        new_device_rows = df[df["device_id"].isin(new_device_ids)].drop_duplicates(subset="device_id", keep="first")
        db.execute(insert(Device), [
            {"device_id": r.device_id, "first_seen_at": r.transaction_time, "last_seen_at": r.transaction_time}
            for r in new_device_rows.itertuples()
        ])
        db.flush()
        existing_devices.update({d.device_id: d for d in db.query(Device).filter(Device.device_id.in_(list(new_device_ids))).all()})

    pairs = list(df[["customer_id", "device_id"]].drop_duplicates().itertuples(index=False, name=None))
    existing_pairs = set(
        (p.customer_id, p.device_id)
        for p in db.query(CustomerDevice.customer_id, CustomerDevice.device_id)
        .filter(CustomerDevice.customer_id.in_(customer_ids), CustomerDevice.device_id.in_(device_ids))
        .all()
    )

    df = df.copy()
    df["is_new_device"] = ~df.apply(lambda r: (r["customer_id"], r["device_id"]) in existing_pairs, axis=1)
    df["customer_risk_score"] = df["customer_id"].map(lambda c: existing_customers[c].customer_risk_score)
    df["merchant_risk_score"] = df["merchant_id"].map(lambda m: existing_merchants[m].merchant_risk_score)
    df["_resolved_avg_amount"] = df["customer_id"].map(lambda c: float(existing_customers[c].average_transaction_amount))

    # Resolved fallbacks for device_age_days/account_age_days when the CSV
    # omits them -- matches feature_builder.py's single-transaction behavior
    # (compute from persisted first_seen_at/account_created_at) instead of
    # silently defaulting every omitted row to "brand new" (age=0).
    def _age_days(row) -> tuple[int, int]:
        tx_time = row["transaction_time"]
        device = existing_devices.get(row["device_id"])
        customer = existing_customers.get(row["customer_id"])
        first_seen = device.first_seen_at.replace(tzinfo=timezone.utc) if device and device.first_seen_at.tzinfo is None else (device.first_seen_at if device else tx_time)
        created_at = customer.account_created_at.replace(tzinfo=timezone.utc) if customer and customer.account_created_at.tzinfo is None else (customer.account_created_at if customer else tx_time)
        return max((tx_time - first_seen).days, 0), max((tx_time - created_at).days, 0)

    resolved_ages = df.apply(_age_days, axis=1, result_type="expand")
    df["_resolved_device_age"] = resolved_ages[0]
    df["_resolved_account_age"] = resolved_ages[1]

    new_pairs = [p for p in pairs if p not in existing_pairs]
    if new_pairs:
        first_seen = df.drop_duplicates(subset=["customer_id", "device_id"], keep="first").set_index(["customer_id", "device_id"])["transaction_time"]
        db.execute(insert(CustomerDevice), [
            {"customer_id": c, "device_id": d, "first_seen_at": first_seen[(c, d)], "last_seen_at": first_seen[(c, d)]}
            for c, d in new_pairs
        ])
    if existing_pairs:
        last_seen = df.groupby(["customer_id", "device_id"])["transaction_time"].max()
        for (c, d) in existing_pairs & set(pairs):
            db.query(CustomerDevice).filter(
                CustomerDevice.customer_id == c, CustomerDevice.device_id == d,
            ).update({"last_seen_at": last_seen[(c, d)]})
    db.flush()

    return df


def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    avg = df["average_transaction_amount"].where(df["average_transaction_amount"].notna(), df["_resolved_avg_amount"])
    df["amount_to_avg_ratio"] = df["amount"] / avg.clip(lower=1.0)
    df["is_cross_border"] = (df["ip_country"] != df["customer_home_country"]).astype(int)
    df["is_ip_merchant_country_mismatch"] = (df["ip_country"] != df["transaction_country"]).astype(int)
    df["is_new_device"] = df["is_new_device"].astype(int)
    df["is_new_beneficiary"] = df["is_new_beneficiary"].astype(int)

    device_age = pd.to_numeric(df["device_age_days"], errors="coerce")
    df["device_age_days"] = device_age.where(device_age.notna(), df["_resolved_device_age"])
    account_age = pd.to_numeric(df["account_age_days"], errors="coerce")
    df["account_age_days"] = account_age.where(account_age.notna(), df["_resolved_account_age"])

    for col in ["days_since_last_transaction", "session_duration_seconds"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _vectorized_rules(df: pd.DataFrame, rules_by_code: dict) -> pd.DataFrame:
    hits = pd.DataFrame(index=df.index)
    hits["CROSS_BORDER_TRANSACTION"] = df["transaction_country"] != df["customer_home_country"]
    hits["IP_COUNTRY_MISMATCH"] = df["ip_country"] != df["customer_home_country"]
    hits["TRANSACTION_COUNTRY_MISMATCH"] = df["ip_country"] != df["transaction_country"]
    hits["NEW_DEVICE"] = df["is_new_device"].astype(bool)
    hr_threshold = (rules_by_code.get("HIGH_RISK_CUSTOMER").config or {}).get("risk_score_threshold", 70) if rules_by_code.get("HIGH_RISK_CUSTOMER") else 70
    hits["HIGH_RISK_CUSTOMER"] = df["customer_risk_score"] >= hr_threshold
    amt_multiplier = (rules_by_code.get("AMOUNT_ABOVE_2X_BASELINE").config or {}).get("multiplier", 2.0) if rules_by_code.get("AMOUNT_ABOVE_2X_BASELINE") else 2.0
    hits["AMOUNT_ABOVE_2X_BASELINE"] = df["amount_to_avg_ratio"] >= amt_multiplier

    for code in hits.columns:
        if code not in rules_by_code:
            hits[code] = False  # rule inactive/deleted -- never fires
    return hits


def _vectorized_bands(
    risk_scores: np.ndarray, thresholds: list[DecisionThreshold], rule_hits: pd.DataFrame, rules_by_code: dict,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Mirrors band_resolver.resolve_band row-by-row, but vectorized. Returns
    (band, source, override_rule_code) -- source/override_rule_code exist so
    a batch-scored decision can truthfully report a rule override later
    (via GET /v1/transactions/{id}), same as the single-transaction path."""
    order = ["monitor", "step_up_auth", "manual_review", "decline"]
    t = {row.band: row for row in thresholds}
    band = pd.Series("decline", index=rule_hits.index)
    for name in order:
        if name not in t:
            continue
        lo, hi = float(t[name].min_score), float(t[name].max_score)
        mask = (risk_scores >= lo) & (risk_scores < hi) if name != order[-1] else (risk_scores >= lo)
        band = band.where(~pd.Series(mask, index=rule_hits.index), name)

    source = pd.Series("model_score", index=rule_hits.index)
    override_rule_code = pd.Series(None, index=rule_hits.index, dtype=object)

    high_codes = [c for c, r in rules_by_code.items() if r.severity == "high" and c in rule_hits.columns]
    critical_codes = [c for c, r in rules_by_code.items() if r.severity == "critical" and c in rule_hits.columns]
    if high_codes:
        high_hit = rule_hits[high_codes].any(axis=1)
        bump_mask = (band == "monitor") & high_hit
        first_high_code = rule_hits[high_codes].idxmax(axis=1)
        override_rule_code = override_rule_code.where(~bump_mask, first_high_code)
        source = source.where(~bump_mask, "rule_override")
        band = band.where(~bump_mask, "step_up_auth")
    if critical_codes:
        critical_hit = rule_hits[critical_codes].any(axis=1)
        force_mask = critical_hit & (band != "decline")
        first_critical_code = rule_hits[critical_codes].idxmax(axis=1)
        override_rule_code = override_rule_code.where(~force_mask, first_critical_code)
        source = source.where(~force_mask, "rule_override")
        band = band.where(~force_mask, "decline")
    return band, source, override_rule_code


def _batch_explain(shap_explainer, X: np.ndarray, output_feature_names: list[str], risk_scores: np.ndarray, bands: pd.Series, top_n: int = 4):
    raw = shap_explainer.shap_values(X)
    matrix = raw[1] if isinstance(raw, list) else np.asarray(raw)

    abs_matrix = np.abs(matrix)
    top_idx = np.argsort(-abs_matrix, axis=1)[:, :top_n]

    results = []
    band_labels = {"monitor": "LOW", "step_up_auth": "ELEVATED", "manual_review": "HIGH", "decline": "CRITICAL"}
    for i in range(matrix.shape[0]):
        idxs = [j for j in top_idx[i] if abs(matrix[i, j]) > 1e-6]
        factors = [explainability._structure(output_feature_names[j], float(matrix[i, j])) for j in idxs]
        contributing_factors = [f.explanation for f in factors]
        if factors:
            headline = contributing_factors[0][0].lower() + contributing_factors[0][1:]
            summary = f"This transaction was flagged as {band_labels.get(bands.iloc[i], bands.iloc[i].upper())} risk (score {risk_scores[i]:.0f}/100), mainly because {headline}"
        else:
            summary = f"This transaction scored {band_labels.get(bands.iloc[i], bands.iloc[i].upper())} risk ({risk_scores[i]:.0f}/100), with no single dominant factor."
        results.append((summary, contributing_factors, factors, {output_feature_names[j]: float(matrix[i, j]) for j in range(matrix.shape[1])}))
    return results


def _fetch_existing_results(db, transaction_ids: list[str]) -> pd.DataFrame:
    """Mirrors scoring_service._response_from_persisted, but for a whole
    batch of already-scored transaction_ids at once -- FR4 idempotency
    applies to batch the same way it applies to /score: a transaction_id
    that's already been scored returns its original decision, it is never
    silently re-scored (and re-inserting it would violate the PK anyway)."""
    if not transaction_ids:
        return pd.DataFrame(columns=["transaction_id", "customer_id", "merchant_id", "amount", "risk_score", "decision_band", "rule_hits"])

    rows = (
        db.query(Transaction.transaction_id, Transaction.customer_id, Transaction.merchant_id, Transaction.amount,
                  Decision.risk_score, Decision.decision_band, Rule.rule_code)
        .join(Decision, Decision.transaction_id == Transaction.transaction_id)
        .outerjoin(RuleHit, RuleHit.decision_id == Decision.id)
        .outerjoin(Rule, Rule.id == RuleHit.rule_id)
        .filter(Transaction.transaction_id.in_(transaction_ids))
        .all()
    )
    by_txn: dict[str, dict] = {}
    for txn_id, cust_id, merch_id, amount, risk_score, band, rule_code in rows:
        entry = by_txn.setdefault(txn_id, {
            "transaction_id": txn_id, "customer_id": cust_id, "merchant_id": merch_id,
            "amount": float(amount), "risk_score": float(risk_score), "decision_band": band, "rule_hits": set(),
        })
        if rule_code:
            entry["rule_hits"].add(rule_code)
    for entry in by_txn.values():
        entry["rule_hits"] = "|".join(sorted(entry["rule_hits"]))
    return pd.DataFrame(list(by_txn.values()))


def run_batch_scoring(job_id_str: str) -> None:
    import dataclasses

    db = SessionLocal()
    job_id = uuid.UUID(job_id_str)
    try:
        job = db.get(BatchJob, job_id)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        loaded = model_loader.get_active_model(db)
        thresholds = db.query(DecisionThreshold).all()
        rules_by_code = {r.rule_code: r for r in db.query(Rule).filter(Rule.is_active.is_(True)).all()}
        policy_version = thresholds[0].policy_version if thresholds else "unversioned"

        df = pd.read_csv(job.input_uri)
        df = _parse_optional_cols(df)
        valid, quarantined = _split_valid_and_quarantined(df)

        # Duplicates *within this file* would violate the transactions PK the
        # same as a re-upload would -- dedupe here before ever touching the DB,
        # keeping the first occurrence and quarantining the rest with a reason.
        in_file_dupe_mask = valid.duplicated(subset="transaction_id", keep="first")
        if in_file_dupe_mask.any():
            in_file_dupes = valid[in_file_dupe_mask].copy()
            in_file_dupes["quarantine_reason"] = "duplicate transaction_id within this file"
            quarantined = pd.concat([quarantined, in_file_dupes], ignore_index=True)
            valid = valid[~in_file_dupe_mask]

        # FR4 idempotency, applied to batch: a transaction_id already scored
        # (from an earlier run or a re-upload) returns its original decision
        # instead of being re-scored -- and re-inserting it would violate the
        # transactions PK regardless, which is the crash this replaces.
        existing_ids = {
            row[0] for row in db.query(Transaction.transaction_id)
            .filter(Transaction.transaction_id.in_(valid["transaction_id"].tolist()))
            .all()
        }
        already_scored = valid[valid["transaction_id"].isin(existing_ids)]
        to_score = valid[~valid["transaction_id"].isin(existing_ids)]

        out_path = batch_service.result_path(job)
        first_chunk = True
        total_quarantined = len(quarantined)
        total_duplicates = len(already_scored)

        if total_duplicates:
            dup_results = _fetch_existing_results(db, already_scored["transaction_id"].tolist())
            dup_results.to_csv(out_path, mode="w", header=True, index=False)
            first_chunk = False

        for start in range(0, len(to_score), CHUNK_SIZE):
            chunk = to_score.iloc[start:start + CHUNK_SIZE].copy()

            chunk = _bulk_resolve_entities(db, chunk)
            chunk = _compute_features(chunk)

            X = loaded.preprocessor.transform(chunk[loaded.feature_columns])
            scores = loaded.model.predict_proba(X)[:, 1]
            risk_scores = np.round(scores * 100, 2)

            rule_hits_df = _vectorized_rules(chunk, rules_by_code)
            bands, band_sources, override_rule_codes = _vectorized_bands(risk_scores, thresholds, rule_hits_df, rules_by_code)
            explained = _batch_explain(loaded.shap_explainer, X, loaded.output_feature_names, risk_scores, bands)

            tx_rows, decision_rows, rule_hit_rows = [], [], []
            for i, r in enumerate(chunk.itertuples()):
                summary, factors_flat, factors_detail, shap_vals = explained[i]
                decision_id = uuid.uuid4()
                tx_rows.append({
                    "transaction_id": r.transaction_id, "customer_id": r.customer_id, "merchant_id": r.merchant_id,
                    "device_id": r.device_id, "amount": r.amount, "currency": r.currency,
                    "transaction_country": r.transaction_country, "ip_country": r.ip_country, "channel": r.channel,
                    "is_new_device": bool(chunk["is_new_device"].iloc[i]), "is_new_beneficiary": bool(r.is_new_beneficiary),
                    "session_duration_seconds": None if pd.isna(r.session_duration_seconds) else int(r.session_duration_seconds),
                    "transactions_last_10_minutes": int(r.transactions_last_10_minutes),
                    "failed_attempts_last_24_hours": int(r.failed_attempts_last_24_hours),
                    "days_since_last_transaction": None if pd.isna(r.days_since_last_transaction) else int(r.days_since_last_transaction),
                    "transaction_time": r.transaction_time, "source": "batch", "batch_job_id": job_id,
                })
                decision_rows.append({
                    "id": decision_id, "transaction_id": r.transaction_id, "model_version_id": loaded.model_version_id,
                    "risk_score": float(risk_scores[i]), "decision_band": bands.iloc[i],
                    "band_source": band_sources.iloc[i], "override_rule_code": override_rule_codes.iloc[i],
                    "policy_version": policy_version,
                    "summary_reason": summary, "contributing_factors": [dataclasses.asdict(f) for f in factors_detail],
                    "shap_values": shap_vals, "processing_time_ms": 0, "inference_time_ms": None, "explainability_time_ms": None,
                })
                for code, hit in rule_hits_df.iloc[i].items():
                    if hit and code in rules_by_code:
                        rule_hit_rows.append({"id": uuid.uuid4(), "decision_id": decision_id, "rule_id": rules_by_code[code].id, "detail": {}})

            db.execute(insert(Transaction), tx_rows)
            db.execute(insert(Decision), decision_rows)
            if rule_hit_rows:
                db.execute(insert(RuleHit), rule_hit_rows)
            db.commit()

            out_chunk = chunk[["transaction_id", "customer_id", "merchant_id", "amount"]].copy()
            out_chunk["risk_score"] = risk_scores
            out_chunk["decision_band"] = bands.values
            out_chunk["rule_hits"] = [
                "|".join(code for code, hit in rule_hits_df.iloc[i].items() if hit) for i in range(len(chunk))
            ]
            out_chunk.to_csv(out_path, mode="w" if first_chunk else "a", header=first_chunk, index=False)
            first_chunk = False

        if not quarantined.empty:
            quarantine_path = out_path.with_name(f"{job_id}_quarantine.csv")
            quarantined.to_csv(quarantine_path, index=False)

        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        job.output_uri = str(out_path)
        notes = []
        if total_duplicates:
            notes.append(f"{total_duplicates} row(s) were already-scored transaction_ids -- original decisions returned unchanged, not re-scored")
        if total_quarantined:
            notes.append(f"{total_quarantined} row(s) quarantined (see {job_id}_quarantine.csv)")
        if notes:
            job.error_message = f"{len(to_score)}/{len(df)} rows newly scored; " + "; ".join(notes)
        db.commit()

    except Exception as exc:
        db.rollback()
        job = db.get(BatchJob, job_id)
        job.status = "failed"
        job.error_message = str(exc)
        db.commit()
        raise
    finally:
        db.close()
