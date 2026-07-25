from common.prompts import SYSTEM_PROMPT, scenario_message
from common.scenario import generate_scenario


def test_system_prompt_matches_the_scoring_and_feasibility_contract():
    required_contract = (
        "score = 0.55 * service + 0.25 * margin + 0.20 * cost_efficiency",
        "inventory by (warehouse, SKU)",
        "capacity by warehouse",
        "total expedite spend",
        "Hill-climb the complete plan",
        "Every input order_id must occur exactly once",
        "one violation makes the entire plan score zero",
    )
    assert all(requirement in SYSTEM_PROMPT for requirement in required_contract)


def test_scenario_message_is_deterministic_and_contains_the_complete_scenario():
    scenario = generate_scenario(123, "tight")
    message = scenario_message(scenario)
    assert message == scenario_message(scenario)
    assert scenario["scenario_id"] in message
    assert all(order["order_id"] in message for order in scenario["orders"])