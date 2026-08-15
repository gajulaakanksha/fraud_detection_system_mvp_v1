"""Stage 07 -- Business Value Simulation -> Champion Selection.

Each model's own tuned policy (stage 06) gets simulated over the validation
period in dollar terms, not ML metrics. This is what actually picks the
champion: the model with the best PR-AUC doesn't automatically win if its
policy produces less net dollar value once realistic prevention efficacy and
friction costs are applied.

Prevention efficacy per band (common.ACTION_PREVENTION_EFFICACY) -- a DECLINE
stops ~all fraud in it; MANUAL_REVIEW catches most but analysts miss some;
STEP_UP_AUTH deters some fraudsters (can't complete OTP/2FA) but plenty get
through anyway; MONITOR stops nothing. These are placeholder assumptions
pending real measured efficacy from a production pilot -- the simulation
method doesn't change once real numbers replace them, only the outputs do.

    net_value = sum(band fraud $ x efficacy) - sum(band legit count x fp_cost)

compared against baseline_do_nothing = -total_fraud_value (no system at all).

Usage (from ml/training/, after 06_threshold_policy.py):
    python 07_business_value_simulation.py
"""
import json

import numpy as np

from common import ACTION_FP_COST, ACTION_PREVENTION_EFFICACY, ARTIFACTS_DIR, MODEL_NAMES, load_scores


def simulate(y_true, scores, amount, policy: dict) -> dict:
    t1 = policy["step_up_auth"]["threshold"]
    t2 = policy["manual_review"]["threshold"]
    t3 = policy["decline"]["threshold"]

    bands = {
        "monitor": (scores < t1),
        "step_up_auth": (scores >= t1) & (scores < t2),
        "manual_review": (scores >= t2) & (scores < t3),
        "decline": (scores >= t3),
    }

    total_fraud_value = amount[y_true == 1].sum()
    band_detail = {}
    total_prevented = 0.0
    total_friction_cost = 0.0
    for band, mask in bands.items():
        fraud_value_in_band = amount[mask & (y_true == 1)].sum()
        legit_count_in_band = int((mask & (y_true == 0)).sum())
        efficacy = ACTION_PREVENTION_EFFICACY[band]
        fp_cost = ACTION_FP_COST.get(band, 0.0)
        prevented = fraud_value_in_band * efficacy
        friction = legit_count_in_band * fp_cost
        total_prevented += prevented
        total_friction_cost += friction
        band_detail[band] = {
            "n_total": int(mask.sum()),
            "fraud_value_in_band": float(fraud_value_in_band),
            "legit_count_in_band": legit_count_in_band,
            "prevention_efficacy_assumed": efficacy,
            "value_prevented": float(prevented),
            "friction_cost": float(friction),
        }

    net_value = total_prevented - total_friction_cost
    baseline_do_nothing = -float(total_fraud_value)
    return {
        "total_fraud_value": float(total_fraud_value),
        "total_value_prevented": float(total_prevented),
        "total_friction_cost": float(total_friction_cost),
        "net_value": float(net_value),
        "baseline_do_nothing": baseline_do_nothing,
        "improvement_over_do_nothing": float(net_value - baseline_do_nothing),
        "bands": band_detail,
    }


def main() -> None:
    policies = json.loads((ARTIFACTS_DIR / "06_threshold_policy_report.json").read_text())
    eval_report = json.loads((ARTIFACTS_DIR / "05_evaluation_report.json").read_text())

    results = {}
    for name in MODEL_NAMES:
        val = load_scores(name, "val")
        y = val["fraud_label"].to_numpy()
        scores = val["score"].to_numpy()
        amount = val["amount"].to_numpy()
        sim = simulate(y, scores, amount, policies[name])
        results[name] = sim
        print(f"\n=== {name} ===")
        print(f"  Total fraud value in period: ${sim['total_fraud_value']:,.0f}")
        print(f"  Value prevented:             ${sim['total_value_prevented']:,.0f}")
        print(f"  Friction cost incurred:      ${sim['total_friction_cost']:,.0f}")
        print(f"  NET VALUE:                   ${sim['net_value']:,.0f}")
        print(f"  vs. do-nothing baseline:     ${sim['baseline_do_nothing']:,.0f}  "
              f"(improvement: ${sim['improvement_over_do_nothing']:,.0f})")

    ranked = sorted(results.items(), key=lambda kv: -kv[1]["net_value"])
    champion_name, champion_sim = ranked[0]

    print("\n\n=== CHAMPION SELECTION ===")
    print(f"{'model':<22s}{'net_value':>14s}{'PR-AUC':>9s}")
    for name, sim in ranked:
        print(f"{name:<22s}{sim['net_value']:>14,.0f}{eval_report[name]['pr_auc']:>9.4f}")
    print(f"\nChampion (highest net dollar value on validation): {champion_name}")

    champion = {
        "champion_model": champion_name,
        "selection_basis": "highest net_value in business value simulation on validation set",
        "policy": policies[champion_name],
        "business_value_summary": champion_sim,
        "runner_up_comparison": {name: sim["net_value"] for name, sim in ranked},
    }
    (ARTIFACTS_DIR / "07_business_value_report.json").write_text(json.dumps(results, indent=2))
    (ARTIFACTS_DIR / "champion.json").write_text(json.dumps(champion, indent=2))
    print("\nWrote ml/artifacts/07_business_value_report.json and champion.json")
    print(f"\nMODEL + THRESHOLDS NOW LOCKED: {champion_name}. Proceed to 08_final_test_evaluation.py.")


if __name__ == "__main__":
    main()
