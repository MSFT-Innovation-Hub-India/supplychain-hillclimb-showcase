# Evaluation Artifacts

This folder contains the published evidence behind the quality, latency, and cost claims in the repository documentation. Raw JSON reports retain per-scenario measurements; Markdown files explain the findings; the PNG is the presentation chart generated from the combined report.

The model comparison app does not load these artifacts at runtime. Its recorded demonstration scenario and model outputs are embedded in [`model_comparison_app/app.py`](../../model_comparison_app/app.py). The app's [README](../../model_comparison_app/README.md) references the full evaluation only as supporting evidence.

## Published Results

| Artifact | Purpose | Referenced by |
|---|---|---|
| `evaluation-20260724-225229.json` | Raw 150-scenario teacher, SFT, and RFT evaluation | [`evaluation-20260724-225229.md`](evaluation-20260724-225229.md), [`reasoning-hill-climb-20260725.md`](reasoning-hill-climb-20260725.md), and the [comparison app guide](../../model_comparison_app/README.md) |
| `evaluation-20260724-225229.md` | Narrative report for the original three-arm evaluation | The [evaluation guide](../README.md) |
| `evaluation-20260725-130458.json` | Raw 150-scenario medium-reasoning teacher evaluation | Both published Markdown reports in this folder |
| `reasoning-hill-climb-20260725.json` | Combined four-package data used to generate the hill-climb chart | [`plot_step_hill_climb.py`](../plot_step_hill_climb.py) through the command in the [runbook](../../RUNBOOK.md) |
| `reasoning-hill-climb-20260725.md` | Final reasoning-aware comparison and interpretation | The [evaluation guide](../README.md) and original evaluation report |
| `step-hill-climb-20260725.png` | Published quality, cost, and latency hill-climb chart | The root [README](../../README.md), [evaluation guide](../README.md), and published reports |

## Archive

The [`archive`](archive/) folder contains exploratory, superseded, or incomplete runs that are not referenced by the current code or published documentation:

| Artifact | Purpose | Current code references |
|---|---|---|
| `evaluation-20260722-160020.json` | Earlier 150-scenario evaluation | None; superseded by the published runs |
| `evaluation-20260723-211948.json` | Earlier 150-scenario evaluation | None; superseded by the published runs |
| `evaluation-20260725-092214.json` | One-scenario high-reasoning probe | None; exploratory only |
| `evaluation-20260725-093827.json` | One-scenario medium-reasoning probe | None; exploratory only |
| `.teacher_high-150-99111228780a.progress.json` | Resume checkpoint from an incomplete high-reasoning evaluation | Read only when resuming the exact matching evaluation configuration |

The evaluation runner creates timestamped JSON reports in this folder and temporary hidden progress files while a run is active. Successful runs delete their progress files automatically. Review new reports before treating them as published evidence; move superseded or incomplete runs to `archive`.