import json
from typing import Any

SYSTEM_PROMPT = """You are a disruption-recovery planner. Return JSON only.
Return exactly {"decisions":[...]}. Include every order exactly once.
A defer decision is {"order_id":"...","action":"defer"}.
A ship decision is {"order_id":"<order_id>","action":"ship","warehouse_id":"<warehouse_id>","sku":"<sku>","quantity":<quantity>,"shipping_mode":"<standard_or_expedite>"}.
Use only available warehouses, requested or approved substitute SKUs, exact order quantities, and standard/expedite modes.

Business rules:
- An order is on time when the selected shipping mode's delivery hours do not exceed the order's deadline hours.
- On-time delivery earns full service value and margin. Late delivery has reduced business value, so prioritize on-time delivery for higher-priority orders.
- An approved substitute SKU may be used when necessary, but it retains slightly less value than the requested SKU.
- Partial shipments are not allowed. A shipped order must use its exact requested quantity.
- Shipped quantity consumes both SKU inventory and warehouse shipment capacity.
- Expedite spending is expedited unit cost multiplied by shipped quantity and must remain within the scenario's expedite budget.
- Deferring an order earns no service or margin, but may be necessary to keep the overall plan feasible.
- Using an unavailable warehouse, exceeding inventory or capacity, using a prohibited substitute, shipping an incorrect quantity, or exceeding the expedite budget invalidates the entire plan.
- Among feasible plans, prioritize on-time service, then retained margin, while avoiding unnecessary shipping cost.

Produce the best feasible plan after checking all inventory, capacity, delivery-time, substitution, quantity, and budget constraints across the complete set of decisions."""


def scenario_message(scenario: dict[str, Any]) -> str:
    return "Produce the best feasible allocation plan for this scenario:\n" + json.dumps(scenario, separators=(",", ":"), sort_keys=True)