import importlib.util
from pathlib import Path


def load_evaluation_module():
    path = Path(__file__).resolve().parents[1] / "04_evaluation" / "evaluate.py"
    spec = importlib.util.spec_from_file_location("evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_rows():
    return [
        {
            "result": {
                "score": 0.8,
                "feasible": True,
                "category": "feasible",
                "metrics": {
                    "service": 1.0,
                    "margin": 0.9,
                    "cost": 0.5,
                    "shipping_cost": 40.0,
                    "expedite_spend": 10.0,
                    "shipped_orders": 12,
                },
            },
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "output_tokens": 50,
                "reasoning_tokens": 30,
                "visible_output_tokens": 20,
                "total_tokens": 150,
                "latency_seconds": 2.0,
            },
        },
        {
            "result": {"score": 0.0, "feasible": False, "category": "schema", "metrics": {}},
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 0,
                "output_tokens": 40,
                "reasoning_tokens": 10,
                "visible_output_tokens": 30,
                "total_tokens": 140,
                "latency_seconds": 4.0,
            },
        },
    ]


def test_quality_summary_counts_failures_and_scores_failed_scenarios_as_zero():
    evaluation = load_evaluation_module()
    quality = evaluation.summarize_quality(sample_rows())
    assert quality["mean_score"] == 0.4
    assert quality["feasible_rate"] == 0.5
    assert quality["mean_service"] == 0.5
    assert quality["mean_shipping_cost_feasible"] == 40.0
    assert quality["failure_category_counts"] == {"schema": 1}


def test_inference_summary_does_not_double_bill_reasoning_tokens():
    evaluation = load_evaluation_module()
    rates = evaluation.parse_pricing(["rft=1,2,0.5"])["rft"]
    inference = evaluation.summarize_inference(sample_rows(), rates)
    assert inference["totals"]["output_tokens"] == 90
    assert inference["totals"]["reasoning_tokens"] == 40
    assert inference["latency_seconds"]["p50"] == 3.0
    assert inference["latency_seconds"]["p95"] == 3.9
    assert abs(inference["cost"]["estimated_total_usd"] - 0.00037) < 1e-12


def test_old_usage_rows_are_supported_but_marked_incomplete():
    evaluation = load_evaluation_module()
    rows = [{"usage": {"prompt_tokens": 10, "completion_tokens": 20}}]
    inference = evaluation.summarize_inference(rows, None)
    assert inference["totals"]["input_tokens"] == 10
    assert inference["totals"]["output_tokens"] == 20
    assert inference["telemetry_complete"] is False
    assert inference["latency_seconds"]["p50"] is None


def test_reasoning_parser_accepts_explicit_per_arm_effort():
    evaluation = load_evaluation_module()
    assert evaluation.parse_reasoning(["teacher_high=high", "rft=medium"]) == {
        "teacher_high": "high",
        "rft": "medium",
    }


def test_reasoning_parser_rejects_unknown_effort():
    evaluation = load_evaluation_module()
    try:
        evaluation.parse_reasoning(["teacher=default"])
    except ValueError as error:
        assert "reasoning effort" in str(error)
    else:
        raise AssertionError("unknown reasoning effort was accepted")


def test_prompt_package_parser_distinguishes_teacher_and_fine_tuned_contracts():
    evaluation = load_evaluation_module()
    assert evaluation.parse_prompt_packages(
        ["teacher=teacher", "sft=detailed-fine-tuned", "rft=thin-fine-tuned"]
    ) == {
        "teacher": "teacher",
        "sft": "detailed-fine-tuned",
        "rft": "thin-fine-tuned",
    }