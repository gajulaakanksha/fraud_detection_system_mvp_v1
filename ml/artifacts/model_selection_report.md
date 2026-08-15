# Fraud Model Selection Report — VALLI SecurePay AI, Phase 1

**Dataset:** `valli_securepay_10lakh_transactions.csv` — 1,000,000 rows, 3.07% fraud rate
**Split:** time-based 70/15/15 (train / val / test) — not random-stratified
**Candidates:** Logistic Regression, Random Forest, XGBoost, LightGBM
**Champion:** **XGBoost**, selected on validation-set net dollar value, confirmed once on a locked test set

---

## Champion at a glance

| Metric | Value |
|---|---|
| Test PR-AUC | 0.6966 |
| Dollar recall @ decision point | 90.7% |
| Net business value (~32-day test period) | $1,385,353 |
| Improvement over "do nothing" baseline | +$2,945,545 |
| P50 inference latency | 1.02ms |

XGBoost was selected on net dollar value, not raw PR-AUC — it edged out LightGBM (marginally higher PR-AUC) on calibration and false-positive cost, and beat Random Forest outright on latency (RF's 67ms P50 alone would consume most of the real-time scoring budget).

---

## Stage 01–02: Data quality & leakage analysis

Before any modeling: is the data what it claims to be, and does any feature already know the answer? Both checks came back clean.

| Check | Result | Verdict |
|---|---|---|
| Missing values | none | clean |
| Duplicate `transaction_id` | 0 | clean |
| Non-positive amounts | 0 | clean |
| Fraud vs. legit avg. amount | $349 vs. $83 | expected signal |
| Highest univariate feature AUC | 0.804 (`amount_to_avg_ratio`) | below 0.97 leakage threshold |
| Features flagged for leakage | 0 of 19 | clear to train |

**Method:** score each feature alone against the label (fraud-rate-encoded for categoricals), flag anything with univariate AUC > 0.97 — a single field predicting fraud almost perfectly in isolation is the standard fingerprint of a field only populated after the decision was made. Nothing came close; the strongest signal is an engineered ratio (transaction amount vs. that customer's own average), a legitimate fraud signal, not a leak.

---

## Stage 03: Time-based split, not random

Transactions sorted by time, cut 70/15/15:
- **Train:** Jan 1 – May 27 (700,000 rows, 3.08% fraud)
- **Validation:** May 27 – Jun 28 (150,000 rows, 3.03% fraud)
- **Test:** Jun 28 – Jul 29 (150,000 rows, 3.05% fraud)

A random split would let the model train on transactions minutes after ones it's tested on, inflating every metric relative to what it actually faces in production — where it only ever scores the future. Fraud rate held steady across all three splits, so the cut didn't accidentally skew class balance.

---

## Stage 04–05: Model comparison (validation set)

All four models trained on identical features and splits. **PR-AUC, not ROC-AUC, is the headline metric** — at a 3% fraud rate, ROC-AUC is dominated by the easy 97% and compresses real differences between models; PR-AUC and recall-at-fixed-FPR expose them.

| Model | PR-AUC | ROC-AUC | Recall@1%FPR | Recall@5%FPR | Precision@5%FPR | $ Recall@op | FP $ burden | Brier ↓ | Weekly σ | Latency P50 | Train time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Logistic Regression | 0.6412 | 0.8763 | 0.577 | 0.692 | 0.302 | 92.7% | $1,166,076 | 0.0898 | 0.0107 | 0.10ms | 6.3s |
| Random Forest | 0.6855 | 0.8812 | 0.644 | 0.707 | 0.307 | 93.2% | $1,019,669 | 0.0705 | 0.0099 | 66.87ms | 439.1s |
| **XGBoost ★** | 0.6959 | 0.8771 | 0.648 | 0.710 | 0.308 | 93.1% | **$913,669** | **0.0687** | 0.0107 | **1.02ms** | 64.7s |
| LightGBM | **0.6960** | 0.8782 | 0.650 | 0.711 | 0.308 | 93.2% | $941,356 | 0.0710 | 0.0116 | 2.67ms | 21.3s |

LightGBM technically posts the highest PR-AUC (0.6960 vs. XGBoost's 0.6959) — a gap of 0.0001, well inside noise. It's not what decides this: XGBoost has the lowest false-positive dollar burden and the best calibration, and both are far ahead of Random Forest on latency. That's why business value simulation (Stage 07), not this table, makes the final call.

### Latency — why Random Forest is disqualified from the real-time path

| Model | P50 | P95 | P99 | Batch throughput |
|---|---|---|---|---|
| Logistic Regression | 0.10ms | 0.24ms | 0.43ms | 43,977 rows/sec |
| **XGBoost ★** | **1.02ms** | **1.98ms** | 2.70ms | 80,011 rows/sec |
| LightGBM | 2.67ms | 4.00ms | 4.57ms | 38,875 rows/sec |
| Random Forest | **66.87ms** | **86.06ms** | 94.71ms | 8,207 rows/sec |

The blueprint's NFR1 budgets P50<100ms / P95<300ms for the *entire* request — DB lookups, feature building, network, and inference combined. RF's P95 alone is 86ms; XGBoost's is 1.98ms. This is a hard constraint, not a preference: RF is accurate enough to be a candidate on paper and operationally unusable in the single-transaction path regardless.

---

## Fraud-type coverage — recall at each model's 5%-FPR operating point (validation)

| Fraud type | Logistic Reg. | Random Forest | XGBoost ★ | LightGBM | Signature |
|---|---|---|---|---|---|
| account_takeover | 1.000 | 0.998 | 1.000 | 1.000 | new device + failed logins |
| new_beneficiary_scam | 1.000 | 1.000 | 1.000 | 1.000 | large amount, new payee |
| velocity_attack | 1.000 | 1.000 | 1.000 | 1.000 | rapid-fire transactions |
| card_not_present | 0.993 | 0.993 | 0.995 | 0.995 | new device, foreign merchant |
| cross_border_anomaly | 0.972 | 0.942 | 0.942 | 0.956 | 3rd-country IP mismatch |
| low_and_slow_takeover | 0.688 | 0.697 | 0.723 | 0.718 | deliberately subtle |
| friendly_fraud | 0.220 | 0.360 | 0.376 | 0.382 | looks like normal spend |
| label_noise | 0.035 | 0.050 | 0.038 | 0.038 | randomly flipped labels |

**Two rows are supposed to look bad.** `label_noise` is ~0.6% of records with their label randomly flipped by the generator — a model scoring ~4% recall on pure noise is behaving *correctly*; scoring high there would mean it memorized noise. `friendly_fraud` (a cardholder disputing their own legitimate-looking purchase) is deliberately engineered to resemble normal spending — low transaction-level recall here reflects a real limitation of scoring single transactions in isolation, not a fixable modeling gap. It needs dispute-pattern/behavioral history, out of scope for a transaction-level score.

---

## Stage 06: Economic policy — XGBoost's locked decision bands

Each band boundary is chosen by sweeping candidate thresholds on validation scores and maximizing `fraud $ caught − cost × false positives`, where cost escalates with the action's real friction (step-up auth ≈ $2, manual review ≈ $15, wrongful decline ≈ $50 — placeholders pending real Risk/Compliance figures, see Assumptions below). Guardrails cap each band's FPR, and two operational constraints can override the cost-optimal point outright: **review capacity** (manual_review can't imply more daily volume than analysts can work) and **alert volume** (total flagged can't exceed 10% of daily traffic). Both bit here — the step-up threshold was raised above its raw cost-optimum because the alert-volume cap was binding.

| Band | Threshold | TPR | FPR | Est. daily volume | Constraint that bound |
|---|---|---|---|---|---|
| Monitor (approve) | < 0.482 | — | — | ~90.0% of traffic | — |
| Step-up auth | ≥ 0.482 | 0.759 | 0.092 | ~356/day | alert-volume cap (raised from 526/day uncapped) |
| Manual review | ≥ 0.806 | 0.635 | 0.005 | ~9/day | cost-optimum (well within analyst capacity) |
| Decline | ≥ 0.858 | 0.624 | 0.003 | ~103/day | cost-optimum, FPR guardrail ≤1% |

Notice decline (~103/day) catches more volume than manual_review (~9/day) despite being the stricter band — the model's confidence for true fraud is heavily polarized: once a transaction crosses ~0.81, scores cluster very high rather than spreading evenly, so the "manual review" slice between the two cutoffs is thin by construction, not by mistake.

Hard rule overrides (sanctioned-country hits, OFAC matches) are **not** part of this sweep — those bypass the score entirely per the blueprint's hybrid rules+ML design (Section 3.5) and always resolve to Decline regardless of what the model says.

---

## Stage 07: Business value simulation — this is what actually picks the champion

Each model's own tuned policy, priced in dollars over the validation period, with realistic prevention efficacy per band (decline stops ~100% of the fraud routed to it; manual review catches ~90%; step-up deters ~40% — fraudsters who can complete OTP/2FA get through anyway; monitor stops nothing). Net value = value prevented − friction cost imposed on legitimate customers.

| Model | Net value (validation) |
|---|---|
| **XGBoost ★** | **$1,368,321** |
| Random Forest | $1,363,422 |
| LightGBM | $1,363,059 |
| Logistic Regression | $1,304,134 |

All four beat "do nothing" (−$1,541,304 in pure fraud loss) by roughly $2.85–2.91M over the ~32-day validation window. XGBoost's margin over LightGBM/Random Forest is modest in isolation (~$5–9K) — its case is really the combination of this result *plus* the calibration and latency advantages above, not this chart alone.

---

## Stage 08: Final result — evaluated once, on data nothing above has seen

Every choice above — which model, which thresholds, which policy — was made using validation data only. Test (Jun 28 – Jul 29) was read exactly once, here. Nothing downstream feeds back into a decision; these are the numbers that stand as expected production performance.

| Metric | Validation | Test (locked, final) | Δ |
|---|---|---|---|
| PR-AUC | 0.6959 | 0.6966 | +0.0007 |
| ROC-AUC | 0.8771 | 0.8759 | −0.0012 |
| Recall @ 5% FPR | 0.710 | 0.713 | +0.003 |
| Brier score | 0.0687 | 0.0680 | stable |
| Net business value | $1,368,321 | $1,385,353 | consistent scale |

Validation and test track each other closely on every headline metric — the model and thresholds weren't overfit to the validation window. That's the point of locking before this step.

### Where test diverges: fraud-type recall

| Fraud type | Validation | Test | Δ |
|---|---|---|---|
| cross_border_anomaly | 0.942 | 0.806 | −0.14 |
| low_and_slow_takeover | 0.723 | 0.481 | −0.24 |
| friendly_fraud | 0.376 | 0.079 | −0.30 |

**This is a real finding, not noise to explain away.** Three of the harder-to-detect fraud types recall noticeably worse in the test month than validation, even though aggregate PR-AUC held steady — aggregate metrics can mask exactly this kind of type-specific drift. Weekly PR-AUC on test ranged 0.667–0.780, a wider spread than validation's 0.638–0.710. This is precisely what the production monitoring loop (population/score-distribution drift, checked weekly — see below) exists to catch before it shows up in chargebacks 60 days later. Flagged as a Phase 4 watch item, not treated as a blocker to shipping.

### Calibration (validation set, champion) — a real weakness, stated plainly

Brier score 0.0687 is the best of the four models *relatively*, but XGBoost's raw probabilities are **not well calibrated in absolute terms** through most of the range:

| Score bin | Mean predicted | Observed fraud rate |
|---|---|---|
| 0.1–0.2 | 0.157 | 0.007 |
| 0.3–0.4 | 0.351 | 0.022 |
| 0.5–0.6 | 0.546 | 0.037 |
| 0.7–0.8 | 0.744 | 0.077 |
| 0.8–0.9 | 0.846 | 0.180 |
| 0.9–1.0 | 0.988 | 0.903 |

A score of 0.85 corresponds to an actual observed fraud rate of 18%, not 85% — the model is substantially overconfident everywhere except the very top bin. This is typical, uncorrected behavior for gradient-boosted trees (the loss function optimizes ranking, not probability calibration) and doesn't invalidate anything above: **the decision bands were tuned directly against realized TPR/FPR/dollar outcomes at each threshold, not against the raw score's face value**, so Stage 06's thresholds are unaffected. What it does mean: the raw score should not be surfaced to an analyst as "72% fraud probability" without first running it through a calibration step (Platt scaling or isotonic regression on held-out data) — flagged here as a concrete Phase 1 explainability follow-up, not a blocker to shipping the band-based decisioning.

---

## Methodology: how the threshold was actually decided

Not by eyeballing an ROC curve or defaulting to 0.5. The process, in order:

1. **Price each action's false-positive cost.** Step-up auth, manual review, and decline impose escalating friction on a wrongly-flagged legitimate customer — a minor OTP prompt is not the same as a blocked purchase. Assumed: $2 / $15 / $50 (placeholders — see below).
2. **Sweep thresholds on validation scores, maximize net dollar value** — fraud $ caught minus (false positives × that action's cost) — not F1, not Youden's J, not a round number.
3. **Apply guardrails, don't just report them.** Max FPR per band (15% / 5% / 1%, tightening as the action gets more punitive) and a floor check on TPR — anything pinned near 100% detection gets flagged as a sign the threshold is trivially low, not a win.
4. **Apply operational constraints that can override the cost-optimum.** Review capacity (can analysts actually work that manual-review volume?) and alert-volume (total flagged capped at 10% of daily traffic) both bound the step-up threshold here.
5. **Carve out hard rule overrides entirely.** A sanctioned-country hit isn't subject to this economic sweep — it's an always-decline regardless of model score. The threshold optimization governs the model's lane, not the whole decision.
6. **Lock on validation, confirm once on test.** Never re-tune against the number you're about to report.

---

## Assumptions this report is not entitled to make up

Every dollar figure above depends on business inputs this exercise doesn't have. They're placeholders, clearly labeled, so the *method* can be validated now and the *numbers* corrected the moment real figures exist — re-running Stages 06–08 with updated constants is all that's required.

| Assumption | Value used | Source needed |
|---|---|---|
| Step-up auth FP cost | $2.00 | Risk/Compliance — real friction & churn cost per action |
| Manual review FP cost | $15.00 | ″ |
| Wrongful decline FP cost | $50.00 | ″ |
| Analyst review capacity | 1,000/day | Fraud ops staffing (assumed 5 analysts × 200/day) |
| Max alert volume share | 10% of daily traffic | Alert-fatigue tolerance, ops-defined |
| Decline prevention efficacy | 100% | Measured from a production shadow/pilot period |
| Manual review efficacy | 90% | ″ |
| Step-up auth efficacy | 40% | ″ |

---

## Before this scores a real transaction

- **Shadow mode, not a cutover.** Score live traffic in parallel with the current system for 1–2 weeks, log would-be decisions, act on none of them — then canary a small traffic share before full rollout.
- **Monitor score distribution, not accuracy.** Chargeback labels arrive 30–90 days late; waiting on them to detect drift means flying blind for a quarter. Track population/score-distribution shift (PSI) weekly instead.
- **Watch the three fraud types that degraded on test** specifically — `cross_border_anomaly`, `low_and_slow_takeover`, `friendly_fraud` — in the first month of shadow mode before trusting aggregate PR-AUC alone.
- **Reject inference risk, flagged for later.** Once declines start happening, the model never observes whether those transactions would have been fraud — future training data only reflects approved traffic. Not solvable without a retraining pipeline (explicitly Phase 2), but worth writing down now.

---

*Pipeline: `ml/training/01…08_*.py` — `common.py` holds shared feature spec & metrics. Full reports: `ml/artifacts/*.json`. Champion lock: `ml/artifacts/champion.json`.*
