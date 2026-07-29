from __future__ import annotations

from common.scoring import score_plan
from grader_mcp.server import assess_supply_chain_plan


SCENARIO = {
    "scenario_id": "mcp-test",
    "family": "test",
    "expedite_budget": 0,
    "orders": [
        {
            "order_id": "O1",
            "sku": "A",
            "quantity": 1,
            "priority": 1,
            "deadline_hours": 24,
            "substitute_sku": None,
            "margin": 100,
        }
    ],
    "warehouses": [
        {
            "warehouse_id": "W1",
            "available": True,
            "inventory": {"A": 1},
            "shipment_capacity": 1,
            "standard_hours": 12,
            "standard_cost": 5,
            "expedite_hours": 6,
            "expedite_cost": 10,
        }
    ],
}

PLAN = {
    "decisions": [
        {
            "order_id": "O1",
            "action": "ship",
            "warehouse_id": "W1",
            "sku": "A",
            "quantity": 1,
            "shipping_mode": "standard",
        }
    ]
}


def test_assessment_matches_authoritative_scorer_for_object() -> None:
    assessment = assess_supply_chain_plan(SCENARIO, PLAN)
    authoritative = score_plan(PLAN, SCENARIO)
    assert {key: assessment[key] for key in authoritative} == authoritative
    assert assessment["report"]["decision_rows"][0] == {
        "order_id": "O1",
        "decision": "Standard",
        "warehouse": "W1",
        "sku": "A",
        "quantity": 1,
        "delivery_hours": 12,
        "on_time": True,
        "shipping_cost": 5,
    }
    assert "### Quality breakdown" in assessment["report"]["markdown"]


def test_assessment_matches_authoritative_scorer_for_json_string() -> None:
    import json

    assessment = assess_supply_chain_plan(SCENARIO, json.dumps(PLAN))
    authoritative = score_plan(PLAN, SCENARIO)
    assert {key: assessment[key] for key in authoritative} == authoritative


def test_invalid_model_output_uses_scorer_failure_contract() -> None:
    assessment = assess_supply_chain_plan(SCENARIO, "not json")
    assert {key: assessment[key] for key in ("score", "feasible", "reason", "category", "metrics")} == {
        "score": 0.0,
        "feasible": False,
        "reason": "plan must contain only a decisions array",
        "category": "schema",
        "metrics": {},
    }
    assert assessment["report"]["decision_rows"] == []


def test_report_includes_supplied_execution_metadata() -> None:
    assessment = assess_supply_chain_plan(
        SCENARIO,
        PLAN,
        {
            "latency_seconds": 3.25,
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    )
    assert assessment["report"]["execution_metadata"] == {
        "latency_seconds": 3.25,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    }