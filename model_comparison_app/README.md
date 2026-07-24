# Allocation Recovery Lab

Streamlit client for comparing any two of the SFT, RFT, and teacher deployments on one fixed three-order supply-chain recovery scenario.

## Run

From the repository root:

```powershell
python -m streamlit run model_comparison_app/app.py
```

The app reads Azure endpoint configuration from the repository `.env` and authenticates with `DefaultAzureCredential`. The initial SFT and RFT panes contain a verified live run; use the model controls to generate fresh results.
