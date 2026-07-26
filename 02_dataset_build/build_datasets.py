"""Transform captured teacher traces into deterministic SFT and RFT datasets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.prompts import SYSTEM_PROMPT, scenario_message

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "01_baseline_teacher" / "traces" / "training.jsonl"
OUTPUT = Path(__file__).resolve().parent / "data"


def rft_row(row: dict) -> dict:
    return {
        "messages": [
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario_message(row["scenario"])},
        ],
        "expected": {"scenario": row["scenario"]},
    }


def sft_row(row: dict) -> dict:
    return {
        "messages": [
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario_message(row["scenario"])},
            {"role": "assistant", "content": json.dumps(row["teacher"]["plan"], separators=(",", ":"))},
        ]
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row) + "\n")


def main() -> None:
    rows = [json.loads(line) for line in INPUT.open(encoding="utf-8")]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for split in ("train", "valid"):
        split_rows = [row for row in rows if row["split"] == split]
        rft_rows = [rft_row(row) for row in split_rows]
        sft_rows = [sft_row(row) for row in split_rows if row["sft_usable"]]
        write_jsonl(OUTPUT / f"rft_{split}.jsonl", rft_rows)
        write_jsonl(OUTPUT / f"sft_{split}.jsonl", sft_rows)
        print(f"{split}: RFT={len(rft_rows)}, SFT={len(sft_rows)}, SFT dropped={len(rft_rows) - len(sft_rows)}")


if __name__ == "__main__":
    main()