# Trace Artifacts

This folder contains the current teacher-model traces and gates used by the experiment pipeline. These files are generated artifacts rather than hand-maintained source data. They are retained because reproducing them requires billable model calls.

The model comparison app does not read any file in this folder.

## Active Pipeline Artifacts

| Artifact | Purpose | Written by | Read or referenced by |
|---|---|---|---|
| `pilot.jsonl` | Raw candidate plans and scores from the current go/no-go pilot | [`capture_pilot.py`](../capture_pilot.py) | [`analyze_pilot.py`](../analyze_pilot.py) |
| `pilot_gate.json` | Frozen pilot decision, checks, and experiment limitations | [`analyze_pilot.py`](../analyze_pilot.py) | [`common/fine_tuning_api.py`](../../common/fine_tuning_api.py), [`pre_submit_audit.py`](../../scripts/validation/pre_submit_audit.py), and the [fine-tuning guide](../../03_finetuning/README.md) |
| `training.jsonl` | Captured teacher plans, deterministic scores, split assignments, and SFT eligibility | [`capture_training.py`](../capture_training.py) | [`build_datasets.py`](../../02_dataset_build/build_datasets.py), [`pre_submit_audit.py`](../../scripts/validation/pre_submit_audit.py), and the [dataset guide](../../02_dataset_build/README.md) |

## Archive

The [`archive`](archive/) folder preserves superseded pilot variants used while developing the final prompt and pilot gate:

| Artifacts | Purpose | Current code references |
|---|---|---|
| `pilot-before-detailed-prompt-20260725.jsonl` and matching gate | Baseline pilot before the detailed planning prompt | None; retained for provenance |
| `pilot-detailed-prompt-independent-retries-20260725.jsonl` and matching gate | Pilot using the detailed prompt with independent retries | None; retained for provenance |
| `pilot-guided-default-reasoning-50-20260725.jsonl` and matching gate | Full guided pilot at the default reasoning setting | None; retained for provenance |
| `pilot-guided-probe-10-20260725.jsonl` | Small guided prompt probe | None; retained for provenance |

Archived traces are not inputs to dataset generation, fine-tuning, evaluation, or the comparison app. Move an archived file back only when intentionally reproducing that historical experiment variant and update the relevant script path explicitly.