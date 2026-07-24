from __future__ import annotations

from copy import deepcopy
from typing import Any


def defer_all(scenario: dict[str, Any]) -> dict[str, Any]:
    return {"decisions": [{"order_id": order["order_id"], "action": "defer"} for order in scenario["orders"]]}


def greedy_plan(scenario: dict[str, Any], variant: str = "priority") -> dict[str, Any]:
    inventory = {w["warehouse_id"]: deepcopy(w["inventory"]) for w in scenario["warehouses"]}
    capacity = {w["warehouse_id"]: w["shipment_capacity"] for w in scenario["warehouses"]}
    warehouses = [w for w in scenario["warehouses"] if w["available"]]
    expedite_left = scenario["expedite_budget"]
    decisions: dict[str, dict[str, Any]] = {}
    if variant == "margin":
        orders = sorted(scenario["orders"], key=lambda order: (-order["margin"], -order["priority"], order["order_id"]))
    else:
        orders = sorted(scenario["orders"], key=lambda order: (-order["priority"], order["deadline_hours"], -order["margin"]))

    for order in orders:
        candidates = []
        for warehouse in warehouses:
            for sku in (order["sku"], order["substitute_sku"]):
                if sku is None or inventory[warehouse["warehouse_id"]].get(sku, 0) < order["quantity"]:
                    continue
                if capacity[warehouse["warehouse_id"]] < order["quantity"]:
                    continue
                for mode in ("standard", "expedite"):
                    cost = warehouse[f"{mode}_cost"] * order["quantity"]
                    if mode == "expedite" and cost > expedite_left:
                        continue
                    on_time = warehouse[f"{mode}_hours"] <= order["deadline_hours"]
                    candidates.append((not on_time, sku != order["sku"], cost, warehouse["warehouse_id"], sku, mode))
        if not candidates:
            decisions[order["order_id"]] = {"order_id": order["order_id"], "action": "defer"}
            continue
        _, _, cost, warehouse_id, sku, mode = min(candidates)
        inventory[warehouse_id][sku] -= order["quantity"]
        capacity[warehouse_id] -= order["quantity"]
        if mode == "expedite":
            expedite_left -= cost
        decisions[order["order_id"]] = {
            "order_id": order["order_id"], "action": "ship", "warehouse_id": warehouse_id,
            "sku": sku, "quantity": order["quantity"], "shipping_mode": mode,
        }
    return {"decisions": [decisions[order["order_id"]] for order in scenario["orders"]]}