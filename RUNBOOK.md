# Supply-Chain Model Hill-Climb Runbook

This runbook provides the end-to-end command sequence for reproducing the experiment, from local validation through fine-tuning, deployment, and held-out evaluation.

> [!IMPORTANT]
> The experiment compares model-and-method packages available in Microsoft Foundry, not training methods applied to a common base model. The preregistered objective is for RFT to beat SFT by at least `0.05`, with a paired 95% bootstrap confidence interval above `0`, while avoiding output-pattern collapse. Raw `o4-mini` uplift cannot be measured because Azure allows fine-tuning this deprecated model but not deploying it raw.

## 1. Install And Validate Locally

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\validation\preflight.py --count 50
```

## 2. Configure The Environment

Copy `.env.example` to `.env` and set the real deployment and resource names. Raw base deployments are optional context arms. Do not substitute another model as an `o4-mini` proxy when deprecated raw `o4-mini` cannot be deployed.

## 3. Run The Go/No-Go Pilot

> [!WARNING]
> The following commands make billable model calls.

Run the 50-scenario pilot:

```powershell
.\.venv\Scripts\python.exe 01_baseline_teacher\capture_pilot.py --count 50 --teacher-attempts 3 --confirm-paid
.\.venv\Scripts\python.exe 01_baseline_teacher\analyze_pilot.py
```

Stop if any gate fails. Do not weaken a failed gate after seeing the results.

## 4. Build The Training Datasets And Grader

Capture fixed-budget teacher labels, build the SFT and RFT datasets, and generate the grader:

```powershell
.\.venv\Scripts\python.exe 01_baseline_teacher\capture_training.py --train 300 --valid 60 --teacher-attempts 3 --sft-threshold 0.75 --confirm-paid
.\.venv\Scripts\python.exe 02_dataset_build\build_datasets.py
.\.venv\Scripts\python.exe 03_finetuning\rft\build_grader.py
```

## 5. Submit The Fine-Tuning Jobs

Review current Azure pricing and the pilot evidence before submitting either job.

```powershell
.\.venv\Scripts\python.exe scripts\validation\pre_submit_audit.py
.\.venv\Scripts\python.exe 03_finetuning\rft\submit_rft_job.py --confirm-paid
.\.venv\Scripts\python.exe 03_finetuning\sft\submit_sft_job.py --confirm-paid
```

## 6. Deploy The Fine-Tuned Models

Run the following command for each completed fine-tuned model:

```powershell
.\.venv\Scripts\python.exe 03_finetuning\deploy_finetuned_model.py MODEL_ID DEPLOYMENT_NAME --confirm-paid
```

## 7. Run The Held-Out Evaluation

Review the current Azure per-million-token rates for each deployment. Then evaluate the teacher, SFT, and RFT packages on the same 150 held-out scenarios:

```powershell
.\.venv\Scripts\python.exe 04_evaluation\evaluate.py --arm teacher=TEACHER_DEPLOYMENT --arm sft=SFT_DEPLOYMENT --arm rft=RFT_DEPLOYMENT --pricing teacher=INPUT_RATE,OUTPUT_RATE,CACHED_INPUT_RATE --pricing sft=INPUT_RATE,OUTPUT_RATE,CACHED_INPUT_RATE --pricing rft=INPUT_RATE,OUTPUT_RATE,CACHED_INPUT_RATE --count 150 --compare rft,sft --confirm-paid
```

Add `raw_rft` or `raw_sft` arms only when those exact raw deployments exist.

Generate the stepped quality, cost, and latency hill-climb chart:

```powershell
.\.venv\Scripts\python.exe 04_evaluation\plot_step_hill_climb.py 04_evaluation\results\reasoning-hill-climb-20260725.json --output 04_evaluation\results\step-hill-climb-20260725.png
```

## Reporting Criteria

Do not claim that RFT is better unless the saved evaluation shows all of the following:

- The RFT-SFT mean difference is at least `0.05`.
- The paired confidence interval excludes zero.
- `dominant_pattern_share` remains below the frozen `0.80` collapse threshold.
- `all_defer_share` remains below the frozen `0.80` collapse threshold.

Always report that raw `o4-mini` uplift was unmeasurable because the raw model could not be deployed.