from __future__ import annotations

import random
from typing import Any

SKUS = ("A", "A2", "B", "B2", "C", "D")
SUBSTITUTES = {"A": "A2", "A2": "A", "B": "B2", "B2": "B", "C": None, "D": None}


def generate_scenario(seed: int, family: str = "mixed") -> dict[str, Any]:
    rng = random.Random(seed)
    warehouses = []
    disrupted_index = seed % 3
    for index in range(3):
        warehouses.append(
            {
                "warehouse_id": f"W{index + 1}",
                "available": index != disrupted_index,
                "inventory": {sku: rng.randint(3, 12) for sku in SKUS},
                "shipment_capacity": rng.randint(15, 24),
                "standard_hours": rng.choice((18, 24, 30, 36)),
                "standard_cost": rng.randint(4, 9),
                "expedite_hours": rng.choice((8, 12, 16)),
                "expedite_cost": rng.randint(11, 19),
            }
        )

    order_count = rng.randint(12, 16)
    pressure = {"loose": 0.75, "mixed": 1.0, "tight": 1.25}[family]
    orders = []
    for index in range(order_count):
        sku = rng.choice(("A", "B", "C", "D"))
        quantity = rng.choice((1, 1, 2, 2, 3))
        orders.append(
            {
                "order_id": f"O{seed:05d}-{index + 1:02d}",
                "sku": sku,
                "quantity": quantity,
                "priority": rng.choice((1, 1, 2, 2, 3)),
                "deadline_hours": rng.choice((12, 18, 24, 30, 36)),
                "substitute_sku": SUBSTITUTES[sku],
                "margin": rng.randint(35, 130),
            }
        )

    active_capacity = sum(w["shipment_capacity"] for w in warehouses if w["available"])
    return {
        "scenario_id": f"{family}-{seed:05d}",
        "family": family,
        "orders": orders,
        "warehouses": warehouses,
        "expedite_budget": max(45, int(active_capacity * 5 / pressure)),
    }


def generate_split(start_seed: int, count: int, families: tuple[str, ...] = ("loose", "mixed", "tight")) -> list[dict[str, Any]]:
    return [generate_scenario(start_seed + index, families[index % len(families)]) for index in range(count)]