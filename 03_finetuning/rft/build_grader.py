"""Build the Foundry RFT grader artifact from the canonical local scorer."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.scoring import _failure, score_plan

OUTPUT = Path(__file__).resolve().parent / "grader.json"


def grader_source() -> str:
    scoring_source = "\n\n".join((inspect.getsource(_failure), inspect.getsource(score_plan)))
    return f"""import json
from collections import Counter, defaultdict
from typing import Any

{scoring_source}

def grade(sample, item):
    try:
        plan = sample.get('output_json') or json.loads(sample.get('output_text', ''))
        scenario = item['expected']['scenario']
        return float(score_plan(plan, scenario)['score'])
    except Exception:
        return 0.0
"""


def grader_definition() -> dict:
    return {"type": "python", "name": "supply-chain-allocation-grader", "source": grader_source()}


def main() -> None:
    OUTPUT.write_text(json.dumps(grader_definition(), indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()