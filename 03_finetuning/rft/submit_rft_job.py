from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.fine_tuning_api import FineTuningClient, require_paid_confirmation, require_pilot_gate
from pre_submit_audit import main as run_pre_submit_audit

DATA = ROOT / "02_dataset_build" / "data"
GRADER = Path(__file__).resolve().parent / "grader.json"

PLAN_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "allocation_plan",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"}, "action": {"type": "string", "enum": ["ship", "defer"]},
                            "warehouse_id": {"type": "string"}, "sku": {"type": "string"},
                            "quantity": {"type": "integer"}, "shipping_mode": {"type": "string", "enum": ["standard", "expedite"]},
                        },
                        "required": ["order_id", "action"], "additionalProperties": False,
                    },
                }
            },
            "required": ["decisions"], "additionalProperties": False,
        },
    },
}


def main(confirm_paid: bool, no_poll: bool) -> None:
    require_paid_confirmation(confirm_paid)
    require_pilot_gate(ROOT)
    run_pre_submit_audit()
    client = FineTuningClient()
    model = os.environ.get("RFT_MODEL", "o4-mini")
    suffix = "allocation-rft"
    client.require_no_active_job(model, suffix, "reinforcement")
    train_id = client.upload(DATA / "rft_train.jsonl")
    valid_id = client.upload(DATA / "rft_valid.jsonl")
    body = {
        "model": model,
        "training_file": train_id, "validation_file": valid_id,
        "method": {"type": "reinforcement", "reinforcement": {
            "grader": json.loads(GRADER.read_text(encoding="utf-8")),
            "response_format": PLAN_SCHEMA,
            "hyperparameters": {
                "n_epochs": int(os.environ.get("RFT_N_EPOCHS", "2")),
                "reasoning_effort": os.environ.get("RFT_REASONING_EFFORT", "medium"),
                "compute_multiplier": int(os.environ.get("RFT_COMPUTE_MULTIPLIER", "2")),
                "learning_rate_multiplier": float(os.environ.get("RFT_LEARNING_RATE_MULTIPLIER", "1.0")),
                "eval_interval": int(os.environ.get("RFT_EVAL_INTERVAL", "5")),
                "eval_samples": int(os.environ.get("RFT_EVAL_SAMPLES", "10")),
            },
        }},
        "suffix": suffix, "seed": 42,
        "trainingType": os.environ.get("RFT_TRAINING_TYPE", "GlobalStandard"),
    }
    job = client.create_job(body)
    print(json.dumps(job, indent=2))
    if not no_poll:
        print(json.dumps(client.poll_job(job["id"]), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--no-poll", action="store_true")
    args = parser.parse_args()
    main(args.confirm_paid, args.no_poll)