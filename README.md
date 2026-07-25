# Supply-Chain Allocation Recovery Showcase

This project explores how language models can create recovery plans for disrupted order fulfillment. Given affected orders and current warehouse conditions, a model selects the warehouse, SKU or approved substitute, quantity, and shipping mode for every order. Each plan is then validated and scored against operational constraints and business outcomes.

## Business Scenario

When a warehouse, carrier, or inventory source is disrupted, orders must be reassigned quickly without breaking customer commitments or operational limits. Decisions cannot be made one order at a time: reserving scarce inventory or fast capacity for one order can prevent a higher-priority order from being fulfilled.

## Enterprise Inputs

In production, an upstream process would detect at-risk orders from an OMS event or order file and query dependent systems:

| System | Required data |
|---|---|
| OMS | Orders, quantities, deadlines, priority, margin |
| WMS | Warehouse status, inventory, shipment capacity |
| TMS | Transit times, shipping modes, freight costs |
| Product/SLA systems | Approved substitutes, customer commitments |
| Finance | Expedite budget |

These integrations are not implemented here; the project generates equivalent scenario data.

## Sample Planning Data

An upstream pipeline would start with the affected orders, retrieve related data from the systems above, and assemble a planning snapshot like this:

**Orders**

| Order | SKU / Qty | Priority | Deadline | Alternate |
|---|---:|---:|---:|---|
| O1 | A / 3 | High | 30 hrs | A2 |
| O2 | B / 1 | Medium | 18 hrs | B2 |
| O3 | C / 1 | Low | 30 hrs | None |

**Supporting data**

| Warehouse | Relevant stock | Capacity | Standard | Expedite |
|---|---|---:|---|---|
| W1 | A: 2, B: 2, C: 1 | 3 | 30 hrs / $5 | 8 hrs / $15 |
| W2 | A: 4, B: 4, C: 4 | 5 | 18 hrs / $9 | 16 hrs / $17 |

Expedite budget: **$45**.

The planning engine must coordinate stock and capacity across warehouses, use alternates only when approved, and choose another warehouse or defer when one location cannot fulfill an order in full. It must also balance priority, deadline, transit time, delivery mode, margin, and cost without exceeding the expedite budget.

**Resulting recovery plan**

| Order | Decision | Why |
|---|---|---|
| O1 | W2, SKU A, standard | W1 has only 2 of the 3 units required |
| O2 | W2, SKU B, standard | W2 meets the tighter 18-hour deadline without expedite |
| O3 | W1, SKU C, standard | The 30-hour deadline allows the lower-cost warehouse |

The engine first eliminates options that fail inventory, capacity, quantity, substitution, deadline, or budget checks. It then compares the feasible plans, reserves fast capacity for constrained orders, and selects the lowest-cost plan that preserves service and margin. This plan fulfills all orders on time for **$41**, with no substitute or expedite spend.

## Planning Flow

1. Detect orders at risk.
2. Gather and reconcile current operational data.
3. Ask the model for one coordinated order-fulfillment recovery plan.
4. Validate inventory, capacity, quantity, substitution, timing, and budget constraints.
5. Score feasible plans on service, retained margin, and shipping cost.

## Why It Is Difficult

Many plans may be feasible, but only some use scarce inventory, capacity, and expedite budget effectively. The number of combinations grows across orders, warehouses, SKUs, substitutes, and shipping modes, and every decision affects what remains available to other orders.

## Approach To The Solution

An optimization solver would typically be used for this problem. This showcase instead considers how far a language model can address it. The starting point was a general-purpose LLM supplied with the domain rules, required output schema, hard constraints, and business objective in its instructions. Every generated plan was measured on three dimensions:

- **Quality:** feasibility, priority-weighted on-time service, retained margin, and shipping-cost efficiency.
- **Latency:** end-to-end time required to produce one complete recovery plan.
- **Cost:** model input, output, and reasoning-token charges, with fine-tuned hosting reported separately.

### Hill-Climbing The Model Package

Here, **hill-climbing the model package** means testing successive combinations of model, prompt, reasoning, and fine-tuning method to improve the overall balance of plan quality, latency, and cost. The experiment progressed through four packages:

Microsoft Foundry's model support constrained the available choices: at the time of the experiment, the same base model could not be used for both supervised fine-tuning (SFT) and reinforcement fine-tuning (RFT). SFT therefore used `gpt-4.1-mini`, while grader-based RFT used `o4-mini`. The results compare deployable model-and-method packages, not SFT and RFT while holding the base model constant.

1. **Teacher baseline:** GPT-5.2 received the domain instructions without explicit reasoning. It was fast, but frequently violated coupled inventory, capacity, and budget constraints.
2. **Knowledge distillation with SFT:** GPT-5.2 generated candidate labeled plans for GPT-4.1-mini. A plan was eligible as training data only when the deterministic scorer found it feasible and assigned a quality score of at least `0.75`. This execution filtering produced 148 training and 38 validation demonstrations. SFT taught the smaller model to imitate those selected teacher answers, reducing cost but not improving held-out quality in this run.
3. **Reasoning teacher:** strengthened instructions and medium reasoning raised GPT-5.2 quality substantially, but also increased latency and token cost.
4. **RFT:** o4-mini received scenarios but no labeled target plans. During training it sampled candidate plans, the grader returned a reward from `0` to `1`, and Foundry's managed policy-gradient optimization used those rewards to update model weights so higher-reward behavior became more likely and lower-reward behavior became less likely.

### Why RFT Used A Grader

There can be several valid recovery plans for one disruption, so forcing the model to reproduce one teacher answer would discard other good strategies. The grader instead evaluates the outcome. It first enforces all hard constraints: malformed plans, missing or duplicate orders, unavailable warehouses, incorrect quantities, prohibited substitutes, exhausted inventory or capacity, invalid shipping modes, and excess expedite spend receive zero reward. A feasible plan then receives continuous credit:

$$
Q = 0.55S + 0.25M + 0.20C_e
$$

Here, $S$ is priority-weighted on-time service, $M$ is retained margin, and $C_e$ is fulfillment-adjusted shipping-cost efficiency. This gives RFT more information than a pass/fail label and directly aligns training with the measured business objective.

For example, in the sample scenario, order O1 needs three units of SKU A while W1 has only two. A candidate that ships O1 from W1 receives zero reward because it exceeds inventory, regardless of how attractive the rest of the plan looks. Shipping O1 from W2 is feasible. For O2, W2 standard delivery meets the tighter 18-hour deadline, so choosing standard preserves service while avoiding unnecessary expedite cost. Across the complete plan, the grader also checks that assigning these orders has not exhausted W2 capacity or the shared expedite budget needed by another constrained order. Rewards therefore steer the model toward the right warehouse, SKU or approved substitute, shipping mode, and globally feasible allocation rather than merely the right JSON shape.

### Workload And Latency Context

The evaluated requests were materially larger than the simplified three-order example above:

- **Orders:** 12–16 per scenario, averaging `14.02`, with quantity, deadline, priority, margin, and approved substitute data.
- **Supporting data:** three warehouses with availability, capacity, transit times, standard and expedite costs, inventory for six SKUs, and one shared expedite budget.
- **Scenario payload:** approximately 2.3K characters of JSON.
- **Model input:** approximately 1.1K tokens per baseline, SFT, and RFT request; the strengthened teacher prompt increased this to approximately 1.5K tokens.

Reasoning output, rather than input size alone, dominated the slower runs. The medium-reasoning teacher generated an average of 6,463 hidden reasoning tokens per scenario, with P50 latency rising from 4.54 seconds for the non-reasoning teacher to 66.68 seconds. RFT inference generated an average of 6,294 hidden reasoning tokens and had a P50 latency of 58.59 seconds. Because these packages use different model families and prompts, the measurements describe the complete packages rather than isolating the causal cost of reasoning.

### Measured Hill Climb

![Supply-chain model step hill climb](04_evaluation/results/step-hill-climb-20260725.png)

The chart combines quality (70%), inverse token cost (15%), and inverse P50 latency (15%) into a documented composite index, while retaining the measured components under every step. SFT made the package cheaper and slightly faster, but its quality regression meant it was not an upward step overall. Medium reasoning produced the major quality gain. RFT then reached `0.833` quality and 100% feasibility, closely matching the `0.851` reasoning teacher while reducing P50 latency from `66.68` to `58.59` seconds and token cost from `$0.09975` to `$0.03101` per scenario. In this experiment, RFT was therefore the strongest operational balance rather than the absolute highest-quality model.

See the [held-out evaluation](04_evaluation/README.md) for the complete methodology, confidence intervals, feasibility analysis, latency distribution, token accounting, hosting-cost assumptions, and experiment limitations.

### Microsoft Foundry And Code-First Execution

Microsoft Foundry provides a streamlined, managed end-to-end platform for the workflow used here: preparing and uploading datasets, configuring SFT and RFT jobs, attaching a grader, monitoring training and validation metrics, deploying fine-tuned models, and evaluating the resulting endpoints. These steps can be performed in the Foundry portal.

For this showcase, GitHub Copilot agent mode in Visual Studio Code was used to perform the workflow through a code-first approach. The repository makes the prompts, dataset transformations, grader, job payloads, deployment scripts, evaluation logic, and resulting artifacts reviewable and repeatable while Foundry supplies the managed training and model-hosting infrastructure.

## Explore The Implementation

- [Baseline teacher](01_baseline_teacher/README.md): model, full policy prompt, and best-of-three label capture.
- [Dataset build](02_dataset_build/README.md): conversion of teacher traces into SFT and RFT fine-tuning datasets.
- [Fine-tuning](03_finetuning/README.md): managed SFT/RFT submission, monitoring, and model deployment.
- [Held-out evaluation](04_evaluation/README.md): paired quality, token cost, latency, and hill-climb comparison.
- [Experiment runbook](RUNBOOK.txt): dataset generation, fine-tuning, deployment, and evaluation.
- [Comparison application](model_comparison_app/README.md): run the interactive SFT, RFT, and teacher comparison.