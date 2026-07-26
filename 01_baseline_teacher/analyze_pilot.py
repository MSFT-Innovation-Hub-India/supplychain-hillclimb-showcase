"""Analyze captured pilot traces and write the go/no-go gate artifact."""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.scoring import score_plan

INPUT = Path(__file__).resolve().parent / "traces" / "pilot.jsonl"
OUTPUT = Path(__file__).resolve().parent / "traces" / "pilot_gate.json"


def pattern(plan: dict | None) -> str:
    if not isinstance(plan, dict) or not isinstance(plan.get("decisions"), list):
        return "invalid"
    actions = Counter(decision.get("action") for decision in plan["decisions"] if isinstance(decision, dict))
    modes = Counter(
        decision.get("shipping_mode") for decision in plan["decisions"]
        if isinstance(decision, dict) and decision.get("action") == "ship"
    )
    total = max(1, actions["ship"] + actions["defer"])
    ship = actions["ship"]
    return (
        f"ship_fraction={round(ship / total, 1)};"
        f"standard_fraction={round(modes['standard'] / max(1, ship), 1)};"
        f"expedite_fraction={round(modes['expedite'] / max(1, ship), 1)}"
    )


def main() -> int:
    rows = [json.loads(line) for line in INPUT.open(encoding="utf-8")]
    summary = {}
    required_arms = {"teacher"}
    available_arms = set(rows[0]["arms"])
    missing_arms = required_arms - available_arms
    if missing_arms:
        raise SystemExit(f"pilot trace is missing required arms: {sorted(missing_arms)}")
    for arm in sorted(available_arms):
        best = [row["arms"][arm]["best"] for row in rows]
        results = [score_plan(candidate["plan"], row["scenario"]) for candidate, row in zip(best, rows)]
        first_attempts = [row["arms"][arm]["attempts"][0] for row in rows]
        first_attempt_results = [
            score_plan(candidate["plan"], row["scenario"])
            for candidate, row in zip(first_attempts, rows)
        ]
        patterns = Counter(pattern(candidate["plan"]) for candidate in best)
        summary[arm] = {
            "mean_score": round(statistics.mean(result["score"] for result in results), 4),
            "feasible_rate": round(statistics.mean(result["feasible"] for result in results), 4),
            "partial_reward_rate": round(statistics.mean(0.05 <= result["score"] < 0.80 for result in results), 4),
            "score_stddev": round(statistics.pstdev(result["score"] for result in results), 4),
            "dominant_pattern_share": round(max(patterns.values()) / len(rows), 4),
            "first_attempt_mean": round(statistics.mean(result["score"] for result in first_attempt_results), 4),
            "first_attempt_high_quality_rate": round(statistics.mean(result["score"] >= 0.90 for result in first_attempt_results), 4),
        }
    checks = {
        "teacher_not_effortlessly_near_optimal": (
            summary["teacher"]["first_attempt_high_quality_rate"] < 0.80
            and summary["teacher"]["first_attempt_mean"] < 0.90
        ),
    }
    if "raw_rft" in summary:
        checks.update({
            "raw_rft_feasible_at_least_20pct": summary["raw_rft"]["feasible_rate"] >= 0.20,
            "raw_rft_has_dense_partial_reward": summary["raw_rft"]["partial_reward_rate"] >= 0.20,
            "raw_rft_reward_varies": summary["raw_rft"]["score_stddev"] >= 0.05,
            "raw_rft_not_pattern_collapsed": summary["raw_rft"]["dominant_pattern_share"] < 0.80,
            "raw_rft_has_headroom": summary["raw_rft"]["mean_score"] < 0.85,
        })
    report = {
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "limitations": [] if "raw_rft" in summary else [
            "Raw o4-mini is deprecated and cannot be deployed; baseline competence and RFT uplift over its raw checkpoint are unmeasurable."
        ],
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {OUTPUT}")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())