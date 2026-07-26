# Held-Out Evaluation

This stage compares teacher, SFT, and RFT deployments on the same deterministic 150-scenario test split. It records the three dimensions needed for the showcase's hill climb:

- **Quality:** deterministic plan score, feasibility, service, retained margin, cost efficiency, and failure modes.
- **Cost:** input, cached-input, output, reasoning, and visible-output tokens, plus an optional USD estimate based on rates supplied at run time.
- **Latency:** end-to-end model-call duration for every scenario and aggregate mean, P50, P95, minimum, and maximum.

The test scenarios start at seed `50_000` and rotate through tight, mixed, and loose families. They do not overlap the training or validation splits. Every arm receives the same scenario objects in the same order, enabling paired comparisons.

One **scenario** is one complete disruption-recovery request containing 12-16 orders, three warehouses (one disrupted), inventory by SKU, warehouse shipment capacity, delivery times and costs, approved substitutes, and one shared expedite budget. A model must return one coordinated decision for every order. The reported time and cost per scenario cover one model request and its complete plan response.

The latest reasoning comparison is documented in [Reasoning Hill-Climb Evaluation](results/reasoning-hill-climb-20260725.md). The original three-arm run remains documented in [Teacher vs SFT vs RFT Evaluation Results](results/evaluation-20260724-225229.md).

See the [evaluation artifact index](results/README.md) for the purpose, references, and retention status of every published or archived result.

## Latest Complete Results

The July 25 comparison retains the original July 24 runs and adds the completed teacher-medium run on the same 150 held-out scenarios:

| Arm | Reasoning level | Quality | Feasible | Mean time/scenario | P50 / P95 latency | Avg reasoning tokens | Token cost/scenario | Hosting cost/scenario** |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Teacher, previous run | Default / not set | 0.335 | 42.7% (64/150) | 4.73 s | 4.54 s / 5.59 s | 0.0 | $0.00858 | N/A |
| Teacher, current run | **Medium (explicit)** | **0.851** | 99.3% (149/150) | 82.50 s | 66.68 s / 188.69 s | 6,463.4 | $0.09975 | N/A |
| SFT | Default / not set | 0.313 | 38.7% (58/150) | 4.14 s | 4.18 s / 4.68 s | 0.0 | $0.00119 | $0.00196 |
| RFT | Medium configured* | 0.833 | **100% (150/150)** | 61.73 s | 58.59 s / 100.53 s | 6,294.2 | $0.03101 | $0.02915 |

\* The RFT training configuration used medium reasoning. Its historical evaluation did not persist the inference-time effort field, so this label is configuration-derived rather than directly recorded on each evaluation row.

\** Fine-tuned Standard/Global Standard hosting is `$1.70/hour`. The table allocates that continuously accruing fee over this sequential evaluation using `$1.70 × mean scenario seconds / 3,600`. This is `$0.2933` for the complete SFT run and `$4.3726` for the complete RFT run. Actual production hosting cost per scenario is `$1.70 / scenarios served per hour`; idle time increases it and concurrent throughput reduces it. Teacher deployments are not fine-tuned models, so this additional hosting fee does not apply here.

**Feasibility** is the percentage of scenarios where the model returned a valid, executable plan that satisfied schema, order coverage, inventory, capacity, substitution, quantity, warehouse, shipping-mode, and expedite-budget constraints. Feasibility does not guarantee a high-value plan; for example, deferring every order can be feasible while earning zero quality.

**Quality** is the mean deterministic business score over all 150 scenarios, including a zero for every infeasible plan. It combines priority-weighted on-time service, retained margin, and fulfillment-adjusted cost efficiency:

$$
Q = 0.55S + 0.25M + 0.20C_e
$$

Teacher-medium beat the previous teacher package by 0.516 quality points and narrowly beat RFT by 0.018 points with a paired 95% confidence interval of `[0.003, 0.029]`. The teacher comparison also includes a strengthened prompt, so it does not isolate reasoning effort as the sole cause. RFT retains perfect feasibility and materially lower latency and cost than teacher-medium.

## Hill-Climb Assessment

![Supply-chain model step hill climb](results/step-hill-climb-20260725.png)

The stepped assessment follows the actual optimization sequence:

1. **GPT-5.2 teacher, no explicit reasoning:** latency was low at 4.54 seconds P50, but quality was only 0.335 and just 42.7% of plans were feasible. This established a fast but weak baseline.
2. **GPT-4.1-mini SFT:** distilling the teacher into a smaller model reduced P50 latency to 4.18 seconds and token cost to `$0.00119` per scenario. Quality did not transfer successfully: it fell to 0.313 and feasibility fell to 38.7%. This was a cost optimization, not a quality improvement.
3. **GPT-5.2 teacher with medium reasoning:** quality climbed to 0.851 and feasibility to 99.3%, demonstrating that the strengthened prompt and explicit reasoning solved the planning task. The trade-off was substantial: P50 latency rose to 66.68 seconds and token cost to `$0.09975` per scenario, the highest of all four packages.
4. **o4-mini RFT with medium reasoning:** RFT reached 0.833 quality and 100% feasibility, closely matching the reasoning teacher while reducing P50 latency to 58.59 seconds and token cost to `$0.03101` per scenario. It is the strongest operational package in this experiment because it retains near-teacher quality with lower latency and roughly 69% lower token cost.

The chart's composite success index weights quality at 70%, inverse token cost at 15%, and inverse P50 latency at 15%, after min-max normalization across the four measured packages. This produces scores of 32, 30, 70, and 80 respectively. The small SFT decline is intentional: its efficiency gains did not compensate for lower quality. The final RFT step is the hill-climb outcome, preserving nearly all of the teacher's quality while improving both operational dimensions. Green metrics improved from the previous stage; red metrics worsened.

### Historical prompt provenance

The SFT-v2 job was trained with the detailed business-rules prompt; the RFT job was trained earlier with the thin v1 prompt. The published three-arm run in `evaluation-20260724-225229.json` predates explicit prompt-package routing and sent the then-current detailed business-rules prompt to teacher, SFT, and RFT alike. Its reported scores are valid for those exact model-plus-prompt packages, but the RFT score is not a thin-prompt inference result. The later teacher reasoning runs used the strengthened teacher prompt.

The command below is intentionally different: it evaluates each fine-tuned deployment with the prompt used for its training run. Treat this as a new experiment configuration and write its output to a new result file; do not compare its numbers as though they came from the historical shared-prompt run.

## Run The Evaluation

Review the current Azure pricing for each deployed model, then pass the input and output rates in USD per one million tokens. Add a third rate only when cached input has a different price.

```powershell
.\.venv\Scripts\python.exe 04_evaluation/evaluate.py `
  --arm teacher=TEACHER_DEPLOYMENT `
  --arm sft=SFT_DEPLOYMENT `
  --arm rft=RFT_DEPLOYMENT `
  --prompt-package teacher=teacher `
  --prompt-package sft=detailed-fine-tuned `
  --prompt-package rft=thin-fine-tuned `
  --pricing teacher=TEACHER_INPUT_RATE,TEACHER_OUTPUT_RATE,TEACHER_CACHED_INPUT_RATE `
  --pricing sft=SFT_INPUT_RATE,SFT_OUTPUT_RATE,SFT_CACHED_INPUT_RATE `
  --pricing rft=RFT_INPUT_RATE,RFT_OUTPUT_RATE,RFT_CACHED_INPUT_RATE `
  --reasoning teacher=medium `
  --reasoning rft=medium `
  --count 150 `
  --compare rft,sft `
  --confirm-paid
```

Prompt packages are explicit because the showcased SFT-v2 job used the detailed business-rules prompt, the RFT job used the earlier thin prompt, and the teacher uses the strengthened planning prompt. Pricing is explicit because Azure prices vary by model, deployment type, and date. Omitting `--pricing` still records tokens, but the corresponding cost estimate and cost-based plot are unavailable. The evaluator blocks live calls unless `--confirm-paid` is present.

The supplied Global token rates used for this comparison are: o4-mini `$1.10` input, `$0.28` cached input, and `$4.40` output per million tokens; GPT-4.1-mini `$0.40`, `$0.10`, and `$1.60`; and GPT-5.2 `$1.75`, `$0.18`, and `$14.00`. Hosting is separate from these token charges.

For each arm, the runner:

1. Loads or creates a deployment-specific progress checkpoint.
2. Sends the shared policy and one held-out scenario to the deployment.
3. Measures the complete API-call duration, including SDK retries.
4. Parses the JSON plan and records detailed API token usage.
5. Applies the deterministic scorer locally.
6. Saves the row immediately so an interrupted paid run can resume.
7. Aggregates quality, usage, latency, cost, diversity, and collapse metrics.
8. Deletes progress checkpoints only after the final report is written.

Reports are saved as `results/evaluation-YYYYMMDD-HHMMSS.json`.

## Token And Cost Semantics

| Field | Meaning |
|---|---|
| `input_tokens` | All prompt tokens reported by the API, including cached input |
| `cached_input_tokens` | Input tokens served from cache when the API reports them |
| `output_tokens` | All billed completion tokens, including hidden reasoning tokens |
| `reasoning_tokens` | Hidden reasoning subset of `output_tokens` |
| `visible_output_tokens` | `output_tokens - reasoning_tokens` |
| `total_tokens` | Input plus output tokens reported by the API |

Reasoning tokens are reported separately for analysis but are **not added to output tokens again** when estimating cost:

$$
C = \frac{(T_i-T_c)P_i + T_cP_c + T_oP_o}{1{,}000{,}000}
$$

where $T_i$ is input tokens, $T_c$ is cached input, $T_o$ is output including reasoning, and $P_i$, $P_c$, and $P_o$ are their supplied rates. This is a token-based estimate; review the Azure invoice for authoritative charges.

## Quality Metrics

The primary score is the same deterministic business outcome used throughout the project:

$$
Q = 0.55S + 0.25M + 0.20C_e
$$

where $S$ is service, $M$ is retained margin, and $C_e$ is cost efficiency. Invalid plans receive zero for the score and all three components. Absolute shipping and expedite spend averages are calculated over feasible plans only so invalid zero-score plans are not misrepresented as inexpensive.

The report also includes feasibility, failure categories, dominant output-pattern share, all-defer share, and the paired bootstrap confidence interval. These distinguish genuine improvement from schema failures, constraint violations, or policy collapse.

## Hill-Climb Data And Plot

The report's `hill_climb.points` array contains one compact record per arm with:

- Mean quality, feasibility, service, retained margin, and cost efficiency.
- P50 and P95 end-to-end latency.
- Average input, output, and reasoning tokens.
- Estimated USD per scenario when pricing was supplied.

Generate the visual after a complete multi-arm run:

```powershell
.\.venv\Scripts\python.exe 04_evaluation/plot_step_hill_climb.py `
  04_evaluation/results/reasoning-hill-climb-20260725.json `
  --output 04_evaluation/results/step-hill-climb-20260725.png
```

The presentation plot orders the packages as teacher baseline, SFT, reasoning teacher, and RFT. Its vertical axis is the documented composite success index; the model packages are on the horizontal axis. Each stage also shows the measured quality, P50 latency, and token cost so the weighting remains auditable.

## Decision Rules

RFT is declared the preregistered winner over SFT only when all required conditions hold:

- Mean paired score improvement is at least `0.05`.
- The paired 95% bootstrap confidence interval excludes zero.
- RFT dominant-pattern share is below `0.80`.
- RFT all-defer share is below `0.80`.

Cost and latency are reported as trade-offs, not silently folded into this frozen quality gate. A production decision should define explicit budgets for P95 latency and cost per scenario before looking at the final results.

## Historical Results

The checked-in historical reports predate detailed telemetry. They contain prompt and completion totals but cannot provide latency or split completion tokens into reasoning and visible output after the fact:

| Arm | Mean score | Feasible | Input tokens | Output tokens |
|---|---:|---:|---:|---:|
| Teacher | 0.3465 | 43.3% | 138,086 | 71,746 |
| RFT | 0.8259 | 98.0% | 138,086 | 952,141 |

These runs show the quality difference and total token trade-off, but they are insufficient for the complete step hill-climb plot. Rerun teacher, SFT, and RFT together with the instrumented evaluator and explicit pricing. If an older progress checkpoint is resumed, `telemetry_complete` remains false; remove that checkpoint and rerun the arm when complete latency and reasoning data are required.