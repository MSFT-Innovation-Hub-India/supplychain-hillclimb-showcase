from __future__ import annotations

import argparse
import hashlib
import json
import math
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
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "visible_output_tokens",
    "total_tokens",
)


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


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def parse_pricing(entries: list[str]) -> dict[str, dict[str, float]]:
    pricing = {}
    for entry in entries:
        label, values = entry.split("=", 1)
        rates = [float(value) for value in values.split(",")]
        if len(rates) not in {2, 3} or any(rate < 0 for rate in rates):
            raise ValueError("pricing must be label=input_rate,output_rate[,cached_input_rate]")
        pricing[label] = {
            "input_per_million": rates[0],
            "output_per_million": rates[1],
            "cached_input_per_million": rates[2] if len(rates) == 3 else rates[0],
        }
    return pricing


def summarize_quality(rows: list[dict]) -> dict:
    categories = Counter(row["result"]["category"] for row in rows)
    count = len(rows)
    metric_names = ("service", "margin", "cost", "shipped_orders")
    means = {
        name: statistics.mean(row["result"].get("metrics", {}).get(name, 0.0) for row in rows)
        for name in metric_names
    }
    feasible_metrics = [row["result"]["metrics"] for row in rows if row["result"]["feasible"]]
    return {
        "mean_score": statistics.mean(row["result"]["score"] for row in rows),
        "feasible_rate": statistics.mean(row["result"]["feasible"] for row in rows),
        "mean_service": means["service"],
        "mean_retained_margin": means["margin"],
        "mean_cost_efficiency": means["cost"],
        "mean_shipping_cost_feasible": statistics.mean(
            metrics["shipping_cost"] for metrics in feasible_metrics
        ) if feasible_metrics else None,
        "mean_expedite_spend_feasible": statistics.mean(
            metrics["expedite_spend"] for metrics in feasible_metrics
        ) if feasible_metrics else None,
        "mean_shipped_orders": means["shipped_orders"],
        "failure_category_counts": {category: value for category, value in categories.items() if category != "feasible"},
        "failure_category_rates": {
            category: value / count for category, value in categories.items() if category != "feasible"
        },
    }


def summarize_inference(rows: list[dict], rates: dict[str, float] | None) -> dict:
    usages = [row.get("usage", {}) for row in rows]
    normalized = []
    for usage in usages:
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)))
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)))
        normalized.append(
            {
                "input_tokens": input_tokens,
                "cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
                "output_tokens": output_tokens,
                "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
                "visible_output_tokens": int(usage.get("visible_output_tokens", output_tokens)),
                "total_tokens": int(usage.get("total_tokens", input_tokens + output_tokens)),
            }
        )
    totals = {field: sum(usage[field] for usage in normalized) for field in TOKEN_FIELDS}
    count = len(rows)
    latencies = [float(usage["latency_seconds"]) for usage in usages if "latency_seconds" in usage]
    telemetry_complete = all(
        "reasoning_tokens" in usage and "latency_seconds" in usage for usage in usages
    )
    cost = None
    if rates:
        uncached_input_tokens = totals["input_tokens"] - totals["cached_input_tokens"]
        total_usd = (
            uncached_input_tokens * rates["input_per_million"]
            + totals["cached_input_tokens"] * rates["cached_input_per_million"]
            + totals["output_tokens"] * rates["output_per_million"]
        ) / 1_000_000
        cost = {
            "estimated_total_usd": total_usd,
            "estimated_usd_per_scenario": total_usd / count,
            "rates_usd_per_million_tokens": rates,
        }
    return {
        "telemetry_complete": telemetry_complete,
        "token_semantics": "output_tokens includes reasoning_tokens; reasoning is not billed a second time",
        "totals": totals,
        "averages_per_scenario": {field: totals[field] / count for field in TOKEN_FIELDS},
        "latency_seconds": {
            "mean": statistics.mean(latencies) if latencies else None,
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "cost": cost,
    }


def hill_climb_points(results: dict[str, dict]) -> list[dict]:
    points = []
    for label, result in results.items():
        quality = result["quality"]
        inference = result["inference"]
        cost = inference["cost"] or {}
        points.append(
            {
                "label": label,
                "deployment": result["deployment"],
                "quality_score": quality["mean_score"],
                "feasible_rate": quality["feasible_rate"],
                "mean_service": quality["mean_service"],
                "mean_retained_margin": quality["mean_retained_margin"],
                "mean_cost_efficiency": quality["mean_cost_efficiency"],
                "p50_latency_seconds": inference["latency_seconds"]["p50"],
                "p95_latency_seconds": inference["latency_seconds"]["p95"],
                "average_input_tokens": inference["averages_per_scenario"]["input_tokens"],
                "average_output_tokens": inference["averages_per_scenario"]["output_tokens"],
                "average_reasoning_tokens": inference["averages_per_scenario"]["reasoning_tokens"],
                "estimated_usd_per_scenario": cost.get("estimated_usd_per_scenario"),
            }
        )
    return points


def evaluate_arm(
    client,
    deployment: str,
    scenarios: list[dict],
    progress_path: Path,
    rates: dict[str, float] | None,
) -> dict:
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
    quality = summarize_quality(rows)
    return {
        "deployment": deployment,
        "mean_score": quality["mean_score"],
        "feasible_rate": quality["feasible_rate"],
        "dominant_pattern_share": max(patterns.values()) / len(rows),
        "all_defer_share": all_defer,
        "quality": quality,
        "inference": summarize_inference(rows, rates),
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


def main(
    arms: list[str],
    count: int,
    comparison: str | None,
    pricing_entries: list[str],
    confirm_paid: bool,
) -> None:
    if not confirm_paid:
        raise SystemExit("billable live evaluation blocked; rerun with --confirm-paid")
    parsed = dict(arm.split("=", 1) for arm in arms)
    pricing = parse_pricing(pricing_entries)
    unknown_pricing_labels = set(pricing) - set(parsed)
    if unknown_pricing_labels:
        raise ValueError(f"pricing supplied for unknown arms: {sorted(unknown_pricing_labels)}")
    scenarios = generate_split(50_000, count, ("tight", "mixed", "loose"))
    client = create_client()
    RESULTS.mkdir(parents=True, exist_ok=True)
    results = {}
    progress_paths = []
    for label, deployment in parsed.items():
        deployment_key = hashlib.sha256(deployment.encode()).hexdigest()[:12]
        progress_path = RESULTS / f".{label}-{count}-{deployment_key}.progress.json"
        progress_paths.append(progress_path)
        results[label] = evaluate_arm(client, deployment, scenarios, progress_path, pricing.get(label))
    report = {
        "scenario_count": count,
        "arms": results,
        "hill_climb": {
            "dimensions": {
                "quality": "mean deterministic business score; higher is better",
                "cost": "estimated USD per scenario from explicit token rates; lower is better",
                "latency": "end-to-end model-call seconds; lower is better",
            },
            "points": hill_climb_points(results),
        },
    }
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
    parser.add_argument(
        "--pricing",
        action="append",
        default=[],
        help="label=input_usd_per_million,output_usd_per_million[,cached_input_usd_per_million]",
    )
    parser.add_argument("--confirm-paid", action="store_true")
    args = parser.parse_args()
    main(args.arm, args.count, args.compare, args.pricing, args.confirm_paid)