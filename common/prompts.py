"""Model instructions and scenario-message serialization."""

import json
from typing import Any

FINE_TUNED_SYSTEM_PROMPT = """You are a disruption-recovery planner. Return JSON only.
Return exactly {"decisions":[...]}. Include every order exactly once.
A defer decision is {"order_id":"...","action":"defer"}.
A ship decision is {"order_id":"<order_id>","action":"ship","warehouse_id":"<warehouse_id>","sku":"<sku>","quantity":<quantity>,"shipping_mode":"<standard_or_expedite>"}.
Use only available warehouses, requested or approved substitute SKUs, exact order quantities, and standard/expedite modes. Respect inventory, shipment capacity, deadlines, and the expedite budget. Maximize priority-weighted on-time service and retained margin while controlling shipping cost."""

DETAILED_FINE_TUNING_SYSTEM_PROMPT = """You are a disruption-recovery planner. Return JSON only.
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

TEACHER_SYSTEM_PROMPT = """You are a disruption-recovery planner. Return JSON only.
Return exactly {"decisions":[...]}. Include every order exactly once.
A defer decision is {"order_id":"...","action":"defer"}.
A ship decision is {"order_id":"<order_id>","action":"ship","warehouse_id":"<warehouse_id>","sku":"<sku>","quantity":<quantity>,"shipping_mode":"<standard_or_expedite>"}.
Do all planning and verification internally. The response must contain no analysis, markdown, comments, totals, or fields beyond the required JSON.

Hard constraints (one violation makes the entire plan score zero):
- Use only warehouses whose available value is true.
- For each warehouse and SKU, total shipped quantity cannot exceed that warehouse's inventory for that exact SKU. Requested and substitute SKU inventory are separate pools.
- For each warehouse, total shipped quantity across all SKUs cannot exceed shipment_capacity.
- A ship decision must use the order's requested SKU or its non-null substitute_sku and exactly the order's quantity. Partial or split shipments are forbidden.
- shipping_mode must be standard or expedite.
- Total expedite spend is the sum of expedite_cost * quantity for every expedited decision and cannot exceed expedite_budget. Standard shipping does not consume this budget.
- Every input order_id must occur exactly once. A defer decision must contain only order_id and action; a ship decision must contain exactly the six documented fields.

Exact objective among feasible complete plans:
- An order is on time when the selected mode's warehouse delivery hours are <= deadline_hours.
- service = sum(priority for on-time shipped orders) / sum(priority for all orders).
- Each shipped order contributes margin * retention, where retention is 1.0 for the requested SKU or 0.90 for a substitute, multiplied by 0.50 if late. margin = retained margin / total order margin.
- shipping_cost = sum(selected mode unit cost * quantity). fulfilled_fraction = shipped order count / total order count. reference_cost = sum(all order quantities) * 15. cost_efficiency = fulfilled_fraction * max(0, 1 - shipping_cost / reference_cost).
- Maximize score = 0.55 * service + 0.25 * margin + 0.20 * cost_efficiency. Do not treat the objectives as lexicographic: use these weights.

Required internal planning procedure:
1. Enumerate each order's legal warehouse, SKU, and mode options. Mark whether each option is on time and calculate its shipping cost, expedite spend, service contribution, and margin retention. Defer is always the safe fallback.
2. Start from an all-defer feasible plan. Add high-value on-time shipments while maintaining running ledgers for inventory by (warehouse, SKU), capacity by warehouse, and total expedite spend.
3. Protect scarce inventory, capacity, and expedite budget for orders with fewer on-time options. Prefer standard over expedite only when the weighted score is not reduced; a late shipment may still add margin and cost-efficiency value.
4. Hill-climb the complete plan: try reassignments, requested/substitute swaps, mode changes, additions, removals, and exchanges between orders. Keep a change only when all ledgers remain feasible and the exact weighted score improves. Compare marginal weighted value rather than priority or margin alone.
5. Before responding, independently recompute all three ledgers from the final decisions, recompute expedite spend, verify exact order coverage and field sets, and replace any decision that cannot be proven feasible with defer.

Return only the audited best feasible plan."""

# Backward-compatible name for callers that intentionally use the teacher package.
SYSTEM_PROMPT = TEACHER_SYSTEM_PROMPT


def scenario_message(scenario: dict[str, Any]) -> str:
    """Serialize a scenario into the user message expected by the model."""
    return "Produce the best feasible allocation plan for this scenario:\n" + json.dumps(scenario, separators=(",", ":"), sort_keys=True)