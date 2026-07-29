"""Foundry prompt-agent client used only by the model comparison app."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from common.prompts import scenario_message


def create_project_client(endpoint: str | None = None) -> AIProjectClient:
    """Create a Foundry project client using the current workload identity."""
    project_endpoint = (endpoint or os.environ["AZURE_AI_PROJECT_ENDPOINT"]).rstrip("/")
    return AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(process_timeout=20),
    )


def request_agent_plan(
    project_client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    scenario: dict[str, Any],
    extra_instructions: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, int | float]]:
    """Request and parse a plan from a pinned Foundry prompt-agent version."""
    started = time.perf_counter()
    message = scenario_message(scenario)
    if extra_instructions:
        message = f"{extra_instructions.strip()}\n\n{message}"
    response = project_client.get_openai_client().responses.create(
        input=[{"role": "user", "content": message}],
        extra_body={
            "agent_reference": {
                "name": agent_name,
                "version": agent_version,
                "type": "agent_reference",
            }
        },
    )
    latency_seconds = time.perf_counter() - started

    try:
        plan = json.loads(response.output_text or "")
    except json.JSONDecodeError:
        plan = None

    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    output_details = getattr(usage, "output_tokens_details", None) if usage else None
    reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) if output_details else 0
    return plan, {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "input_tokens": input_tokens,
        "cached_input_tokens": 0,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "visible_output_tokens": max(0, output_tokens - reasoning_tokens),
        "total_tokens": getattr(usage, "total_tokens", input_tokens + output_tokens) if usage else 0,
        "latency_seconds": round(latency_seconds, 6),
    }