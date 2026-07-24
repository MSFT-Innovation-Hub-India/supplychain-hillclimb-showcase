from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.model_client import create_client, request_plan
from common.scenario import generate_split
from common.scoring import score_plan

RESULTS = Path(__file__).resolve().parent / "results"


def plan_pattern(plan: dict | None, scenario: dict) -> str:
    if not isinstance(plan, dict) or not isinstance(plan.get("decisions"), list):
        return "invalid"
    orders = {order["order_id"]: order for order in scenario["orders"]}
    ship = substitute = expedite = 0
    for decision in plan["decisions"]:
        if decision.get("action") == "ship":
            ship += 1
            expedite += decision.get("shipping_mode") == "expedite"
            order = orders.get(decision.get("order_id"))
            substitute += bool(order and decision.get("sku") != order["sku"])
    total = max(1, len(scenario["orders"]))
    return (
        f"ship_fraction={round(ship / total, 1)};"
        f"substitute_fraction={round(substitute / max(1, ship), 1)};"
        f"expedite_fraction={round(expedite / max(1, ship), 1)}"
    )


def write_progress(path: Path, deployment: str, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"deployment": deployment, "rows": rows}, indent=2), encoding="utf-8")
    temporary.replace(path)


def evaluate_arm(client, deployment: str, scenarios: list[dict], progress_path: Path) -> dict:
    rows = []
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        if progress.get("deployment") != deployment:
            raise ValueError(f"checkpoint deployment mismatch: {progress_path}")
        rows = progress.get("rows", [])
    completed = {row["scenario_id"] for row in rows}
    for scenario in scenarios:
        if scenario["scenario_id"] in completed:
            print(deployment, scenario["scenario_id"], "resumed")
            continue
        plan, usage = request_plan(client, deployment, scenario)
        result = score_plan(plan, scenario)
        rows.append({"scenario_id": scenario["scenario_id"], "plan": plan, "result": result, "usage": usage, "pattern": plan_pattern(plan, scenario)})
        write_progress(progress_path, deployment, rows)
        print(deployment, scenario["scenario_id"], round(result["score"], 3), result["category"])
    patterns = Counter(row["pattern"] for row in rows)
    all_defer = sum(row["pattern"].startswith("ship_fraction=0.0;") for row in rows) / len(rows)
    return {
        "deployment": deployment,
        "mean_score": statistics.mean(row["result"]["score"] for row in rows),
        "feasible_rate": statistics.mean(row["result"]["feasible"] for row in rows),
        "dominant_pattern_share": max(patterns.values()) / len(rows),
        "all_defer_share": all_defer,
        "patterns": dict(patterns),
        "rows": rows,
    }


def paired_bootstrap(left: list[float], right: list[float], iterations: int = 10_000) -> dict:
    rng = random.Random(20260722)
    differences = [a - b for a, b in zip(left, right)]
    samples = []
    for _ in range(iterations):
        samples.append(statistics.mean(rng.choice(differences) for _ in differences))
    samples.sort()
    return {
        "mean_difference": statistics.mean(differences),
        "ci95": [samples[int(iterations * 0.025)], samples[int(iterations * 0.975)]],
    }


def main(arms: list[str], count: int, comparison: str | None, confirm_paid: bool) -> None:
    if not confirm_paid:
        raise SystemExit("billable live evaluation blocked; rerun with --confirm-paid")
    parsed = dict(arm.split("=", 1) for arm in arms)
    scenarios = generate_split(50_000, count, ("tight", "mixed", "loose"))
    client = create_client()
    RESULTS.mkdir(parents=True, exist_ok=True)
    results = {}
    progress_paths = []
    for label, deployment in parsed.items():
        deployment_key = hashlib.sha256(deployment.encode()).hexdigest()[:12]
        progress_path = RESULTS / f".{label}-{count}-{deployment_key}.progress.json"
        progress_paths.append(progress_path)
        results[label] = evaluate_arm(client, deployment, scenarios, progress_path)
    report = {"scenario_count": count, "arms": results}
    if comparison:
        left_label, right_label = comparison.split(",", 1)
        left = [row["result"]["score"] for row in results[left_label]["rows"]]
        right = [row["result"]["score"] for row in results[right_label]["rows"]]
        report["comparison"] = {"labels": [left_label, right_label], **paired_bootstrap(left, right)}
    if {"rft", "sft"}.issubset(results):
        comparison_result = paired_bootstrap(
            [row["result"]["score"] for row in results["rft"]["rows"]],
            [row["result"]["score"] for row in results["sft"]["rows"]],
        )
        criteria = {
            "rft_beats_sft_by_5_points": comparison_result["mean_difference"] >= 0.05,
            "paired_ci_excludes_zero": comparison_result["ci95"][0] > 0.0,
            "rft_not_pattern_collapsed": results["rft"]["dominant_pattern_share"] < 0.80,
            "rft_not_defer_collapsed": results["rft"]["all_defer_share"] < 0.80,
        }
        optional_criteria = {}
        limitations = []
        if "raw_rft" in results:
            optional_criteria = {
                "rft_improves_over_raw_rft": results["rft"]["mean_score"] > results["raw_rft"]["mean_score"],
                "rft_feasibility_does_not_regress": results["rft"]["feasible_rate"] >= results["raw_rft"]["feasible_rate"],
            }
        else:
            limitations.append(
                "Raw o4-mini is deprecated and cannot be deployed; RFT uplift over its raw checkpoint is not evaluated."
            )
        report["rft_win"] = {
            "passed": all(criteria.values()) and all(optional_criteria.values()),
            "criteria": criteria,
            "optional_raw_baseline_criteria": optional_criteria,
            "comparison": comparison_result,
            "limitations": limitations,
        }
    path = RESULTS / f"evaluation-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for progress_path in progress_paths:
        progress_path.unlink(missing_ok=True)
    summary = {
        label: {key: value for key, value in result.items() if key != "rows"}
        for label, result in results.items()
    }
    print(json.dumps({"arms": summary, "comparison": report.get("comparison"), "rft_win": report.get("rft_win"), "result_file": str(path)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", action="append", required=True, help="label=deployment; repeat for each arm")
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--compare", help="left_label,right_label; reports left minus right")
    parser.add_argument("--confirm-paid", action="store_true")
    args = parser.parse_args()
    main(args.arm, args.count, args.compare, args.confirm_paid)