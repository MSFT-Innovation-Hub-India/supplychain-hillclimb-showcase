import json
from typing import Any

SYSTEM_PROMPT = """You are a disruption-recovery planner. Return JSON only.
Return exactly {"decisions":[...]}. Include every order exactly once.
A defer decision is {"order_id":"...","action":"defer"}.
A ship decision is {"order_id":"<order_id>","action":"ship","warehouse_id":"<warehouse_id>","sku":"<sku>","quantity":<quantity>,"shipping_mode":"<standard_or_expedite>"}.
Use only available warehouses, requested or approved substitute SKUs, exact order quantities, and standard/expedite modes. Respect inventory, shipment capacity, deadlines, and the expedite budget. Maximize priority-weighted on-time service and retained margin while controlling shipping cost."""


def scenario_message(scenario: dict[str, Any]) -> str:
    return "Produce the best feasible allocation plan for this scenario:\n" + json.dumps(scenario, separators=(",", ":"), sort_keys=True)