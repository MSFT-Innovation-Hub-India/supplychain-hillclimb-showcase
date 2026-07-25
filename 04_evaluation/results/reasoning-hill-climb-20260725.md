# Reasoning Hill-Climb Evaluation

All four arms below were evaluated on the same 150 deterministic scenarios (`50_000` through `50_149`). The July 24 default teacher, SFT, and RFT results are preserved in `evaluation-20260724-225229.json`; the July 25 teacher-medium result is preserved in `evaluation-20260725-130458.json`.

## Results

| Arm | Reasoning level | Quality | Feasible | P50 / P95 latency | Avg reasoning tokens | Estimated cost/scenario |
|---|---|---:|---:|---:|---:|---:|
| Teacher, previous run and original prompt | Default / not set | 0.3353 | 42.67% | 4.54 s / 5.59 s | 0.0 | $0.0086 |
| Teacher, current run and strengthened prompt | **Medium (explicit)** | **0.8515** | 99.33% | 66.68 s / 188.69 s | 6,463.4 | $0.0997 |
| SFT | Default / not set | 0.3132 | 38.67% | 4.18 s / 4.68 s | 0.0 | $0.0012 |
| RFT | Medium configured* | 0.8332 | 100.00% | 58.59 s / 100.53 s | 6,294.2 | $0.0310 |

\* The RFT fine-tuning configuration used medium reasoning, but the historical evaluator did not persist an explicit inference-time effort field.

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