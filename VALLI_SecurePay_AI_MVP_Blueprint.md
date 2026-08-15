# VALLI SecurePay AI — Fraud Detection MVP
### Product Requirements, Architecture, Data & API Design, and Implementation Plan

**Author:** Architecture review for Meenakshi Sundaram Lakshmanan, Founder & CEO, VALLI AI Pte. Ltd.
**Scope:** MVP hardening of the existing SecurePay AI console (Overview / Transaction Analyser / Report) and the underlying XGBoost + SHAP decision engine, backed by the `valli_securepay_10lakh_transactions` synthetic dataset.
**Status:** Draft v1.0

---

## 1. Product Requirements Document (PRD)

### 1.1 Problem statement
BFSI clients need a transaction-level fraud/AML risk decision returned in real time (single transaction) or in bulk (batch/CSV), with a **defensible, explainable** risk score an analyst can act on — not just a black-box number. The current build (screens reviewed) already proves the UX shape: score a transaction, see a gauge + plain-English reasons + a recommended action, browse a report of past decisions, and see fleet-level KPIs. The MVP's job is to turn this working prototype into a system with a real backend, persistent data model, calibrated model, and an auditable decision trail — the things a bank's risk/compliance team will actually diligence.

### 1.2 Goals (MVP)
1. Real-time single-transaction scoring: submit → decision in **P50 < 100ms, P95 < 300ms** end-to-end (model inference already benchmarks at P50 3.1ms; the rest is API/DB overhead budget).
2. Batch scoring via CSV upload (10 lakh+ row scale, matching the existing generator's shape) with async job status and downloadable results.
3. Every decision is **explainable**: top contributing factors (SHAP-derived) rendered as plain-English reasons + a technical detail drawer, exactly as shown in the current UI.
4. A **Report** view: searchable, filterable (decision, risk band), paginated history of every scored transaction, with CSV export.
5. An **Overview** dashboard: volume, decision distribution, average risk score trend, top-triggered rules — fed by real aggregation queries, not session-only state.
6. A **rules layer** sitting alongside the ML model (hybrid decisioning), because pure-ML decisions are hard to defend to a bank's compliance team and rules give instant, auditable overrides (e.g., sanctions-list hit → always Decline).
7. Full audit trail: every score, every rule fired, every model version used, immutably logged — required for BFSI/MAS-style audits.
8. Fix the **known calibration issue already flagged in the product itself**: `is_new_device` currently flags ~100% of traffic because there's no persisted device history to bootstrap from. MVP must ship a device-fingerprint store so this stops being a permanent disclaimer banner.

### 1.3 Non-goals (explicitly out of scope for MVP)
- Multi-tenant client isolation / per-bank white-labeling (single-tenant analyst console for MVP).
- Real card-network integration (ISO 8583 / 3-D Secure step-up execution) — MVP only *recommends* step-up auth, it doesn't execute it.
- Model retraining pipeline / MLOps CI for continuous learning (MVP ships one versioned, evaluated model; retraining is Phase 2).
- Case management workflow (assigning reviews to analysts, SLA timers) — Report view is read/export only in MVP.
- Real KYC/sanctions data providers — customer/merchant risk scores remain the synthetic/derived fields already in the dataset for MVP; provider integration is a stated Phase 2 dependency.

### 1.4 Users / personas
| Persona | Need |
|---|---|
| Fraud Analyst (`analyst@bank.com` in the demo login) | Score a transaction ad hoc, review the Report queue, understand *why* something was flagged |
| Risk/Compliance Lead | Wants Overview KPIs, decision-band distribution, exportable audit trail |
| Integrating Bank's Engineering Team | Wants a stable, versioned REST API and a batch endpoint they can call from their own pipeline |
| VALLI AI (internal) | Wants model version control, rule config, and calibration health visibility (the yellow banner is this persona's voice today) |

### 1.5 Success metrics for MVP sign-off
- PR-AUC ≥ 0.80 on held-out synthetic test split (current lab result: 0.821 — MVP must not regress this).
- False-positive rate on `is_new_device` reduced from 100%/28% shadow-mode down to a realistic single-digit % once device history persists across ≥ 2 weeks of traffic.
- 100% of scored transactions have a persisted, replayable decision record (score, reasons, rule hits, model version).
- Batch job of 1,000,000 rows completes and is downloadable within an agreed SLA (target: < 30 min for MVP, async).
- Zero unauthenticated access to scoring or report endpoints (today's login is a stub — "any email/password signs you in").

---

## 2. Requirements

### 2.1 Functional requirements
- **FR1** — Score a single transaction submitted via form (matches current "Single transaction" tab fields: identifiers, transaction facts, behavioural/risk context).
- **FR2** — Score a batch of transactions via CSV upload matching the documented template columns; return a job ID; poll for status; download scored CSV on completion.
- **FR3** — Persist every request, its computed features, its model output (score + SHAP contributions), any rule hits, the final decision band, and the model/ruleset version used.
- **FR4** — Idempotency: resubmitting the same `transaction_id` must be rejected or return the original decision, not silently re-score as a new event (this reverses today's explicit disclaimer).
- **FR5** — Decision bands are configurable thresholds (Monitor / Step-up auth / Manual review / Decline) stored as data, not hardcoded, so risk/compliance can retune without a deploy.
- **FR6** — Report view supports filter by decision, risk level, and free-text search across transaction/customer/merchant ID, with pagination and CSV export.
- **FR7** — Overview dashboard computes real aggregates: transactions analyzed, decline/hold rate, avg risk score, avg processing time, decision distribution, 14-day avg-risk trend, top-6 triggered rules by hit count.
- **FR8** — Explainability: every score returns (a) a human-readable summary reason, (b) 2–4 bullet contributing factors, (c) a technical detail panel (raw SHAP values / feature contributions) for analysts who want it.
- **FR9** — Authentication: replace the stub login with real session/JWT auth; all scoring and report endpoints require a valid analyst session.
- **FR10** — Device & customer history store: every `device_id` and `customer_id` seen is persisted so `is_new_device` / velocity / dormancy features are computed from real history, not per-request guesses.

### 2.2 Non-functional requirements
- **NFR1 Performance** — single-transaction P50 < 100ms / P95 < 300ms; batch throughput ≥ 2,000 rows/sec for scoring (model alone benchmarks at ~322 tx/sec single-threaded at 3.1ms/tx — batch path must parallelize/batch-infer, not loop row-by-row).
- **NFR2 Scalability** — schema and pipeline must hold the 10-lakh-row dataset shape (300K customers, 50K merchants, 8 countries) comfortably, with clear headroom to 10M+ rows without a redesign.
- **NFR3 Auditability** — every decision immutable and replayable (model version, ruleset version, input snapshot, output, timestamp, actor).
- **NFR4 Explainability** — no decision may be returned without at least one contributing-factor reason; "black box score with no reasons" is a shipped-bug, not an acceptable state.
- **NFR5 Security** — PII fields (none of the current synthetic set are direct PII, but customer/device/merchant IDs plus behavioural data are sensitive) encrypted at rest; TLS in transit; role-based access (analyst vs admin).
- **NFR6 Availability** — scoring API target 99.5% for MVP (single-region acceptable; multi-region is Phase 2).
- **NFR7 Data integrity** — batch upload validated against the CSV template schema before any scoring begins; malformed rows quarantined and reported, not silently dropped.

---

## 3. Architecture Design

### 3.1 Component overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND (React SPA)                               │
│   Overview · Transaction Analyser (single + batch CSV) · Report                   │
└───────────────────────────────────┬────────────────────────────────────────────┬─┘
                                     │ HTTPS / JSON                                │
                                     ▼                                              │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (FastAPI)                                │
│   Auth (JWT) · Rate limiting · Request validation · Routing                       │
└───────┬───────────────┬───────────────┬───────────────┬─────────────────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────────────────┐
│ Scoring Service│ │ Batch Service │ │ Report Service│ │ Metrics/Overview Service │
│ (sync, single) │ │ (async, queue)│ │ (query+export)│ │ (aggregation queries)    │
└───────┬────────┘ └───────┬───────┘ └───────┬───────┘ └───────────┬─────────────┘
        │                  │                 │                     │
        ▼                  ▼                 │                     │
┌─────────────────────────────────────┐      │                     │
│         DECISION ENGINE              │      │                     │
│  1. Feature Builder (reads history)  │      │                     │
│  2. ML Model (XGBoost, versioned)    │      │                     │
│  3. Explainability (SHAP)            │      │                     │
│  4. Rules Engine (deterministic)     │      │                     │
│  5. Band Resolver (config thresholds)│      │                     │
└──────────────┬────────────────────────      │                     │
               │                              │                     │
               ▼                              ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER (PostgreSQL, primary OLTP)                     │
│  customers · merchants · devices · transactions · decisions ·                     │
│  rule_hits · rules · model_versions · audit_log                                   │
└───────┬───────────────────────────────────────────────────────────┬─────────────┘
        │                                                             │
        ▼                                                             ▼
┌────────────────────────┐                             ┌─────────────────────────────┐
│  Feature/History Cache  │                             │  Object storage (batch files) │
│  (Redis: velocity, last │                             │  raw uploads · scored results │
│  N tx per customer/dev) │                             │  model artifacts (.pkl)       │
└────────────────────────┘                             └─────────────────────────────┘

                     ┌──────────────────────────────────────┐
                     │        Background Worker (Celery/RQ)   │
                     │  batch scoring jobs · nightly Overview  │
                     │  aggregate rollups · SHAP precompute    │
                     └──────────────────────────────────────┘
```

### 3.2 Component responsibilities

| Component | Responsibility | MVP tech choice |
|---|---|---|
| Frontend | Renders the three existing screens against real APIs instead of session state | React + existing component set (gauge, decision-band table, KPI cards) |
| API Gateway | AuthN/Z, validation, routing, rate limiting | FastAPI (matches VALLI's existing decision-engine stack) |
| Scoring Service | Synchronous single-transaction path | FastAPI route → Decision Engine, in-process for latency |
| Batch Service | Accepts CSV, validates schema, enqueues job, streams progress | FastAPI upload endpoint + Celery/RQ worker |
| Feature Builder | Turns a raw transaction + historical context into the model's feature vector (device age, velocity, dormancy, risk scores) | Python module, reads Postgres + Redis hot cache |
| ML Model | XGBoost classifier producing fraud probability | Existing trained artifact, versioned in object storage, loaded once per process |
| Explainability | SHAP value computation per prediction | `shap.TreeExplainer` (fast for tree models — keeps P50 latency low) |
| Rules Engine | Deterministic overrides (velocity spike, sanctioned country, crypto+new-beneficiary combo, etc.) evaluated alongside the model | Config-driven rule table, evaluated in the same request path |
| Band Resolver | Combines model score + rule hits → final decision band using configurable thresholds | Reads `decision_thresholds` config table |
| Data Layer | System of record for every entity + every decision | PostgreSQL (relational integrity for customers/merchants/devices/transactions matters here) |
| Feature/History Cache | Sub-ms lookups for velocity counters (`transactions_last_10_minutes`) and "have we seen this device/customer before" | Redis |
| Background Worker | Batch scoring at scale, nightly Overview rollups so dashboard queries stay fast | Celery/RQ + Postgres/Redis broker |
| Object storage | Uploaded CSVs, scored result CSVs, model binaries | S3-compatible bucket (or local disk for MVP demo) |

### 3.3 Single-transaction request flow
1. Frontend submits the form (identifiers, transaction facts, behavioural/risk context) → `POST /v1/transactions/score`.
2. API validates payload shape and auth.
3. Feature Builder resolves `customer_id`/`device_id` against history: is this device known for this customer? What's the velocity in the last 10 minutes? Days since last transaction? — all read from Postgres/Redis, **not** re-derived from the request body alone (this is the fix for the `is_new_device` calibration bug).
4. Decision Engine runs: ML model score → SHAP top factors → Rules Engine evaluation → Band Resolver picks Monitor/Step-up/Manual review/Decline.
5. Response returned to frontend with score, band, human-readable reasons, and a technical-detail payload.
6. Decision + inputs + rule hits persisted asynchronously (fire-and-forget write, doesn't block the response) to `decisions`, `rule_hits`, `audit_log`.
7. Customer/device/merchant history tables updated (last-seen device, running velocity counters) so the *next* transaction benefits from real history.

### 3.4 Batch flow
1. CSV uploaded → schema-validated against the template columns (same columns as `valli_securepay_10lakh_transactions.csv`) before any row is touched.
2. Job row created (`status=queued`), file stored in object storage, job enqueued.
3. Worker picks up job, loads model once, **vectorized batch inference** (matching the vectorized approach already used in `gen_10lakh.py` for generation — no per-row Python loop for scoring either), writes results + persists decisions in bulk (`COPY`/bulk insert, not row-by-row `INSERT`).
4. Job status polled by frontend (`queued → running → done/failed`, with row-count progress).
5. On completion, scored CSV made available for download; summary stats (decision distribution for the batch) shown inline.

### 3.5 Why a hybrid rules + ML design (not ML-only)
A pure model score is hard for a bank's compliance team to sign off on. The MVP keeps a small, explicit rules table (e.g., `CROSS_BORDER_TRANSACTION`, `IP_COUNTRY_MISMATCH`, `HIGH_RISK_CUSTOMER`, `AMOUNT_ABOVE_2X_BASELINE`) — the same rule names already visible in the current "Most-triggered rules" widget — evaluated deterministically alongside the model. This gives (a) instant explainability independent of SHAP, (b) a safe way to hard-force a Decline regardless of model score, and (c) an audit story: "transaction X was declined because rule Y fired," not "the model said so."

---

## 4. Database Schema

Design notes:
- Normalized around the entities already implied by the dataset generator: `customers`, `merchants`, `devices`, `transactions`. This matches `CUS-######`, `MER-######`, `DEV-#######`, `TXN-########` ID formats already in use.
- `decisions` is separated from `transactions` because a transaction is submitted once but a decision (score, band, reasons) is a derived, versioned artifact of it — this separation is what makes replay/audit possible.
- `rule_hits` is a child of `decisions` (many rules can fire per decision) rather than columns on `decisions`, so new rules don't require schema migrations.
- All monetary fields use `NUMERIC`, not `FLOAT`, to avoid rounding drift in a financial system.
- `fraud_type` on historical/labeled data is kept for training/evaluation lineage but is never populated by the live scoring path (that would be leaking the label).

```sql
-- ============================================================
-- CORE REFERENCE ENTITIES
-- ============================================================

CREATE TABLE customers (
    customer_id            VARCHAR(12)  PRIMARY KEY,           -- e.g. CUS-018853
    home_country            CHAR(2)      NOT NULL,
    account_created_at      TIMESTAMPTZ  NOT NULL,
    average_transaction_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    customer_risk_score     SMALLINT     NOT NULL DEFAULT 0 CHECK (customer_risk_score BETWEEN 0 AND 100),
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE merchants (
    merchant_id             VARCHAR(12)  PRIMARY KEY,           -- e.g. MER-019379
    merchant_category       VARCHAR(32)  NOT NULL,
    home_country             CHAR(2)      NOT NULL,
    merchant_risk_score      SMALLINT     NOT NULL DEFAULT 0 CHECK (merchant_risk_score BETWEEN 0 AND 100),
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE devices (
    device_id                VARCHAR(14)  PRIMARY KEY,           -- e.g. DEV-0687287
    first_seen_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen_at               TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- device <-> customer association is many-to-many and IS the fix for the
-- "is_new_device flags 100% of traffic" calibration bug: this table is the
-- persisted history that lets us answer "has this device been used by this
-- customer before?" honestly.
CREATE TABLE customer_devices (
    customer_id   VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    device_id      VARCHAR(14) NOT NULL REFERENCES devices(device_id),
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (customer_id, device_id)
);

-- ============================================================
-- TRANSACTIONS & DECISIONS
-- ============================================================

CREATE TABLE transactions (
    transaction_id                  VARCHAR(14)  PRIMARY KEY,       -- e.g. TXN-00000001
    customer_id                      VARCHAR(12)  NOT NULL REFERENCES customers(customer_id),
    merchant_id                       VARCHAR(12)  NOT NULL REFERENCES merchants(merchant_id),
    device_id                         VARCHAR(14)  NOT NULL REFERENCES devices(device_id),
    amount                             NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    currency                           CHAR(3)      NOT NULL,
    transaction_country                CHAR(2)      NOT NULL,
    ip_country                          CHAR(2)      NOT NULL,
    channel                             VARCHAR(16)  NOT NULL,       -- mobile_app | web | pos | atm | api
    is_new_device                       BOOLEAN      NOT NULL,
    is_new_beneficiary                  BOOLEAN      NOT NULL,
    session_duration_seconds             INTEGER,
    transactions_last_10_minutes          INTEGER      NOT NULL DEFAULT 0,
    failed_attempts_last_24_hours          INTEGER      NOT NULL DEFAULT 0,
    days_since_last_transaction             INTEGER,
    transaction_time                        TIMESTAMPTZ  NOT NULL,
    ingested_at                              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    source                                    VARCHAR(16)  NOT NULL DEFAULT 'single',  -- single | batch
    batch_job_id                              UUID REFERENCES batch_jobs(id),

    -- labeling lineage for training/eval datasets only -- NEVER populated by live scoring
    fraud_label                                SMALLINT,
    fraud_type                                  VARCHAR(32)
);
CREATE INDEX idx_transactions_customer ON transactions(customer_id, transaction_time DESC);
CREATE INDEX idx_transactions_merchant ON transactions(merchant_id);
CREATE INDEX idx_transactions_device   ON transactions(device_id);
CREATE INDEX idx_transactions_time     ON transactions(transaction_time DESC);

CREATE TABLE model_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_tag    VARCHAR(32)  NOT NULL UNIQUE,     -- e.g. xgb-v2.0-2026-08
    artifact_uri    TEXT         NOT NULL,             -- object storage path to the .pkl
    pr_auc          NUMERIC(5,4),
    trained_at       TIMESTAMPTZ,
    is_active         BOOLEAN      NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE rules (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code      VARCHAR(64)  NOT NULL UNIQUE,      -- e.g. CROSS_BORDER_TRANSACTION
    description     TEXT         NOT NULL,
    severity         VARCHAR(16)  NOT NULL,             -- low | medium | high | critical
    is_active         BOOLEAN      NOT NULL DEFAULT true,
    config             JSONB        NOT NULL DEFAULT '{}', -- thresholds, e.g. {"velocity_threshold": 10}
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE decision_thresholds (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    band            VARCHAR(16)  NOT NULL UNIQUE,       -- monitor | step_up_auth | manual_review | decline
    min_score        NUMERIC(5,2) NOT NULL,               -- inclusive lower bound on 0-100 risk score
    max_score         NUMERIC(5,2) NOT NULL,
    recommended_action TEXT       NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id       VARCHAR(14)  NOT NULL REFERENCES transactions(transaction_id),
    model_version_id      UUID         NOT NULL REFERENCES model_versions(id),
    risk_score              NUMERIC(5,2) NOT NULL,          -- 0-100
    decision_band            VARCHAR(16)  NOT NULL,           -- monitor | step_up_auth | manual_review | decline
    summary_reason            TEXT         NOT NULL,           -- plain-English headline
    contributing_factors       JSONB        NOT NULL,           -- ["Amount far above baseline", ...]
    shap_values                  JSONB,                          -- raw technical-detail payload
    processing_time_ms            INTEGER      NOT NULL,
    decided_at                     TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_decisions_transaction ON decisions(transaction_id);
CREATE INDEX idx_decisions_band_time   ON decisions(decision_band, decided_at DESC);

CREATE TABLE rule_hits (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id    UUID NOT NULL REFERENCES decisions(id),
    rule_id         UUID NOT NULL REFERENCES rules(id),
    detail            JSONB
);
CREATE INDEX idx_rule_hits_decision ON rule_hits(decision_id);
CREATE INDEX idx_rule_hits_rule     ON rule_hits(rule_id);

-- ============================================================
-- BATCH JOBS
-- ============================================================

CREATE TABLE batch_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submitted_by       UUID NOT NULL REFERENCES users(id),
    original_filename    TEXT NOT NULL,
    input_uri              TEXT NOT NULL,
    output_uri               TEXT,
    row_count                  INTEGER,
    status                       VARCHAR(16) NOT NULL DEFAULT 'queued', -- queued|running|done|failed
    error_message                 TEXT,
    started_at                     TIMESTAMPTZ,
    completed_at                     TIMESTAMPTZ,
    created_at                        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- AUTH & AUDIT
-- ============================================================

CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT       NOT NULL UNIQUE,
    password_hash    TEXT         NOT NULL,
    role               VARCHAR(16)  NOT NULL DEFAULT 'analyst',  -- analyst | admin
    is_active           BOOLEAN      NOT NULL DEFAULT true,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
    id             BIGSERIAL PRIMARY KEY,
    actor_user_id    UUID REFERENCES users(id),
    action             VARCHAR(64) NOT NULL,   -- e.g. score_transaction, export_report, update_rule
    entity_type          VARCHAR(32),
    entity_id              TEXT,
    metadata                 JSONB,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_actor ON audit_log(actor_user_id, created_at DESC);

-- ============================================================
-- MATERIALIZED VIEW FOR OVERVIEW DASHBOARD (nightly + on-demand refresh)
-- ============================================================
CREATE MATERIALIZED VIEW mv_overview_daily AS
SELECT
    date_trunc('day', d.decided_at) AS day,
    count(*)                          AS transactions_analyzed,
    avg(d.risk_score)                  AS avg_risk_score,
    avg(d.processing_time_ms)            AS avg_processing_time_ms,
    count(*) FILTER (WHERE d.decision_band IN ('decline','manual_review')) * 1.0
        / NULLIF(count(*), 0)              AS decline_hold_rate,
    count(*) FILTER (WHERE d.decision_band = 'monitor')        AS monitor_count,
    count(*) FILTER (WHERE d.decision_band = 'step_up_auth')   AS step_up_count,
    count(*) FILTER (WHERE d.decision_band = 'manual_review')  AS manual_review_count,
    count(*) FILTER (WHERE d.decision_band = 'decline')        AS decline_count
FROM decisions d
GROUP BY 1;
```

### 4.1 Entity relationship summary
```
customers 1──∞ transactions ∞──1 merchants
customers ∞──∞ devices (via customer_devices)   ← fixes is_new_device calibration
transactions 1──1 decisions ∞──∞ rules (via rule_hits)
decisions ∞──1 model_versions
batch_jobs 1──∞ transactions (source='batch')
users 1──∞ audit_log
```

---

## 5. API Design

Base URL: `/v1`. Auth: `Bearer <JWT>` on every endpoint except `/auth/login`. All errors follow `{"error": {"code": "...", "message": "..."}}`.

### 5.1 Auth

**`POST /v1/auth/login`**
```json
// Request
{ "email": "analyst@bank.com", "password": "********" }
// Response 200
{ "access_token": "eyJ...", "expires_in": 3600, "user": { "id": "...", "email": "...", "role": "analyst" } }
```
Replaces today's "any email/password signs you in" demo stub with real credential verification.

### 5.2 Scoring — single transaction

**`POST /v1/transactions/score`**

Request body mirrors the existing "Single transaction" form fields:
```json
{
  "transaction_id": "txn_653281",
  "customer_id": "cust_501",
  "merchant_id": "merchant_112",
  "device_id": "device_82",
  "amount": 1250.00,
  "currency": "SGD",
  "transaction_country": "SG",
  "customer_home_country": "SG",
  "ip_country": "SG",
  "channel": "mobile_app",
  "merchant_category": "electronics",
  "transaction_time": "2026-08-07T08:45:00Z",
  "session_duration_seconds": 0,
  "device_age_days": 5,
  "account_age_days": 612,
  "average_transaction_amount": 82.36,
  "transactions_last_10_minutes": 0,
  "failed_attempts_last_24_hours": 0,
  "days_since_last_transaction": 0,
  "is_new_beneficiary": false
}
```
Note: `is_new_device`, `merchant_risk_score`, `customer_risk_score` are **not** accepted from the client in the hardened API — they are resolved server-side from persisted history/reference tables, closing the exact gap called out in the current calibration-issue banner. (MVP transition: accept them as optional overrides for demo/testing, server-computed values win by default.)

```json
// Response 200
{
  "transaction_id": "txn_653281",
  "risk_score": 51.0,
  "decision_band": "manual_review",
  "recommended_action": {
    "label": "Manual review",
    "detail": "Route to analyst queue for manual review before completing."
  },
  "summary_reason": "This transaction was flagged as HIGH risk, mainly due to an unusually large amount for this customer and an unrecognized device.",
  "contributing_factors": [
    "The amount is far above this customer's typical spending pattern.",
    "This device hasn't been seen with this customer before.",
    "The session was unusually short, on a device that hasn't been seen before."
  ],
  "rule_hits": ["AMOUNT_ABOVE_2X_BASELINE", "NEW_DEVICE"],
  "model_version": "xgb-v2.0-2026-08",
  "processing_time_ms": 12,
  "decided_at": "2026-08-07T08:45:15Z"
}
```

**`GET /v1/transactions/{transaction_id}`** — returns the persisted decision (same shape as above) for replay/audit, or `404` if never scored.

**`GET /v1/transactions/{transaction_id}/technical-detail`** — returns raw SHAP feature contributions (the "Technical detail" expandable panel).

### 5.3 Scoring — batch

**`POST /v1/transactions/batch`** (multipart file upload)
```json
// Response 202
{ "job_id": "b3f1...", "status": "queued", "row_count_detected": 43 }
```

**`GET /v1/transactions/batch/{job_id}`**
```json
{ "job_id": "b3f1...", "status": "running", "rows_processed": 12000, "row_count": 1000000 }
```

**`GET /v1/transactions/batch/{job_id}/download`** — streams the scored CSV once `status == done`.

**`GET /v1/transactions/batch/template`** — returns the CSV column template (already present in the UI as "Download CSV template").

### 5.4 Report

**`GET /v1/transactions`**
Query params: `decision` (monitor|step_up_auth|manual_review|decline), `risk_level` (low|medium|high|critical), `q` (free-text over transaction/customer/merchant ID), `from`, `to`, `page`, `page_size`.
```json
{
  "results": [
    {
      "transaction_id": "txn_653281", "time": "2026-08-07T08:45:15Z",
      "customer_id": "cust_501", "merchant_id": "merchant_112",
      "amount": 1250.00, "currency": "SGD",
      "decision_band": "manual_review", "risk_level": "high"
    }
  ],
  "page": 1, "page_size": 50, "total": 43
}
```

**`GET /v1/transactions/export`** — same filters as above, streams CSV (the "Export CSV" button).

### 5.5 Overview / metrics

**`GET /v1/overview/summary`**
```json
{
  "transactions_analyzed": 42,
  "decline_hold_rate": 0.071,
  "avg_risk_score": 42.6,
  "avg_processing_time_ms": 12.6
}
```

**`GET /v1/overview/decision-distribution`** → `{ "monitor": 24, "step_up_auth": 24, "manual_review": 12, "decline": 3 }`

**`GET /v1/overview/risk-trend?days=14`** → daily `{ "day": "2026-07-25", "avg_risk_score": 0, "transactions": 0 }` series.

**`GET /v1/overview/top-rules?limit=6`** → `[{ "rule_code": "CROSS_BORDER_TRANSACTION", "hit_count": 36 }, ...]`

### 5.6 Rules & thresholds (admin)

**`GET /v1/rules`** / **`PATCH /v1/rules/{rule_code}`** — view/toggle/reconfigure rules (`is_active`, `config` thresholds).
**`GET /v1/decision-thresholds`** / **`PATCH /v1/decision-thresholds/{band}`** — retune score→band cutoffs without a deploy (FR5).

### 5.7 System health

**`GET /v1/health`** — liveness. **`GET /v1/models/active`** — currently active model version + its PR-AUC, so the "known calibration issue" banner can eventually be driven by real, live metrics instead of being a static hardcoded notice.

---

## 6. Folder Structure

```
valli-securepay-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entrypoint
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── transactions.py     # single-transaction score, get, technical-detail
│   │   │   │   ├── batch.py            # upload, status, download, template
│   │   │   │   ├── report.py           # list, export
│   │   │   │   ├── overview.py         # summary, distribution, trend, top-rules
│   │   │   │   └── admin.py            # rules, decision-thresholds
│   │   ├── core/
│   │   │   ├── config.py               # env/settings
│   │   │   ├── security.py             # JWT, password hashing
│   │   │   └── dependencies.py         # auth guards, pagination
│   │   ├── decision_engine/
│   │   │   ├── feature_builder.py      # resolves history from DB/Redis into a feature vector
│   │   │   ├── model_loader.py         # loads versioned XGBoost artifact
│   │   │   ├── explainability.py       # SHAP wrapper, reason-string generation
│   │   │   ├── rules_engine.py         # evaluates active rules against features
│   │   │   └── band_resolver.py        # score+rules -> decision band
│   │   ├── models/                     # SQLAlchemy ORM models (1:1 with schema in Sec.4)
│   │   ├── schemas/                    # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── scoring_service.py
│   │   │   ├── batch_service.py
│   │   │   ├── report_service.py
│   │   │   └── overview_service.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── batch_scoring_task.py   # vectorized batch inference
│   │   │   └── overview_rollup_task.py # nightly mv_overview_daily refresh
│   │   └── db/
│   │       ├── session.py
│   │       └── migrations/             # Alembic
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   └── Dockerfile
│
├── ml/
│   ├── data/
│   │   ├── gen_10lakh.py               # existing synthetic generator (kept as-is)
│   │   └── valli_securepay_10lakh_transactions.csv
│   ├── training/
│   │   ├── train_xgboost.py
│   │   ├── evaluate.py                 # PR-AUC, calibration curve, latency benchmark
│   │   └── feature_spec.yaml           # single source of truth for feature names/types
│   ├── artifacts/
│   │   └── xgb-v2.0-2026-08.pkl
│   └── notebooks/
│       └── calibration_analysis.ipynb  # investigates is_new_device false-positive rate
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Overview.tsx
│   │   │   ├── TransactionAnalyser/
│   │   │   │   ├── SingleTransactionForm.tsx
│   │   │   │   └── BatchUpload.tsx
│   │   │   ├── Report.tsx
│   │   │   └── Login.tsx
│   │   ├── components/
│   │   │   ├── RiskGauge.tsx
│   │   │   ├── DecisionBadge.tsx
│   │   │   ├── ContributingFactors.tsx
│   │   │   ├── TechnicalDetailPanel.tsx
│   │   │   ├── CalibrationBanner.tsx   # now driven by GET /v1/models/active
│   │   │   └── KPICard.tsx
│   │   ├── api/                        # typed API client (matches Sec.5 contracts)
│   │   ├── hooks/
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml              # postgres, redis, backend, worker, frontend
│   ├── migrations_ci.yml
│   └── terraform/ (Phase 2+)
│
└── docs/
    ├── VALLI_SecurePay_AI_MVP_Blueprint.md   # this document
    └── api-contracts.openapi.yaml
```

---

## 7. Implementation Plan

Assumes the ML model, feature engineering, and synthetic dataset are already in hand (per current lab results: PR-AUC 0.821, P50 3.1ms) — this plan is about turning the existing UI + model into a productionized MVP.

### Phase 0 — Foundations (Week 1)
- Stand up Postgres + Redis + object storage locally via `docker-compose`.
- Implement schema from Section 4 with Alembic migrations.
- Seed `customers` / `merchants` / `devices` / `customer_devices` from the existing 10-lakh dataset (backfills real history so `is_new_device` and velocity fields become truthful on day one instead of bootstrapping from zero).
- Replace the login stub with real auth (`users` table, JWT).

**Exit criteria:** DB stands up clean, seeded, and login is real.

### Phase 1 — Core scoring API (Weeks 2–3)
- Wrap the existing trained XGBoost model + SHAP explainer behind `POST /v1/transactions/score`.
- Implement `feature_builder.py` reading from Postgres/Redis instead of trusting client-submitted `is_new_device`/risk scores.
- Implement `rules_engine.py` with the rule set already visible in the product (`CROSS_BORDER_TRANSACTION`, `IP_COUNTRY_MISMATCH`, `NEW_DEVICE`, `HIGH_RISK_CUSTOMER`, `AMOUNT_ABOVE_2X_BASELINE`, `TRANSACTION_COUNTRY_MISMATCH`) and `band_resolver.py` reading configurable thresholds.
- Persist every decision + rule hits + audit log entry.
- Wire the existing "Single transaction" form in the frontend to the real endpoint, replacing session-only state.
- Enforce idempotency on `transaction_id` (fixes the current disclaimer).

**Exit criteria:** a submitted transaction gets a real, persisted, explainable, replayable decision at target latency.

### Phase 2 — Batch pipeline (Weeks 3–4)
- CSV schema validation against the template.
- Celery/RQ worker + vectorized batch inference (numpy/pandas batch predict, not a row loop — mirrors the vectorization already used in `gen_10lakh.py`).
- Job status polling + result download endpoints.
- Wire the existing "Batch upload (CSV)" tab to the real job lifecycle (queued/running/done + progress).
- Load-test against the full 10-lakh-row file to validate the throughput NFR.

**Exit criteria:** the 1,000,000-row dataset can be uploaded, scored, and downloaded within SLA.

### Phase 3 — Report & Overview (Weeks 4–5)
- `GET /v1/transactions` with filter/search/pagination; wire to the existing Report table + detail panel.
- CSV export endpoint; wire the existing "Export CSV" button.
- `mv_overview_daily` materialized view + nightly refresh job; wire Overview KPI cards, decision-distribution chart, risk-trend chart, top-rules chart to real aggregates instead of session-only counts.

**Exit criteria:** Overview and Report reflect real historical data, not just the current session's 42 transactions.

### Phase 4 — Calibration close-out & hardening (Week 6)
- Recompute the shadow-mode false-positive rate for `is_new_device` now that `customer_devices` history is real; confirm it drops materially from the current 28%.
- Turn the static "Known calibration issue" banner into a dynamic one driven by `GET /v1/models/active` (only shows when live metrics actually degrade).
- Security pass: rate limiting, input validation, encrypted-at-rest sensitive fields, role-based access for the `/admin` rule/threshold endpoints.
- Load/perf test single-transaction path against NFR1; tune Redis caching for velocity counters if P95 is at risk.

**Exit criteria:** MVP success metrics from Section 1.5 are met and demonstrable end-to-end.

### Phase 5 — MVP demo readiness (Week 6–7)
- End-to-end smoke tests (single + batch + report + overview) against a fresh environment.
- Runbook + API contract doc (`docs/api-contracts.openapi.yaml`) for the integrating bank's engineering team.
- Sign-off checklist against Section 1.5 metrics, presented to risk/compliance persona.

### Suggested team shape
- 1 backend engineer (FastAPI, decision engine wiring)
- 1 ML engineer (model/SHAP packaging, batch vectorization, calibration analysis)
- 1 frontend engineer (wire existing screens to real API contracts)
- 1 (part-time) DevOps for Docker/CI and load testing
- Founder/architect review at each phase gate

### Key risks & mitigations
| Risk | Mitigation |
|---|---|
| Batch inference too slow at 10-lakh scale if done row-by-row | Mandate vectorized/batched model inference from day one (Phase 2) |
| `is_new_device` calibration doesn't actually improve after adding history store | Backfill real device history from the existing dataset before go-live (Phase 0), not after |
| Compliance rejects a pure-ML decision with no deterministic rationale | Hybrid rules + ML design is architectural, not optional (Section 3.5) |
| Report/Overview queries slow down as transaction volume grows | Materialized view + nightly rollup instead of live aggregation on raw `decisions` table |
| Demo-stub auth ships accidentally to a client environment | Auth hardening is a Phase 0 gate, not a late-stage add-on |
