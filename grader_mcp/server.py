"""Authenticated Streamable HTTP MCP server for deterministic plan assessment."""

from __future__ import annotations

import json
import os
import secrets
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from common.scoring import score_plan


def _parse_model_output(model_output: dict[str, Any] | str) -> Any:
    if not isinstance(model_output, str):
        return model_output
    try:
        return json.loads(model_output)
    except json.JSONDecodeError:
        return model_output


def _allocation_rows(plan: Any, scenario: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(plan, dict) or not isinstance(plan.get("decisions"), list):
        return []

    orders = {order["order_id"]: order for order in scenario.get("orders", [])}
    warehouses = {
        warehouse["warehouse_id"]: warehouse for warehouse in scenario.get("warehouses", [])
    }
    rows: list[dict[str, Any]] = []
    for decision in plan["decisions"]:
        if not isinstance(decision, dict):
            continue
        order_id = decision.get("order_id")
        order = orders.get(order_id)
        if decision.get("action") == "defer":
            rows.append(
                {
                    "order_id": order_id,
                    "decision": "Defer",
                    "warehouse": None,
                    "sku": None,
                    "quantity": 0,
                    "delivery_hours": None,
                    "on_time": False,
                    "shipping_cost": 0.0,
                }
            )
            continue

        warehouse = warehouses.get(decision.get("warehouse_id"))
        mode = decision.get("shipping_mode")
        quantity = decision.get("quantity")
        if not order or not warehouse or mode not in {"standard", "expedite"} or not isinstance(quantity, int):
            continue
        delivery_hours = warehouse[f"{mode}_hours"]
        shipping_cost = warehouse[f"{mode}_cost"] * quantity
        rows.append(
            {
                "order_id": order_id,
                "decision": mode.title(),
                "warehouse": warehouse["warehouse_id"],
                "sku": decision.get("sku"),
                "quantity": quantity,
                "delivery_hours": delivery_hours,
                "on_time": delivery_hours <= order["deadline_hours"],
                "shipping_cost": round(shipping_cost, 2),
            }
        )
    return rows


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows available._"
    columns = list(rows[0])
    header = "| " + " | ".join(column.replace("_", " ").title() for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join("-" if row.get(column) is None else str(row.get(column)) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _build_report(
    plan: Any,
    scenario: dict[str, Any],
    result: dict[str, Any],
    execution_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    decision_rows = _allocation_rows(plan, scenario)
    metadata = execution_metadata or {}
    latency = metadata.get("latency_seconds")
    total_tokens = metadata.get("total_tokens")
    summary_rows = [
        {"metric": "Quality score", "value": result["score"]},
        {"metric": "Constraint gate", "value": "Pass" if result["feasible"] else "Fail"},
        {"metric": "Model latency (seconds)", "value": latency if latency is not None else "Not provided"},
        {"metric": "Total tokens", "value": total_tokens if total_tokens is not None else "Not provided"},
    ]

    labels = {
        "service": "Priority-weighted on-time service",
        "margin": "Margin capture",
        "cost": "Normalized cost efficiency",
        "shipping_cost": "Total shipping cost",
        "expedite_spend": "Expedite spend",
        "shipped_orders": "Orders shipped",
    }
    metric_rows = [
        {"metric": labels.get(name, name), "value": value}
        for name, value in result["metrics"].items()
    ]

    explanations: list[str]
    if not result["feasible"]:
        explanations = [
            f"The plan failed the {result['category']} constraint: {result['reason']}.",
            "The hard-constraint gate therefore assigns zero quality, regardless of partial business value.",
        ]
    else:
        on_time_shipped = sum(row["on_time"] for row in decision_rows if row["decision"] != "Defer")
        deferred = sum(row["decision"] == "Defer" for row in decision_rows)
        metrics = result["metrics"]
        explanations = [
            "Inventory, capacity, substitution, quantity, shipping-mode, and expedite-budget checks passed.",
            f"{on_time_shipped} shipped orders arrive on time; service is priority-weighted, so its value is {metrics['service']:.1%} rather than a simple order percentage.",
            f"The plan captures {metrics['margin']:.1%} of available margin and spends ${metrics['shipping_cost']:.2f} on shipping.",
            f"Expedite spend is ${metrics['expedite_spend']:.2f} of the ${scenario['expedite_budget']:.2f} budget; {deferred} orders are deferred.",
            "Quality is computed as 55% service + 25% margin + 20% normalized cost efficiency.",
        ]

    markdown_sections = [
        "### Assessment summary",
        _markdown_table(summary_rows),
        "### Quality breakdown",
        _markdown_table(metric_rows),
        "### Allocation decisions",
        _markdown_table(decision_rows),
        "### Explanation",
        "\n".join(f"- {statement}" for statement in explanations),
    ]
    return {
        "summary_rows": summary_rows,
        "metric_rows": metric_rows,
        "decision_rows": decision_rows,
        "execution_metadata": {
            "latency_seconds": latency,
            "prompt_tokens": metadata.get("prompt_tokens"),
            "completion_tokens": metadata.get("completion_tokens"),
            "total_tokens": total_tokens,
        },
        "explanations": explanations,
        "markdown": "\n\n".join(markdown_sections),
    }


def assess_supply_chain_plan(
    scenario: dict[str, Any],
    model_output: dict[str, Any] | str,
    execution_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return authoritative scoring plus deterministic report tables and explanations."""
    plan = _parse_model_output(model_output)
    result = score_plan(plan, scenario)
    return {**result, "report": _build_report(plan, scenario, result, execution_metadata)}


allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
if configured_host := os.environ.get("GRADER_ALLOWED_HOST"):
    allowed_hosts.append(configured_host)

mcp = FastMCP(
    "Supply Chain Plan Grader",
    instructions=(
        "Use assess_supply_chain_plan after producing an allocation plan. Pass the "
        "complete original scenario and the complete model output. Treat the returned "
        "assessment as authoritative and do not recalculate its values. Present the "
        "report.markdown value verbatim when the user requests a detailed report."
    ),
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
    ),
)
mcp.tool()(assess_supply_chain_plan)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


class ApiKeyMiddleware:
    """Require the configured shared key for every MCP request."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return

        expected_key = os.environ.get("GRADER_API_KEY", "")
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        authorization = headers.get("authorization", "")
        bearer_key = authorization[7:] if authorization.lower().startswith("bearer ") else ""
        provided_key = headers.get("x-api-key") or headers.get("api-key") or bearer_key

        if not expected_key:
            response = JSONResponse({"error": "grader API key is not configured"}, status_code=503)
            await response(scope, receive, send)
            return
        if not provided_key or not secrets.compare_digest(provided_key, expected_key):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


app = mcp.streamable_http_app()
app.routes.insert(0, Route("/health", health, methods=["GET"]))
app.add_middleware(ApiKeyMiddleware)