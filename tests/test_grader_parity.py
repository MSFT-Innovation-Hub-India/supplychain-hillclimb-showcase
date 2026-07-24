import json

from common.baselines import defer_all, greedy_plan
from common.scenario import generate_scenario
from common.scoring import score_plan
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_builder():
    path = Path(__file__).resolve().parents[1] / "03_finetuning" / "rft" / "build_grader.py"
    spec = spec_from_file_location("build_grader", path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_embedded_grader_matches_local_scorer():
    builder = load_builder()
    namespace = {}
    exec(builder.grader_source(), namespace)
    for seed in range(10):
        scenario = generate_scenario(seed)
        for plan in (defer_all(scenario), greedy_plan(scenario, "priority"), greedy_plan(scenario, "margin")):
            expected = score_plan(plan, scenario)["score"]
            sample = {"output_text": json.dumps(plan)}
            assert namespace["grade"](sample, {"expected": {"scenario": scenario}}) == expected


def test_checked_in_grader_is_generated_from_current_scorer():
    builder = load_builder()
    checked_in = json.loads(builder.OUTPUT.read_text(encoding="utf-8"))
    assert checked_in == builder.grader_definition()