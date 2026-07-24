from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _failure(reason: str, category: str) -> dict[str, Any]:
    return {"score": 0.0, "feasible": False, "reason": reason, "category": category, "metrics": {}}


def score_plan(plan: Any, scenario: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != {"decisions"} or not isinstance(plan["decisions"], list):
        return _failure("plan must contain only a decisions array", "schema")

    orders = {order["order_id"]: order for order in scenario["orders"]}
    warehouses = {warehouse["warehouse_id"]: warehouse for warehouse in scenario["warehouses"]}
    decision_ids = [decision.get("order_id") for decision in plan["decisions"] if isinstance(decision, dict)]
    if (
        len(decision_ids) != len(plan["decisions"])
        or any(not isinstance(order_id, str) for order_id in decision_ids)
        or Counter(decision_ids) != Counter(orders.keys())
    ):
        return _failure("every order must appear exactly once", "coverage")

    inventory_used: dict[tuple[str, str], int] = defaultdict(int)
    capacity_used: dict[str, int] = defaultdict(int)
    expedite_spend = 0.0
    shipping_cost = 0.0
    service_earned = 0.0
    margin_earned = 0.0
    shipped_orders = 0

    for decision in plan["decisions"]:
        order = orders[decision["order_id"]]
        action = decision.get("action")
        if action == "defer":
            if set(decision) != {"order_id", "action"}:
                return _failure("defer decisions cannot contain ignored fields", "schema")
            continue
        if action != "ship" or set(decision) != {"order_id", "action", "warehouse_id", "sku", "quantity", "shipping_mode"}:
            return _failure("ship decision has invalid fields", "schema")
        if (
            not isinstance(decision["warehouse_id"], str)
            or not isinstance(decision["sku"], str)
            or not isinstance(decision["shipping_mode"], str)
            or not isinstance(decision["quantity"], int)
            or isinstance(decision["quantity"], bool)
        ):
            return _failure("ship decision has invalid field types", "schema")

        warehouse = warehouses.get(decision["warehouse_id"])
        if warehouse is None or not warehouse["available"]:
            return _failure("unknown or disrupted warehouse", "warehouse")
        if decision["quantity"] != order["quantity"] or decision["quantity"] <= 0:
            return _failure("shipped quantity must exactly match the order", "quantity")
        allowed_skus = {order["sku"]}
        if order["substitute_sku"]:
            allowed_skus.add(order["substitute_sku"])
        if decision["sku"] not in allowed_skus:
            return _failure("prohibited substitution", "substitution")
        if decision["shipping_mode"] not in {"standard", "expedite"}:
            return _failure("invalid shipping mode", "schema")

        quantity = decision["quantity"]
        inventory_used[(warehouse["warehouse_id"], decision["sku"])] += quantity
        capacity_used[warehouse["warehouse_id"]] += quantity
        unit_cost = warehouse[f"{decision['shipping_mode']}_cost"]
        shipping_cost += unit_cost * quantity
        if decision["shipping_mode"] == "expedite":
            expedite_spend += unit_cost * quantity
        delivered_on_time = warehouse[f"{decision['shipping_mode']}_hours"] <= order["deadline_hours"]
        if delivered_on_time:
            service_earned += order["priority"]
        retention = 0.90 if decision["sku"] != order["sku"] else 1.0
        if not delivered_on_time:
            retention *= 0.50
        margin_earned += order["margin"] * retention
        shipped_orders += 1

    for (warehouse_id, sku), quantity in inventory_used.items():
        if quantity > warehouses[warehouse_id]["inventory"].get(sku, 0):
            return _failure("inventory exceeded", "inventory")
    for warehouse_id, quantity in capacity_used.items():
        if quantity > warehouses[warehouse_id]["shipment_capacity"]:
            return _failure("warehouse shipment capacity exceeded", "capacity")
    if expedite_spend > scenario["expedite_budget"]:
        return _failure("expedite budget exceeded", "budget")

    total_priority = sum(order["priority"] for order in orders.values())
    total_margin = sum(order["margin"] for order in orders.values())
    service = service_earned / total_priority
    margin = margin_earned / total_margin
    fulfilled_fraction = shipped_orders / len(orders)
    reference_cost = max(1.0, sum(order["quantity"] for order in orders.values()) * 15.0)
    cost = fulfilled_fraction * max(0.0, 1.0 - shipping_cost / reference_cost)
    score = 0.55 * service + 0.25 * margin + 0.20 * cost
    return {
        "score": round(score, 6),
        "feasible": True,
        "reason": "feasible plan",
        "category": "feasible",
        "metrics": {
            "service": round(service, 6),
            "margin": round(margin, 6),
            "cost": round(cost, 6),
            "shipping_cost": round(shipping_cost, 2),
            "expedite_spend": round(expedite_spend, 2),
            "shipped_orders": shipped_orders,
        },
    }