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
from common.fine_tuning_api import require_paid_confirmation, require_pilot_gate

OUTPUT = Path(__file__).resolve().parent / "traces" / "training.jsonl"


def capture_split(client, deployment: str, split: str, scenarios: list[dict], attempts: int, threshold: float, output, completed: set[tuple[str, str]]) -> None:
    for scenario in scenarios:
        key = (split, scenario["scenario_id"])
        if key in completed:
            print(split, scenario["scenario_id"], "resumed")
            continue
        candidates = []
        for attempt in range(1, attempts + 1):
            plan, usage = request_plan(client, deployment, scenario)
            result = score_plan(plan, scenario)
            candidates.append({"attempt": attempt, "plan": plan, "result": result, "usage": usage})
        best = max(candidates, key=lambda candidate: candidate["result"]["score"])
        output.write(json.dumps({
            "split": split,
            "scenario": scenario,
            "teacher": best,
            "sft_usable": best["result"]["feasible"] and best["result"]["score"] >= threshold,
        }) + "\n")
        output.flush()
        print(split, scenario["scenario_id"], round(best["result"]["score"], 3), f"attempt={best['attempt']}")

def main(train_count: int, valid_count: int, attempts: int, threshold: float, confirm_paid: bool, resume: bool) -> None:
    require_paid_confirmation(confirm_paid)
    require_pilot_gate(Path(__file__).resolve().parents[1])
    load_dotenv(override=True)
    client = create_client()
    deployment = os.environ["TEACHER_DEPLOYMENT"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    completed: set[tuple[str, str]] = set()
    if resume and OUTPUT.exists():
        completed = {
            (row["split"], row["scenario"]["scenario_id"])
            for line in OUTPUT.open(encoding="utf-8")
            if (row := json.loads(line))
        }
    with OUTPUT.open("a" if resume else "w", encoding="utf-8") as output:
        capture_split(client, deployment, "train", generate_split(30_000, train_count), attempts, threshold, output, completed)
        capture_split(client, deployment, "valid", generate_split(40_000, valid_count), attempts, threshold, output, completed)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=300)
    parser.add_argument("--valid", type=int, default=60)
    parser.add_argument("--teacher-attempts", type=int, default=3)
    parser.add_argument("--sft-threshold", type=float, default=0.75)
    parser.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    main(args.train, args.valid, args.teacher_attempts, args.sft_threshold, args.confirm_paid, args.resume)