# Dataset Build

This offline stage runs after baseline teacher capture and before fine-tuning. It converts the common teacher trace into the different JSONL formats required by SFT and RFT.

```text
Teacher trace -> Dataset build -> SFT/RFT training and validation files -> Fine-tuning jobs
```

## Input

[training.jsonl](../01_baseline_teacher/traces/training.jsonl) contains the fixed scenario, selected teacher plan, grader result, split, and SFT eligibility flag for each captured case.

## Transformation

[build_datasets.py](build_datasets.py) applies the shared policy prompt from `common.prompts` and preserves the original train/validation split.

| Dataset | What one row contains | Selection rule |
|---|---|---|
| SFT | Policy prompt + scenario + teacher plan as the assistant answer | Only feasible teacher plans meeting the quality threshold |
| RFT | Policy prompt + scenario + structured scenario in `expected` for grading | Every captured scenario |

SFT learns to imitate selected teacher answers. RFT receives no target answer; it generates plans during training and receives reward from the grader.

## Scenario Families

The generator uses three families: `loose`, `mixed`, and `tight`. Every scenario has 12-16 orders, three warehouses, and one unavailable warehouse. The family controls expedite-budget pressure:

| Family | Pressure | Meaning |
|---|---:|---|
| `loose` | 0.75 | More expedite budget relative to active capacity |
| `mixed` | 1.00 | Baseline expedite budget |
| `tight` | 1.25 | Less expedite budget; tradeoffs are harder |

The budget formula is:

$$
B=\max\left(45,\left\lfloor\frac{5A}{p}\right\rfloor\right)
$$

Here, $A$ is active warehouse capacity and $p$ is the family pressure. For an active capacity of 40, the budgets are approximately **$266 loose**, **$200 mixed**, and **$160 tight**. Other values such as orders, inventory, deadlines, and costs are generated from the scenario seed rather than directly controlled by the family.

**Actual dataset distribution**

| Dataset | Loose | Mixed | Tight | Total |
|---|---:|---:|---:|---:|
| RFT train | 100 (33.3%) | 100 (33.3%) | 100 (33.3%) | 300 |
| RFT validation | 20 (33.3%) | 20 (33.3%) | 20 (33.3%) | 60 |
| SFT train | 57 (38.5%) | 46 (31.1%) | 45 (30.4%) | 148 |
| SFT validation | 14 (36.8%) | 10 (26.3%) | 14 (36.8%) | 38 |

RFT retains the generator's equal 1:1:1 rotation. SFT keeps only feasible teacher plans above the quality threshold, so its final family ratio is not exactly balanced.

## How An RFT Row Is Used

One row in [rft_train.jsonl](data/rft_train.jsonl) has this structure:

```json
{
	"messages": [
		{
			"role": "developer",
			"content": "<POLICY, CONSTRAINTS, OBJECTIVE AND OUTPUT FORMAT>"
		},
		{
			"role": "user",
			"content": "Produce the best feasible allocation plan for this scenario:\n<SCENARIO_AS_JSON_TEXT>"
		}
	],
	"expected": {
		"scenario": "<SAME_SCENARIO_AS_A_STRUCTURED_JSON_OBJECT>"
	}
}
```

The JSONL file escapes newlines because `content` must be a string. The same row is easier to understand when its values are expanded below.

**Developer `content`**

```text
You are a disruption-recovery planner. Return JSON only.
Return exactly {"decisions":[...]}. Include every order exactly once.
A defer decision is {"order_id":"...","action":"defer"}.
A ship decision is {"order_id":"<order_id>","action":"ship","warehouse_id":"<warehouse_id>","sku":"<sku>","quantity":<quantity>,"shipping_mode":"<standard_or_expedite>"}.
Use only available warehouses, requested or approved substitute SKUs, exact order quantities, and standard/expedite modes.

Business rules:
- An order is on time when the selected shipping mode's delivery hours do not exceed the order's deadline hours.
- On-time delivery earns full service value and margin. Late delivery has reduced business value, so prioritize on-time delivery for higher-priority orders.
- An approved substitute SKU may be used when necessary, but it retains slightly less value than the requested SKU.
- Partial shipments are not allowed. A shipped order must use its exact requested quantity.
- Shipped quantity consumes both SKU inventory and warehouse shipment capacity.
- Expedite spending is expedited unit cost multiplied by shipped quantity and must remain within the scenario's expedite budget.
- Deferring an order earns no service or margin, but may be necessary to keep the overall plan feasible.
- Using an unavailable warehouse, exceeding inventory or capacity, using a prohibited substitute, shipping an incorrect quantity, or exceeding the expedite budget invalidates the entire plan.
- Among feasible plans, prioritize on-time service, then retained margin, while avoiding unnecessary shipping cost.

Produce the best feasible plan after checking all inventory, capacity, delivery-time, substitution, quantity, and budget constraints across the complete set of decisions.
```

**Scenario contained in the user `content`**

The user message starts with `Produce the best feasible allocation plan for this scenario:` and then contains scenario JSON. This shortened representative scenario uses the same schema as the 12-16 order training cases:

```json
{
	"scenario_id": "sample-tight-scenario",
	"family": "tight",
	"orders": [
		{"order_id": "O1", "sku": "A", "quantity": 3, "priority": 3, "deadline_hours": 30, "substitute_sku": "A2", "margin": 114},
		{"order_id": "O2", "sku": "B", "quantity": 1, "priority": 2, "deadline_hours": 18, "substitute_sku": "B2", "margin": 80},
		{"order_id": "O3", "sku": "C", "quantity": 1, "priority": 1, "deadline_hours": 30, "substitute_sku": null, "margin": 92}
	],
	"warehouses": [
		{
			"warehouse_id": "W1",
			"available": true,
			"inventory": {"A": 2, "A2": 0, "B": 2, "B2": 5, "C": 1},
			"shipment_capacity": 3,
			"standard_hours": 30,
			"standard_cost": 5,
			"expedite_hours": 8,
			"expedite_cost": 15
		},
		{
			"warehouse_id": "W2",
			"available": true,
			"inventory": {"A": 4, "A2": 0, "B": 4, "B2": 4, "C": 4},
			"shipment_capacity": 5,
			"standard_hours": 18,
			"standard_cost": 9,
			"expedite_hours": 16,
			"expedite_cost": 17
		}
	],
	"expedite_budget": 45
}
```

In the actual row, this JSON is serialized inside the user `content` string. The identical JSON object is also stored under `expected.scenario`; it is not escaped there and is visible only to the grader.

The two scenario copies serve different consumers:

- `messages` is visible to the model. The developer message explains how to interpret the fields, all hard constraints, business priorities, and the required `{"decisions": [...]}` response. The user message supplies the scenario as text.
- `expected.scenario` is private grader context. It is a JSON object, not the model's target answer, and lets the grader validate the generated plan without parsing the user message.

During RFT, the loop is:

1. The model reads `messages` and generates a fulfillment plan in the required response schema.
2. The [grader](../03_finetuning/rft/grader.json) compares that plan with `expected.scenario`.
3. Invalid plans receive `0`; feasible plans receive a reward based on on-time service, retained margin, and shipping cost.
4. RFT updates the model toward actions that earn higher reward across repeated scenarios.

## How The Grader Calculates Reward

Hard-constraint failures receive a score of **0**. These include invalid output, missing or duplicate orders, unavailable warehouses, incorrect quantities, prohibited substitutes, inventory or capacity overuse, and exceeding the expedite budget.

For a feasible plan, the grader calculates three normalized components:

$$
S=\frac{P_{on\mbox{-}time}}{P_{total}}
$$

$$
M=\frac{M_{retained}}{M_{total}}
$$

Exact-SKU, on-time delivery retains full margin. A substitute retains 90%; a late shipment retains 50% of the otherwise retained margin. Deferred orders earn no service or margin.

$$
C=F\times\max\left(0,1-\frac{K}{15Q}\right)
$$

Here, $F$ is the fulfilled-order fraction, $K$ is shipping cost, and $Q$ is total ordered quantity.

The final reward is:

$$
R=0.55S+0.25M+0.20C
$$

Thus, service is most important, followed by retained margin and cost efficiency. See the authoritative implementation in [common/scoring.py](../common/scoring.py).

## How The Model Knows The Criteria

The criteria are explicitly stated in the shared [policy prompt](../common/prompts.py): inventory, capacity, exact quantity, approved substitutions, deadlines, priority, expedite budget, margin, and cost. The model therefore knows what each scenario field means and which outcomes to prefer.

The exact numerical weights are intentionally grader-side: **55% service, 25% margin, and 20% cost**. RFT does not need those constants in the prompt; it learns their practical effect from reward. Keeping qualitative goals visible and exact scoring logic in the grader prevents the task from becoming direct formula execution while still giving the model enough guidance to explore sensible plans.

## Outputs

- [sft_train.jsonl](data/sft_train.jsonl) and [sft_valid.jsonl](data/sft_valid.jsonl)
- [rft_train.jsonl](data/rft_train.jsonl) and [rft_valid.jsonl](data/rft_valid.jsonl)

Each line is one complete training or validation example. The files are deterministic rebuilds of the captured trace, not new model-generated data.

## How Train And Validation Enter The RFT Job

[submit_rft_job.py](../03_finetuning/rft/submit_rft_job.py) uploads both files and receives a file ID for each. Those IDs are placed directly in the managed fine-tuning request:

```json
{
	"training_file": "<ID_FROM_RFT_TRAIN_UPLOAD>",
	"validation_file": "<ID_FROM_RFT_VALID_UPLOAD>",
	"method": {
		"type": "reinforcement",
		"reinforcement": {
			"grader": "<GRADER_DEFINITION>",
			"response_format": "<PLAN_SCHEMA>",
			"hyperparameters": {
				"eval_interval": 5,
				"eval_samples": 10
			}
		}
	}
}
```

- `rft_train.jsonl` supplies scenarios used by the managed RFT service to generate rewards and update model weights.
- `rft_valid.jsonl` supplies held-out scenarios for periodic evaluation; it does not update model weights.

The repository does not implement the training or validation loop itself. It prepares and uploads the files, grader, response schema, and hyperparameters; the Azure fine-tuning service consumes them and runs the managed job.

## What Happens Next

1. Build and verify the RFT grader.
2. Upload the SFT train/validation files to the supervised fine-tuning job.
3. Upload the RFT train/validation files with the grader and response schema to the reinforcement fine-tuning job.
4. Deploy the completed models and evaluate them on the same held-out scenarios.

Fine-tuning is implemented under [03_finetuning](../03_finetuning/); commands and safeguards are listed in the [runbook](../RUNBOOK.txt).
