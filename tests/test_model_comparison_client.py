import os
from types import SimpleNamespace
from unittest.mock import patch

from common.prompts import scenario_message
from common.scenario import generate_scenario
from model_comparison_app.foundry_agent_client import create_project_client, request_agent_plan


def test_create_project_client_uses_app_endpoint_and_default_credential():
    with (
        patch.dict(os.environ, {"AZURE_AI_PROJECT_ENDPOINT": "https://example.test/project/"}),
        patch("model_comparison_app.foundry_agent_client.DefaultAzureCredential") as credential,
        patch("model_comparison_app.foundry_agent_client.AIProjectClient") as project_client,
    ):
        create_project_client()

    credential.assert_called_once_with(process_timeout=20)
    assert project_client.call_args.kwargs["endpoint"] == "https://example.test/project"
    assert project_client.call_args.kwargs["credential"] == credential.return_value


def test_request_agent_plan_uses_pinned_agent_reference_and_parses_json():
    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text='{"decisions":[]}',
                usage=SimpleNamespace(input_tokens=17, output_tokens=9, total_tokens=26),
            )

    project_client = SimpleNamespace(
        get_openai_client=lambda: SimpleNamespace(responses=Responses())
    )
    scenario = generate_scenario(123)

    plan, usage = request_agent_plan(project_client, "sft-agent", "13", scenario)

    assert plan == {"decisions": []}
    assert captured["input"] == [{"role": "user", "content": scenario_message(scenario)}]
    assert captured["extra_body"] == {
        "agent_reference": {"name": "sft-agent", "version": "13", "type": "agent_reference"}
    }
    assert usage["total_tokens"] == 26