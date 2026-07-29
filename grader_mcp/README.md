# Supply Chain Grader MCP

Remote Streamable HTTP MCP server exposing the repository's deterministic
`common.scoring.score_plan` implementation.

## Foundry connection

- URL: `https://foundry-agent-grader-mcp.calmwave-eb4dbdd3.swedencentral.azurecontainerapps.io/mcp`
- Authentication: key/header based
- Header name: `X-API-Key`
- Tool: `assess_supply_chain_plan`

Azure resource:

- Subscription: `35d56b9b-9660-4b8a-aaf6-76cfc033ac97`
- Resource group: `rg-foundry-app-svc`
- Container App: `foundry-agent-grader-mcp`
- Region: Sweden Central

The tool accepts the complete original `scenario` and `model_output`. The model
output may be a JSON object or a JSON-encoded string. Its return value is the
authoritative scorer result containing `score`, `feasible`, `reason`, `category`,
and `metrics`, plus a `report` containing summary, quality, and allocation rows,
deterministic business explanations, and ready-to-render Markdown tables.

Model latency and token usage are not observable after the model response reaches
the grader. Callers may optionally pass them in `execution_metadata`; absent values
are reported as `Not provided` rather than estimated.

Instruct the agent to always call the tool after generating a plan, render
`report.markdown` verbatim for detailed reports, and never recalculate the result.

## Deployment

The server runs as its own Container App (`foundry-agent-grader-mcp`), separate from
the `model_comparison_app` Container App, in the same reused Container Apps
environment (`cae-foundry-agent-grader`, resource group `rg-foundry-app-svc`).

- **Image**: built from [`Dockerfile`](Dockerfile) — `python:3.12-slim`, copies only
  `common/` (for `common.scoring.score_plan`) and `grader_mcp/`, installs
  [`requirements.txt`](requirements.txt), runs as a non-root user, and starts
  `uvicorn grader_mcp.server:app` on port `8000`.
- **App surface**: a Streamlit-free ASGI app (`mcp.streamable_http_app()`) exposing:
  - `POST /mcp` — the Streamable HTTP MCP endpoint agents/tools connect to.
  - `GET /health` — unauthenticated liveness check, excluded from API-key enforcement.
- **Auth**: `ApiKeyMiddleware` in [`server.py`](server.py) requires a shared secret on
  every `/mcp` request via the `X-API-Key` header (or `Authorization: Bearer <key>`),
  checked with a constant-time comparison against the `GRADER_API_KEY` environment
  variable. A missing/misconfigured `GRADER_API_KEY` fails closed with `503`, not `401`,
  so the server never silently runs unauthenticated.
- **DNS-rebinding protection**: `TransportSecuritySettings` only allows `localhost`/
  loopback hosts plus whatever host is set in the `GRADER_ALLOWED_HOST` environment
  variable (the Container App's own FQDN in production).

This Container App does not need a managed identity for its own operation — it doesn't
call any other Azure resource. It only needs `AcrPull` (or `Container Registry Repository
Reader`) on the shared ACR so the environment can pull its image, the same as any other
app in this environment.

## Using it as a tool from the Foundry portal playground

Because it's a standard remote Streamable HTTP MCP server, it can be attached as an
**MCP tool** to any agent in the Foundry portal — including outside this repo's own
SFT/RFT/Teacher agents — for interactive testing from the playground:

1. In the agent's tool configuration, add an MCP tool pointing at
   `https://foundry-agent-grader-mcp.calmwave-eb4dbdd3.swedencentral.azurecontainerapps.io/mcp`.
2. Configure the required header (`X-API-Key`) with the shared `GRADER_API_KEY` value.
3. In the playground, ask the agent to call `assess_supply_chain_plan` with a `scenario`
   and a `model_output` (a plan). The tool returns the deterministic score, feasibility,
   category, metrics, and a Markdown `report` — exactly what the deployed SFT/RFT/Teacher
   agents receive when they call this same tool automatically during a real run.

### Limitation: full assessment reports need manually supplied execution metadata

`execution_metadata` (`latency_seconds`, `prompt_tokens`, `completion_tokens`,
`total_tokens`) is an **optional** third argument to `assess_supply_chain_plan`. The
grader has no way to observe how long the model took to respond or how many tokens it
consumed — that information only exists on the *caller's* side, in the original model
response, not in anything the grader can inspect after the fact.

When testing from the Foundry playground, the model has no built-in mechanism to
introspect its own just-completed generation's latency or token usage and pass that back
to itself as a tool argument on the next turn — the playground UI doesn't expose those
values for the agent to forward automatically. In practice this means:

- If you only pass `scenario` and `model_output`, the tool still returns a fully valid
  score, feasibility result, and report — the "Model latency (seconds)" and "Total
  tokens" rows in the summary table just render as `Not provided` (see
  `_build_report` in [`server.py`](server.py)).
- To see those fields populated while testing manually from the playground, you have to
  read the latency/token numbers off the model's own response (or the portal's run
  details) and type them into the tool call's `execution_metadata` argument yourself.
  This is why the grader MCP tool isn't wired into the playground's automatic
  agent-to-tool loop with metadata attached in this repo — there's no reliable way for
  the calling agent to supply it without a human copying it over.
- This limitation is specific to **manual playground testing**. The MCP server itself is
  fully deployed and running continuously; the `model_comparison_app` calls agents whose
  definitions reference this same tool, and any client capable of measuring its own
  latency/token usage (like `model_comparison_app`'s Foundry client) can pass
  `execution_metadata` and get a fully populated report.