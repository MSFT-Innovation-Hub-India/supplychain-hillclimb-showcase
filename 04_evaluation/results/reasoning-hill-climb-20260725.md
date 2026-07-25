# Reasoning Hill-Climb Evaluation

All four arms below were evaluated on the same 150 deterministic scenarios (`50_000` through `50_149`). The July 24 default teacher, SFT, and RFT results are preserved in `evaluation-20260724-225229.json`; the July 25 teacher-medium result is preserved in `evaluation-20260725-130458.json`.

One **scenario** is one complete model request to produce a coordinated recovery plan for 12-16 orders across three warehouses (one disrupted), subject to SKU inventory, shipment capacity, delivery-time, substitution, quantity, and shared expedite-budget constraints.

## Results

| Arm | Reasoning level | Quality | Feasible | Mean time/scenario | P50 / P95 latency | Avg reasoning tokens | Token cost/scenario | Hosting cost/scenario** |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Teacher, previous run and original prompt | Default / not set | 0.3353 | 42.67% | 4.73 s | 4.54 s / 5.59 s | 0.0 | $0.00858 | N/A |
| Teacher, current run and strengthened prompt | **Medium (explicit)** | **0.8515** | 99.33% | 82.50 s | 66.68 s / 188.69 s | 6,463.4 | $0.09975 | N/A |
| SFT | Default / not set | 0.3132 | 38.67% | 4.14 s | 4.18 s / 4.68 s | 0.0 | $0.00119 | $0.00196 |
| RFT | Medium configured* | 0.8332 | 100.00% | 61.73 s | 58.59 s / 100.53 s | 6,294.2 | $0.03101 | $0.02915 |

\* The RFT fine-tuning configuration used medium reasoning, but the historical evaluator did not persist an explicit inference-time effort field.

\** SFT and RFT use fine-tuned Global Standard deployments with a `$1.70/hour` hosting fee. Evaluation-time allocation is `$1.70 × mean scenario seconds / 3,600`. Hosting accrues while deployed, including idle time, so production cost per scenario depends on throughput. The token rates are Global prices: o4-mini `$1.10/$0.28/$4.40`, GPT-4.1-mini `$0.40/$0.10/$1.60`, and GPT-5.2 `$1.75/$0.18/$14.00` per million input/cached-input/output tokens.

Teacher-medium returned 149 feasible plans and one capacity-invalid plan. Its feasible-plan averages were 0.958 service, 0.966 retained margin, and 0.414 cost efficiency.

## Paired Comparisons

| Comparison | Mean quality difference | Paired bootstrap 95% CI |
|---|---:|---:|
| Teacher-medium minus default teacher | +0.5161 | [0.4519, 0.5778] |
| Teacher-medium minus SFT | +0.5383 | [0.4735, 0.5989] |
| Teacher-medium minus RFT | **+0.0183** | **[0.0026, 0.0294]** |

Teacher-medium narrowly but statistically consistently beat RFT on this fixed split. The operational trade-off is unfavorable: teacher-medium had 13.8% higher P50 latency, 87.7% higher P95 latency, and approximately 3.2 times the estimated inference cost per scenario.

## Interpretation Limits

The default-to-medium teacher comparison changes two factors together: the shared policy prompt was strengthened and reasoning was changed from implicit default to explicit medium. It demonstrates the improvement of the complete teacher package, not the isolated causal effect of reasoning effort. A clean reasoning-only attribution would require rerunning the strengthened prompt with no explicit reasoning on the same 150 scenarios.

The RFT report did not persist an explicit inference-time `reasoning_effort` field because it predates per-arm reasoning metadata. It did record an average of 6,294 hidden reasoning tokens per scenario, and its fine-tuning configuration used medium reasoning. Treat the comparison as an operational package comparison rather than a perfectly controlled model-method experiment.

The one-scenario high-reasoning smoke test scored the same 0.878 as medium but took 71.6 seconds and 3,803 reasoning tokens, versus 38.5 seconds and 2,625 reasoning tokens for medium. High was therefore abandoned before a complete run.