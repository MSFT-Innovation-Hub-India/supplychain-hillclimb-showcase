"""Submit the supervised fine-tuning job and optionally poll for completion."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.fine_tuning_api import FineTuningClient, require_paid_confirmation, require_pilot_gate

DATA = ROOT / "02_dataset_build" / "data"


def main(confirm_paid: bool, no_poll: bool) -> None:
    require_paid_confirmation(confirm_paid)
    require_pilot_gate(ROOT)
    client = FineTuningClient()
    model = os.environ.get("SFT_MODEL", "gpt-4.1-mini")
    suffix = os.environ.get("SFT_SUFFIX", "allocation-sft-v2")
    client.require_no_active_job(model, suffix, "supervised")
    train_id = client.upload(DATA / "sft_train.jsonl")
    valid_id = client.upload(DATA / "sft_valid.jsonl")
    body = {
        "model": model,
        "training_file": train_id, "validation_file": valid_id,
        "method": {"type": "supervised", "supervised": {"hyperparameters": {
            "n_epochs": int(os.environ.get("SFT_N_EPOCHS", "3"))
        }}},
        "suffix": suffix, "seed": 42,
        "trainingType": os.environ.get("SFT_TRAINING_TYPE", "GlobalStandard"),
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