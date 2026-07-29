# Allocation Recovery Lab

Streamlit client for comparing SFT and RFT on one fixed three-order supply-chain recovery scenario. The app includes the exact scenario and verified outputs captured from the original deployments, so it can be demonstrated after those deployments are deleted.

## Run

For the default **Recorded replay**, no `.env`, Azure credentials, deployments, or network access are required. From the repository root, install the app requirements and start Streamlit:

```powershell
.\.venv\Scripts\python.exe -m pip install -r model_comparison_app\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run model_comparison_app\app.py
```

Open the displayed local URL and leave **Execution mode** set to **Recorded replay**. Use **Replay both models** while recording. Replay mode:

- requires no Azure deployment, credentials, or network access;
- loads the captured SFT and RFT plans for the displayed scenario;
- recomputes reward, feasibility, constraints, and business rationale with the repository grader;
- retains the original measured inference latency as historical context.

## Live Azure Configuration

Live Azure mode invokes pinned Microsoft Foundry prompt agents through the Responses API. Create an app-local `.env` from the committed template:

```powershell
Copy-Item model_comparison_app\.env.example model_comparison_app\.env
```

Set `AZURE_AI_PROJECT_ENDPOINT` and the agent names and versions. This app-specific configuration is independent of the direct model deployment settings used by the fine-tuning, capture, and evaluation code.

The app authenticates with `DefaultAzureCredential`; `.env` contains configuration, not credentials. In Azure Container Apps, provide the same values as environment variables and grant the Container App's managed identity permission to invoke agents in the Foundry project. Leave **Execution mode** set to **Recorded replay** when these resources are unavailable.

The published evaluation data is retained under [`04_evaluation/results/`](../04_evaluation/results/README.md), with superseded and exploratory runs documented in its `archive` subfolder. `evaluation-20260724-225229.json` contains teacher, SFT, and RFT results over 150 held-out scenarios. The app does not load that file; it intentionally uses one embedded scenario and its recorded outputs for an understandable side-by-side demonstration.

The replay artifact retained plans and latency, but not the original request messages. The prompt panel therefore shows package provenance: SFT-v2 was trained with the detailed business-rules prompt and RFT-v1 with the thin prompt. In Live Azure mode, runtime instructions come from the pinned Foundry agent definitions.

## Deploying to Azure Container Apps

The app runs as a single Container App with a system-assigned managed identity, reusing an existing Container Apps environment, Azure Container Registry, and Foundry project — no new environment, registry, or project is created for this app.

Required role assignments for the Container App's managed identity:

| Role | Scope | Purpose |
| --- | --- | --- |
| `AcrPull` | Azure Container Registry | Pull the app's container image |
| `Foundry Agent Consumer` | Foundry project (or the specific agent) | Least-privilege data-plane role to invoke a *published* agent endpoint via the Responses API |
| `Foundry User` | Foundry project | Required in addition to `Foundry Agent Consumer` while the agents are **unpublished/draft** (see gotcha below) |

Assign roles with the Azure CLI, for example:

```powershell
$principalId = az containerapp show --name <app-name> --resource-group <rg> --query identity.principalId -o tsv

az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role AcrPull --scope <acr-resource-id>

az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role "Foundry Agent Consumer" --scope <foundry-project-resource-id>

az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role "Foundry User" --scope <foundry-project-resource-id>
```

Role assignments can take several minutes to propagate; restart the Container App revision after assigning roles to force a fresh managed-identity token rather than waiting on the old one to expire.

### Changing the pinned agent version without a rebuild/redeploy

Agent versions (`SFT_AGENT_VERSION`, `RFT_AGENT_VERSION`, `TEACHER_AGENT_VERSION`) are plain environment variables — `app.py` already reads them via `os.environ.get(...)`. Whenever you iterate on an agent's instructions/version in Foundry, update the **running** Container App directly instead of rebuilding the image:

```powershell
az containerapp update --name foundry-agent-grader-app --resource-group rg-foundry-app-svc `
  --set-env-vars SFT_AGENT_VERSION=<n> RFT_AGENT_VERSION=<n> TEACHER_AGENT_VERSION=<n>
```

This creates a new Container App revision using the **same existing image** — no Docker build, no ACR push, no code change. It takes effect within seconds. Verify with:

```powershell
az containerapp show --name foundry-agent-grader-app --resource-group rg-foundry-app-svc `
  --query "properties.template.containers[0].env"
```

`infra/main.bicep` also exposes `sftAgentVersion`, `rftAgentVersion`, and `teacherAgentVersion` parameters (mirrored in `infra/main.parameters.json`) so a future full redeploy of the Bicep template won't silently revert to stale defaults. Keep those parameter defaults in sync with whatever you last set via `az containerapp update`, but day-to-day version changes should go through the command above, not a Bicep redeploy.

### Gotcha: unpublished/draft agents need `Foundry User`, not just `Foundry Agent Consumer`

Microsoft's documentation states `Foundry Agent Consumer` is sufficient to invoke an agent endpoint via the Responses API (`agent_reference`). That's true for a **published** agent. For a declarative/prompt agent authored directly in the Foundry portal that has **not yet been published**, calls from a service principal (managed identity) with only `Foundry Agent Consumer` fail with an opaque, empty-body `403` — even though the identical call succeeds instantly for an interactive user identity (e.g. the agent's author, or the Foundry portal playground) with the same or lesser project role.

How this was diagnosed:

- The 403 response body was empty (no `AuthorizationFailed`-style JSON), unlike genuine RBAC denials on other calls (e.g. `models.list()`), which pointed away from a simple missing-role explanation.
- Decoding the JWTs for both the working user call and the failing managed-identity call showed identical `aud` (`https://ai.azure.com`), `tid`, and API version — the only difference was `idtyp`: `"user"` (works) vs `"app"` (fails).
- Both pinned agent versions were confirmed to exist and be independently callable (ruling out a stale/incorrect version pin).
- The account's network ACLs were open (`publicNetworkAccess: Enabled`, default action `Allow`), ruling out a firewall/VNet cause.
- Adding `Foundry User` at project scope (in addition to the existing `Foundry Agent Consumer`) resolved the 403 immediately after a revision restart — with no other change.

If you later publish the agents, re-test with only `Foundry Agent Consumer` — the extra `Foundry User` grant may no longer be necessary once the agents are out of draft/authoring state.
