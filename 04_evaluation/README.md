# Held-Out Evaluation

This stage compares teacher, SFT, and RFT deployments on the same deterministic 150-scenario test split. It records the three dimensions needed for the showcase's hill climb:

- **Quality:** deterministic plan score, feasibility, service, retained margin, cost efficiency, and failure modes.
- **Cost:** input, cached-input, output, reasoning, and visible-output tokens, plus an optional USD estimate based on rates supplied at run time.
- **Latency:** end-to-end model-call duration for every scenario and aggregate mean, P50, P95, minimum, and maximum.

The test scenarios start at seed `50_000` and rotate through tight, mixed, and loose families. They do not overlap the training or validation splits. Every arm receives the same scenario objects in the same order, enabling paired comparisons.

The latest complete run is documented in [Teacher vs SFT vs RFT Evaluation Results](results/evaluation-20260724-225229.md), with links to its raw JSON report and hill-climb chart.

## Latest Complete Results

The July 24, 2026 run evaluated each arm on the same 150 held-out scenarios:

| Arm | Quality | Feasible | P50 / P95 latency | Avg input | Avg output | Avg reasoning | Estimated cost/scenario |
|---|---:|---:|---:|---:|---:|---:|---:|
| Teacher | 0.335 | 42.7% (64/150) | 4.54 s / 5.59 s | 1,123.6 | 472.2 | 0.0 | $0.0086 |
| SFT | 0.313 | 38.7% (58/150) | 4.18 s / 4.68 s | 1,124.6 | 466.8 | 0.0 | $0.0012 |
| RFT | **0.833** | **100% (150/150)** | 58.59 s / 100.53 s | 1,123.6 | 6,768.0 | 6,294.2 | $0.0310 |

**Feasibility** is the percentage of scenarios where the model returned a valid, executable plan that satisfied schema, order coverage, inventory, capacity, substitution, quantity, warehouse, shipping-mode, and expedite-budget constraints. Feasibility does not guarantee a high-value plan; for example, deferring every order can be feasible while earning zero quality.

**Quality** is the mean deterministic business score over all 150 scenarios, including a zero for every infeasible plan. It combines priority-weighted on-time service, retained margin, and fulfillment-adjusted cost efficiency:

$$
Q = 0.55S + 0.25M + 0.20C_e
$$

RFT beat SFT by 0.520 quality points with a paired bootstrap 95% confidence interval of `[0.461, 0.580]`, and passed all preregistered RFT winner criteria. Its quality gain came with substantially higher reasoning-token usage, latency, and estimated inference cost.

## Run The Evaluation

Review the current Azure pricing for each deployed model, then pass the input and output rates in USD per one million tokens. Add a third rate only when cached input has a different price.

```powershell
.\.venv\Scripts\python.exe 04_evaluation/evaluate.py `
  --arm teacher=TEACHER_DEPLOYMENT `
  --arm sft=SFT_DEPLOYMENT `
  --arm rft=RFT_DEPLOYMENT `
  --pricing teacher=TEACHER_INPUT_RATE,TEACHER_OUTPUT_RATE,TEACHER_CACHED_INPUT_RATE `
  --pricing sft=SFT_INPUT_RATE,SFT_OUTPUT_RATE,SFT_CACHED_INPUT_RATE `
  --pricing rft=RFT_INPUT_RATE,RFT_OUTPUT_RATE,RFT_CACHED_INPUT_RATE `
  --count 150 `
  --compare rft,sft `
  --confirm-paid
```

Pricing is explicit because Azure prices vary by model, deployment type, and date. Omitting `--pricing` still records tokens, but the corresponding cost estimate and cost-based plot are unavailable. The evaluator blocks live calls unless `--confirm-paid` is present.

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
.\.venv\Scripts\python.exe 04_evaluation/plot_hill_climb.py `
  04_evaluation/results/evaluation-YYYYMMDD-HHMMSS.json `
  --output 04_evaluation/results/hill-climb.png
```

The plot uses quality on the vertical axis, P50 latency on the horizontal axis, and bubble area for estimated cost per scenario. Arrows follow the `--arm` order. This preserves the competing dimensions rather than hiding them inside an arbitrary composite score: upward is better quality, leftward is lower latency, and a smaller bubble is lower cost.

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

These runs show the quality difference and total token trade-off, but they are insufficient for the complete hill-climb plot. Rerun teacher, SFT, and RFT together with the instrumented evaluator and explicit pricing. If an older progress checkpoint is resumed, `telemetry_complete` remains false; remove that checkpoint and rerun the arm when complete latency and reasoning data are required.