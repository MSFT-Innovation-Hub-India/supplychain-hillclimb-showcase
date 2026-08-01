"""Redeploy an already fine-tuned model into a Cognitive Services account in any subscription.

Unlike deploy_finetuned_model.py, every Azure Resource Manager coordinate is an
explicit argument instead of an environment variable, so this script can target a
destination subscription, resource group, and account that differ from the source
account the model was trained in. This is what a deleted deployment recovery, or a
move of a fine-tuned model to a new environment, requires.

No fine-tuning job, dataset, or grader is touched. This only creates or updates a
deployment that points at an already-trained fine-tuned model ID.
"""

from __future__ import annotations

import argparse
import time

import httpx
from azure.identity import DefaultAzureCredential


def _management_token() -> str:
    credential = DefaultAzureCredential(process_timeout=20)
    return credential.get_token("https://management.azure.com/.default").token


def _deployment_url(subscription: str, resource_group: str, account: str, deployment: str, api_version: str) -> str:
    return (
        f"https://management.azure.com/subscriptions/{subscription}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices"
        f"/accounts/{account}/deployments/{deployment}?api-version={api_version}"
    )


def _resolve_model_id(args: argparse.Namespace, headers: dict[str, str]) -> str:
    if args.model_id:
        return args.model_id
    # Read the model id straight from an existing deployment instead of guessing it.
    url = _deployment_url(
        args.source_subscription,
        args.source_resource_group,
        args.source_account,
        args.source_deployment_name,
        args.api_version,
    )
    response = httpx.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    model_id = response.json()["properties"]["model"]["name"]
    print(f"resolved model id from source deployment: {model_id}")
    return model_id


def main(args: argparse.Namespace) -> None:
    if not args.confirm_paid:
        raise SystemExit("paid deployment blocked; rerun with --confirm-paid")
    source_values = (args.source_subscription, args.source_resource_group, args.source_account)
    if any(source_values) and not all(source_values):
        raise SystemExit("provide --source-subscription, --source-resource-group, and --source-account together")
    has_source_lookup = all(source_values) and args.source_deployment_name
    if not args.model_id and not has_source_lookup:
        raise SystemExit("provide --model-id, or all four --source-* arguments to resolve it")

    token = _management_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    model_id = _resolve_model_id(args, headers)
    url = _deployment_url(args.destination_subscription, args.destination_resource_group, args.destination_account, args.deployment_name, args.api_version)
    model = {"format": "OpenAI", "name": model_id, "version": "1"}
    if all(source_values):
        model["source"] = (
            f"/subscriptions/{args.source_subscription}"
            f"/resourceGroups/{args.source_resource_group}"
            "/providers/Microsoft.CognitiveServices"
            f"/accounts/{args.source_account}"
        )
    body = {
        "sku": {"name": args.sku, "capacity": args.capacity},
        "properties": {"model": model},
    }
    response = httpx.put(url, headers=headers, json=body, timeout=60)
    if response.is_error:
        raise RuntimeError(
            f"Deployment request failed ({response.status_code}): {response.text}"
        )

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        state_response = httpx.get(url, headers=headers, timeout=30)
        state_response.raise_for_status()
        state = state_response.json().get("properties", {}).get("provisioningState")
        print(state)
        if state == "Succeeded":
            return
        if state == "Failed":
            raise RuntimeError(state_response.text)
        time.sleep(args.interval)
    raise TimeoutError(f"deployment did not finish within {args.timeout} seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deployment_name", help="Deployment name to create or update in the destination account, e.g. supplychain-sft")
    parser.add_argument("--model-id", help="Fully-qualified fine-tuned model id, e.g. gpt-4.1-mini-2025-04-14.ft-<job-id>-allocation-sft-v2")
    parser.add_argument("--source-subscription", help="Subscription of the account that owns the fine-tuned model")
    parser.add_argument("--source-resource-group")
    parser.add_argument("--source-account")
    parser.add_argument("--source-deployment-name", help="Existing deployment name in the source account to read properties.model.name from")
    parser.add_argument("--destination-subscription", required=True)
    parser.add_argument("--destination-resource-group", required=True)
    parser.add_argument("--destination-account", required=True)
    parser.add_argument("--sku", default="DeveloperTier")
    parser.add_argument("--capacity", type=int, default=1)
    parser.add_argument("--api-version", default="2024-10-01")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--confirm-paid", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
