import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from common.model_client import create_client, plan_messages, request_plan
from common.prompts import SYSTEM_PROMPT, scenario_message
from common.scenario import generate_scenario


def test_plan_messages_preserves_one_shot_contract():
    scenario = generate_scenario(123)
    assert plan_messages(scenario) == [
        {"role": "developer", "content": SYSTEM_PROMPT},
        {"role": "user", "content": scenario_message(scenario)},
    ]


def test_plan_messages_adds_prior_plan_and_validator_feedback_for_revision():
    scenario = generate_scenario(123)
    previous_plan = {"decisions": [{"order_id": scenario["orders"][0]["order_id"], "action": "defer"}]}
    messages = plan_messages(scenario, previous_plan, "Validator feedback")
    assert [message["role"] for message in messages] == ["developer", "user", "assistant", "user"]
    assert json.loads(messages[2]["content"]) == previous_plan
    assert messages[3]["content"] == "Validator feedback"


def test_request_plan_passes_explicit_reasoning_effort():
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"decisions":[]}'))],
                usage=None,
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    request_plan(client, "teacher", generate_scenario(123), reasoning_effort="high")
    assert captured["reasoning_effort"] == "high"


def test_create_client_uses_configurable_long_timeout_for_reasoning_calls():
    with (
        patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://example.test", "MODEL_REQUEST_TIMEOUT_SECONDS": "720"}),
        patch("common.model_client.DefaultAzureCredential"),
        patch("common.model_client.get_bearer_token_provider", return_value="token"),
        patch("common.model_client.OpenAI") as openai,
    ):
        create_client()
    assert openai.call_args.kwargs["timeout"] == 720.0