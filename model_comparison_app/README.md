# Allocation Recovery Lab

Streamlit client for comparing SFT and RFT on one fixed three-order supply-chain recovery scenario. The app includes the exact scenario and verified outputs captured from the original deployments, so it can be demonstrated after those deployments are deleted.

## Run

From the repository root:

```powershell
python -m streamlit run model_comparison_app/app.py
```

Open the displayed local URL and leave **Execution mode** set to **Recorded replay**. Use **Replay both models** while recording. Replay mode:

- requires no Azure deployment, credentials, or network access;
- loads the captured SFT and RFT plans for the displayed scenario;
- recomputes reward, feasibility, constraints, and business rationale with the repository grader;
- retains the original measured inference latency as historical context.

**Live Azure** remains available for future deployments. It reads endpoint configuration from the repository `.env`, authenticates with `DefaultAzureCredential`, and requires the deployment names in `MODEL_OPTIONS` to exist.

The published evaluation data is retained under [`04_evaluation/results/`](../04_evaluation/results/README.md), with superseded and exploratory runs documented in its `archive` subfolder. `evaluation-20260724-225229.json` contains teacher, SFT, and RFT results over 150 held-out scenarios. The app does not load that file; it intentionally uses one embedded scenario and its recorded outputs for an understandable side-by-side demonstration.
