from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.model_client import create_client, request_plan
from common.scenario import generate_split
from common.scoring import score_plan

OUTPUT = Path(__file__).resolve().parent / "traces" / "pilot.jsonl"


def main(count: int, attempts: int, confirm_paid: bool) -> None:
    if not confirm_paid:
        raise SystemExit("billable model pilot blocked; rerun with --confirm-paid")
    load_dotenv(override=True)
    deployments = {"teacher": os.environ["TEACHER_DEPLOYMENT"]}
    if raw_rft := os.environ.get("RFT_BASE_DEPLOYMENT"):
        deployments["raw_rft"] = raw_rft
    if raw_sft := os.environ.get("SFT_BASE_DEPLOYMENT"):
        deployments["raw_sft"] = raw_sft
    client = create_client()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as output:
        for scenario in generate_split(20_000, count):
            record = {"scenario": scenario, "arms": {}}
            for arm, deployment in deployments.items():
                best = None
                candidates = []
                max_attempts = attempts if arm == "teacher" else 1
                for attempt in range(1, max_attempts + 1):
                    plan, usage = request_plan(client, deployment, scenario)
                    result = score_plan(plan, scenario)
                    candidate = {"attempt": attempt, "plan": plan, "result": result, "usage": usage}
                    if best is None or result["score"] > best["result"]["score"]:
                        best = candidate
                    candidates.append(candidate)
                record["arms"][arm] = {"best": best, "attempts": candidates}
            output.write(json.dumps(record) + "\n")
            print(scenario["scenario_id"], {arm: round(value["best"]["result"]["score"], 3) for arm, value in record["arms"].items()})
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--teacher-attempts", type=int, default=3)
    parser.add_argument("--confirm-paid", action="store_true")
    args = parser.parse_args()
    main(args.count, args.teacher_attempts, args.confirm_paid)