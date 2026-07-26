"""Audit environment, datasets, grader, and split integrity before RFT submission."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from common.baselines import defer_all, greedy_plan
from common.prompts import SYSTEM_PROMPT, scenario_message
from common.scenario import generate_scenario, generate_split
from common.scoring import score_plan

DATA = ROOT / "02_dataset_build" / "data"
CAPTURE = ROOT / "01_baseline_teacher" / "traces" / "training.jsonl"
PILOT_GATE = ROOT / "01_baseline_teacher" / "traces" / "pilot_gate.json"
GRADER = ROOT / "03_finetuning" / "rft" / "grader.json"
GRADER_BUILDER = ROOT / "03_finetuning" / "rft" / "build_grader.py"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grader_definition() -> dict:
    spec = importlib.util.spec_from_file_location("audit_grader_builder", GRADER_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load grader builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.grader_definition()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def audit_dataset(path: Path, expected_count: int) -> tuple[list[dict], set[str]]:
    rows = load_jsonl(path)
    check(len(rows) == expected_count, f"{path.name} expected {expected_count} rows, found {len(rows)}")
    scenario_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        check(set(row) == {"messages", "expected"}, f"{path.name}:{index} has unexpected top-level fields")
        check([message.get("role") for message in row["messages"]] == ["developer", "user"], f"{path.name}:{index} must not contain an assistant answer")
        scenario = row["expected"].get("scenario")
        check(isinstance(scenario, dict), f"{path.name}:{index} is missing expected.scenario")
        check(row["messages"][0].get("content") == SYSTEM_PROMPT, f"{path.name}:{index} has a stale developer prompt")
        check(row["messages"][1].get("content") == scenario_message(scenario), f"{path.name}:{index} scenario/prompt mismatch")
        scenario_id = scenario.get("scenario_id")
        check(isinstance(scenario_id, str) and scenario_id not in scenario_ids, f"{path.name}:{index} has a duplicate or invalid scenario_id")
        scenario_ids.add(scenario_id)
    return rows, scenario_ids


def main() -> int:
    load_dotenv(override=True)
    check(os.getenv("RFT_MODEL", "o4-mini") == "o4-mini", "RFT_MODEL must be o4-mini")
    check(int(os.getenv("RFT_N_EPOCHS", "2")) == 2, "first RFT run must use 2 epochs")
    check(os.getenv("RFT_REASONING_EFFORT", "medium") == "medium", "first RFT run must use medium reasoning effort")
    check(int(os.getenv("RFT_COMPUTE_MULTIPLIER", "2")) == 2, "first RFT run must use compute multiplier 2")
    check(float(os.getenv("RFT_LEARNING_RATE_MULTIPLIER", "1.0")) == 1.0, "first RFT run must use learning rate multiplier 1.0")
    check(int(os.getenv("RFT_EVAL_INTERVAL", "5")) == 5, "first RFT run must evaluate every 5 steps")
    check(int(os.getenv("RFT_EVAL_SAMPLES", "10")) == 10, "first RFT run must use 10 validation samples per evaluation")

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    check(urlparse(endpoint).hostname is not None, "AZURE_OPENAI_ENDPOINT is missing or invalid")
    check(os.environ.get("AZURE_AI_ACCOUNT") is not None, "AZURE_AI_ACCOUNT is missing")

    gate = json.loads(PILOT_GATE.read_text(encoding="utf-8"))
    check(gate.get("passed") is True, "pilot gate is not passing")
    check("Raw o4-mini is deprecated" in " ".join(gate.get("limitations", [])), "raw o4-mini limitation is not recorded")

    checked_in_grader = json.loads(GRADER.read_text(encoding="utf-8"))
    check(checked_in_grader == grader_definition(), "grader.json is stale relative to common/scoring.py")

    train_rows, train_ids = audit_dataset(DATA / "rft_train.jsonl", 300)
    valid_rows, valid_ids = audit_dataset(DATA / "rft_valid.jsonl", 60)
    check(train_ids.isdisjoint(valid_ids), "RFT train and validation scenarios overlap")
    evaluation_ids = {scenario["scenario_id"] for scenario in generate_split(50_000, 150, ("tight", "mixed", "loose"))}
    check(train_ids.isdisjoint(evaluation_ids) and valid_ids.isdisjoint(evaluation_ids), "training data overlaps held-out evaluation scenarios")

    check('"warehouse_id":"W1"' not in SYSTEM_PROMPT and '"sku":"A"' not in SYSTEM_PROMPT, "developer prompt contains literal warehouse or SKU examples")
    scenario = generate_scenario(7)
    check(score_plan(defer_all(scenario), scenario)["score"] == 0.0, "all-defer shortcut must score zero")
    invalid = defer_all(scenario)
    invalid["decisions"][0]["ignored"] = True
    check(score_plan(invalid, scenario)["score"] == 0.0, "invalid plans must score zero")
    check(score_plan(greedy_plan(scenario, "priority"), scenario)["feasible"], "adaptive reference plan must remain feasible")

    captured = load_jsonl(CAPTURE)
    feasible_scores = [
        result["score"]
        for row in captured
        if (result := score_plan(row["teacher"]["plan"], row["scenario"]))["feasible"]
    ]
    check(len(set(feasible_scores)) >= 50, "feasible reward signal is not sufficiently continuous")
    check(max(feasible_scores) - min(feasible_scores) >= 0.25, "feasible reward range is too narrow")

    report = {
        "passed": True,
        "endpoint_host": urlparse(endpoint).hostname,
        "azure_ai_account": os.environ["AZURE_AI_ACCOUNT"],
        "rft": {
            "model": "o4-mini",
            "epochs": 2,
            "reasoning_effort": "medium",
            "compute_multiplier": 2,
            "learning_rate_multiplier": 1.0,
            "eval_interval": 5,
            "eval_samples": 10,
            "train_rows": len(train_rows),
            "valid_rows": len(valid_rows),
        },
        "reward": {
            "infeasible_score": 0.0,
            "all_defer_score": 0.0,
            "distinct_feasible_scores": len(set(feasible_scores)),
            "feasible_score_range": [min(feasible_scores), max(feasible_scores)],
        },
        "artifacts": {
            "rft_train_sha256": sha256(DATA / "rft_train.jsonl"),
            "rft_valid_sha256": sha256(DATA / "rft_valid.jsonl"),
            "grader_sha256": sha256(GRADER),
        },
        "limitations": gate["limitations"],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())