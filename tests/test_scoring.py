from common.scenario import generate_scenario
from common.scoring import score_plan
from common.baselines import greedy_plan


def defer_all(scenario):
    return {"decisions": [{"order_id": order["order_id"], "action": "defer"} for order in scenario["orders"]]}


def test_defer_all_is_feasible_but_not_competitive():
    scenario = generate_scenario(7)
    result = score_plan(defer_all(scenario), scenario)
    assert result["feasible"]
    assert result["score"] == 0.0


def test_missing_order_is_rejected():
    scenario = generate_scenario(7)
    plan = defer_all(scenario)
    plan["decisions"].pop()
    assert score_plan(plan, scenario)["category"] == "coverage"


def test_disrupted_warehouse_is_rejected():
    scenario = generate_scenario(7)
    plan = defer_all(scenario)
    order = scenario["orders"][0]
    warehouse = next(item for item in scenario["warehouses"] if not item["available"])
    plan["decisions"][0] = {"order_id": order["order_id"], "action": "ship", "warehouse_id": warehouse["warehouse_id"], "sku": order["sku"], "quantity": order["quantity"], "shipping_mode": "standard"}
    result = score_plan(plan, scenario)
    assert result["category"] == "warehouse"
    assert result["score"] == 0.0


def test_ignored_fields_are_rejected():
    scenario = generate_scenario(7)
    plan = defer_all(scenario)
    plan["decisions"][0]["comment"] = "reward hack"
    assert score_plan(plan, scenario)["category"] == "schema"


def test_unhashable_and_boolean_fields_are_rejected_without_raising():
    scenario = generate_scenario(7)
    plan = defer_all(scenario)
    plan["decisions"][0]["order_id"] = []
    assert score_plan(plan, scenario)["category"] == "coverage"

    plan = defer_all(scenario)
    order = scenario["orders"][0]
    warehouse = next(item for item in scenario["warehouses"] if item["available"])
    plan["decisions"][0] = {
        "order_id": order["order_id"], "action": "ship", "warehouse_id": warehouse["warehouse_id"],
        "sku": order["sku"], "quantity": True, "shipping_mode": "standard",
    }
    assert score_plan(plan, scenario)["category"] == "schema"


def test_adaptive_baselines_are_feasible_and_diverse():
    distinct_high_quality = 0
    for seed in range(50):
        scenario = generate_scenario(10_000 + seed, ("loose", "mixed", "tight")[seed % 3])
        priority = greedy_plan(scenario, "priority")
        margin = greedy_plan(scenario, "margin")
        priority_result = score_plan(priority, scenario)
        margin_result = score_plan(margin, scenario)
        assert priority_result["feasible"] and margin_result["feasible"]
        distinct_high_quality += priority != margin and priority_result["score"] >= 0.85 and margin_result["score"] >= 0.85
    assert distinct_high_quality >= 5


def test_every_infeasible_category_receives_zero_reward():
    scenario = generate_scenario(7)
    order = scenario["orders"][0]
    warehouse = next(item for item in scenario["warehouses"] if item["available"])
    invalid_decisions = [
        {"order_id": order["order_id"], "action": "ship", "warehouse_id": warehouse["warehouse_id"], "sku": "INVALID", "quantity": order["quantity"], "shipping_mode": "standard"},
        {"order_id": order["order_id"], "action": "ship", "warehouse_id": warehouse["warehouse_id"], "sku": order["sku"], "quantity": order["quantity"] + 1, "shipping_mode": "standard"},
    ]
    for invalid_decision in invalid_decisions:
        plan = defer_all(scenario)
        plan["decisions"][0] = invalid_decision
        result = score_plan(plan, scenario)
        assert not result["feasible"]
        assert result["score"] == 0.0