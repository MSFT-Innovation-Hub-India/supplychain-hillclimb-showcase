from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def revision_feedback(plan: Any, scenario: dict[str, Any], result: dict[str, Any]) -> str:
    warehouses = {warehouse["warehouse_id"]: warehouse for warehouse in scenario["warehouses"]}
    inventory_used: dict[tuple[str, str], int] = defaultdict(int)
    capacity_used: dict[str, int] = defaultdict(int)
    expedite_spend = 0

    decisions = plan.get("decisions", []) if isinstance(plan, dict) else []
    if isinstance(decisions, list):
        for decision in decisions:
            if not isinstance(decision, dict) or decision.get("action") != "ship":
                continue
            warehouse = warehouses.get(decision.get("warehouse_id"))
            quantity = decision.get("quantity")
            sku = decision.get("sku")
            if warehouse is None or not isinstance(quantity, int) or isinstance(quantity, bool) or not isinstance(sku, str):
                continue
            inventory_used[(warehouse["warehouse_id"], sku)] += quantity
            capacity_used[warehouse["warehouse_id"]] += quantity
            if decision.get("shipping_mode") == "expedite":
                expedite_spend += warehouse["expedite_cost"] * quantity

    diagnostics = {
        "score": result["score"],
        "feasible": result["feasible"],
        "failure_category": result["category"],
        "failure_reason": result["reason"],
        "inventory_overruns": [
            {
                "warehouse_id": warehouse_id,
                "sku": sku,
                "used": used,
                "available": warehouses[warehouse_id]["inventory"].get(sku, 0),
            }
            for (warehouse_id, sku), used in inventory_used.items()
            if used > warehouses[warehouse_id]["inventory"].get(sku, 0)
        ],
        "capacity_overruns": [
            {
                "warehouse_id": warehouse_id,
                "used": used,
                "available": warehouses[warehouse_id]["shipment_capacity"],
            }
            for warehouse_id, used in capacity_used.items()
            if used > warehouses[warehouse_id]["shipment_capacity"]
        ],
        "expedite_spend": expedite_spend,
        "expedite_budget": scenario["expedite_budget"],
        "metrics": result.get("metrics", {}),
    }
    return (
        "Revise the preceding plan using this deterministic validator feedback: "
        + json.dumps(diagnostics, separators=(",", ":"), sort_keys=True)
        + "\nReturn a complete replacement plan, not a patch. First eliminate every hard-constraint violation; "
        "then improve the exact weighted score without reintroducing any violation. Recompute all resource "
        "ledgers from the replacement decisions and return only the required JSON object."
    )