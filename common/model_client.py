from __future__ import annotations

import json
import os
import time
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import OpenAI

from common.prompts import SYSTEM_PROMPT, scenario_message


def create_client() -> OpenAI:
    load_dotenv(override=True)
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    if not endpoint.endswith("/openai/v1"):
        endpoint += "/openai/v1"
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(process_timeout=20), "https://ai.azure.com/.default"
    )
    return OpenAI(base_url=endpoint, api_key=token_provider, timeout=180.0, max_retries=2)


def request_plan(client: OpenAI, deployment: str, scenario: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, int | float]]:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario_message(scenario)},
        ],
        response_format={"type": "json_object"},
    )
    latency_seconds = time.perf_counter() - started
    usage = response.usage
    try:
        plan = json.loads(response.choices[0].message.content or "")
    except json.JSONDecodeError:
        plan = None
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    prompt_details = usage.prompt_tokens_details if usage else None
    completion_details = usage.completion_tokens_details if usage else None
    cached_input_tokens = prompt_details.cached_tokens if prompt_details and prompt_details.cached_tokens else 0
    reasoning_tokens = completion_details.reasoning_tokens if completion_details and completion_details.reasoning_tokens else 0
    return plan, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "input_tokens": prompt_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "visible_output_tokens": max(0, completion_tokens - reasoning_tokens),
        "total_tokens": usage.total_tokens if usage else prompt_tokens + completion_tokens,
        "latency_seconds": round(latency_seconds, 6),
    }