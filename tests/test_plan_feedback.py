import json

from common.baselines import defer_all
from common.plan_feedback import revision_feedback
from common.scenario import generate_scenario
from common.scoring import score_plan


def feedback_diagnostics(feedback):
    payload = feedback.split("feedback: ", 1)[1].split("\n", 1)[0]
    return json.loads(payload)


def test_revision_feedback_reports_exact_inventory_and_budget_overruns():
    scenario = generate_scenario(7)
    warehouse = next(item for item in scenario["warehouses"] if item["available"])
    order = scenario["orders"][0]
    plan = defer_all(scenario)
    plan["decisions"][0] = {
        "order_id": order["order_id"],
        "action": "ship",
        "warehouse_id": warehouse["warehouse_id"],
        "sku": order["sku"],
        "quantity": warehouse["inventory"][order["sku"]] + 1,
        "shipping_mode": "expedite",
    }
    diagnostics = feedback_diagnostics(revision_feedback(plan, scenario, score_plan(plan, scenario)))
    assert diagnostics["inventory_overruns"][0]["used"] == warehouse["inventory"][order["sku"]] + 1
    assert diagnostics["inventory_overruns"][0]["available"] == warehouse["inventory"][order["sku"]]
    assert diagnostics["expedite_spend"] == warehouse["expedite_cost"] * (warehouse["inventory"][order["sku"]] + 1)


def test_revision_feedback_includes_feasible_score_metrics_for_hill_climbing():
    scenario = generate_scenario(7)
    plan = defer_all(scenario)
    diagnostics = feedback_diagnostics(revision_feedback(plan, scenario, score_plan(plan, scenario)))
    assert diagnostics["feasible"] is True
    assert diagnostics["score"] == 0.0
    assert diagnostics["inventory_overruns"] == []