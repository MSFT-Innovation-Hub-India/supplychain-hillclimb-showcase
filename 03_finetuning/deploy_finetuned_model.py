"""Deploy a completed fine-tuned model to an Azure AI resource."""

from __future__ import annotations

import argparse
import os
import time

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def main(model_id: str, deployment: str, sku: str, capacity: int, confirm_paid: bool) -> None:
    if not confirm_paid:
        raise SystemExit("paid deployment blocked; rerun with --confirm-paid")
    load_dotenv(override=True)
    required = ("AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_AI_ACCOUNT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"missing environment variables: {', '.join(missing)}")
    credential = DefaultAzureCredential(process_timeout=20)
    token = credential.get_token("https://management.azure.com/.default").token
    url = (
        f"https://management.azure.com/subscriptions/{os.environ['AZURE_SUBSCRIPTION_ID']}"
        f"/resourceGroups/{os.environ['AZURE_RESOURCE_GROUP']}/providers/Microsoft.CognitiveServices"
        f"/accounts/{os.environ['AZURE_AI_ACCOUNT']}/deployments/{deployment}?api-version=2023-05-01"
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"sku": {"name": sku, "capacity": capacity}, "properties": {"model": {"format": "OpenAI", "name": model_id, "version": "1"}}}
    response = httpx.put(url, headers=headers, json=body, timeout=60)
    response.raise_for_status()
    for _ in range(20):
        state_response = httpx.get(url, headers=headers, timeout=30)
        state_response.raise_for_status()
        state = state_response.json().get("properties", {}).get("provisioningState")
        print(state)
        if state == "Succeeded":
            return
        if state == "Failed":
            raise RuntimeError(state_response.text)
        time.sleep(15)
    raise TimeoutError("deployment did not finish within five minutes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model_id")
    parser.add_argument("deployment")
    parser.add_argument("--sku", default="GlobalStandard")
    parser.add_argument("--capacity", type=int, default=50)
    parser.add_argument("--confirm-paid", action="store_true")
    args = parser.parse_args()
    main(args.model_id, args.deployment, args.sku, args.capacity, args.confirm_paid)