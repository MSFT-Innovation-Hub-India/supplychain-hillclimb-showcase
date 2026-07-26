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

Live Azure mode requires environment-specific resource and deployment names. Create `.env` from the committed template:

```powershell
Copy-Item .env.example .env
```

Set `AZURE_OPENAI_ENDPOINT`, `SFT_DEPLOYMENT`, `RFT_DEPLOYMENT`, and `TEACHER_DEPLOYMENT` to values from your Azure AI resource. The deployment values in `.env.example` are intentionally blank because deployment names are created per resource and the historical experiment deployments no longer exist.

The app authenticates with `DefaultAzureCredential`; `.env` contains configuration, not credentials. It is ignored by Git because its values are machine- and resource-specific. Leave **Execution mode** set to **Recorded replay** when these Azure resources are unavailable.

The published evaluation data is retained under [`04_evaluation/results/`](../04_evaluation/results/README.md), with superseded and exploratory runs documented in its `archive` subfolder. `evaluation-20260724-225229.json` contains teacher, SFT, and RFT results over 150 held-out scenarios. The app does not load that file; it intentionally uses one embedded scenario and its recorded outputs for an understandable side-by-side demonstration.

The replay artifact retained plans and latency, but not the original request messages. The prompt panel therefore shows training provenance, not an asserted replay request: SFT-v2 was trained with the detailed business-rules prompt and RFT-v1 with the thin prompt. In Live Azure mode, those displayed prompts are the prompts actually sent.
