"""Check scenario and reward suitability before paid model experiments."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.baselines import defer_all, greedy_plan
from common.scenario import generate_split
from common.scoring import score_plan


def main(count: int) -> int:
    scenarios = generate_split(10_000, count)
    strategies = {
        "defer_all": defer_all,
        "greedy_priority": lambda scenario: greedy_plan(scenario, "priority"),
        "greedy_margin": lambda scenario: greedy_plan(scenario, "margin"),
    }
    scores = {
        name: [score_plan(planner(scenario), scenario)["score"] for scenario in scenarios]
        for name, planner in strategies.items()
    }
    plan_pairs = [(greedy_plan(scenario, "priority"), greedy_plan(scenario, "margin")) for scenario in scenarios]
    distinct = sum(left != right for left, right in plan_pairs)
    distinct_high_quality = sum(
        left != right
        and score_plan(left, scenario)["score"] >= 0.85
        and score_plan(right, scenario)["score"] >= 0.85
        for scenario, (left, right) in zip(scenarios, plan_pairs)
    )
    report = {
        "scenario_count": count,
        "mean_scores": {name: round(statistics.mean(values), 4) for name, values in scores.items()},
        "greedy_plan_variants_differ": distinct,
        "distinct_high_quality_plan_pairs": distinct_high_quality,
        "checks": {
            "defer_shortcut_noncompetitive": statistics.mean(scores["defer_all"]) + 0.20 < statistics.mean(scores["greedy_priority"]),
            "multiple_plan_patterns": distinct >= max(3, count // 10),
            "multiple_high_quality_plans": distinct_high_quality >= max(3, count // 10),
            "simple_greedy_not_near_ceiling": max(statistics.mean(scores["greedy_priority"]), statistics.mean(scores["greedy_margin"])) < 0.90,
        },
    }
    report["passed"] = all(report["checks"].values())
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    raise SystemExit(main(args.count))