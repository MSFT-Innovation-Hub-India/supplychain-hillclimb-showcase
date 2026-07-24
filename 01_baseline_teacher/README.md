# Baseline Teacher

This stage creates the high-quality starting examples used by the SFT and RFT workflows.

## Role In The End-To-End Flow

`01_baseline_teacher` is an **offline experiment-preparation module**. It is used before dataset construction and fine-tuning, not when the deployed SFT or RFT model handles a planning request.

```text
Generate scenarios -> Pilot teacher/grader -> Capture teacher traces
-> Build SFT/RFT datasets -> Fine-tune -> Evaluate and deploy
```

The module is used in two phases:

1. **Pilot:** run a small scenario set and confirm that the task has useful reward variation and sufficient improvement headroom.
2. **Capture:** after the pilot gate passes, generate the fixed teacher traces from which both fine-tuning datasets are built.

## Module Map

| File | Responsibility |
|---|---|
| `capture_pilot.py` | Runs the billable go/no-go pilot and writes all candidate attempts to `traces/pilot.jsonl` |
| `analyze_pilot.py` | Measures feasibility, reward variation, and output diversity; writes the gate decision to `traces/pilot_gate.json` |
| `capture_training.py` | Creates fixed train/validation scenarios and writes selected teacher results to `traces/training.jsonl` |
| `traces/*.jsonl` | Append-only evidence containing scenarios, model plans, grader results, and usage data |

The scripts reuse the shared `common` package so every stage applies the same contract:

- `common.scenario` generates deterministic scenario splits.
- `common.prompts` supplies the policy prompt and serializes each scenario.
- `common.model_client` invokes the configured Azure model deployment.
- `common.scoring` validates and scores returned plans.
- `common.fine_tuning_api` enforces paid-run and pilot-gate safeguards where required.

This shared boundary prevents teacher capture, dataset creation, and later evaluation from silently using different business rules.

## Teacher Model

This sample used the **gpt-5.2** deployment as the teacher. For each generated scenario, the teacher produces three candidate fulfillment plans. The deterministic grader scores them, and the highest-scoring plan is retained.

This is a best-of-three selection step, not an iterative hill-climbing loop. It establishes a strong baseline before fine-tuning.

<a id="full-policy-prompt"></a>

## Full Policy Prompt

The teacher receives the scenario data together with this system prompt from `common/prompts.py`:

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

The prompt is intentionally detailed: it gives the teacher the output contract, hard constraints, and business priorities needed to produce useful labels.

## Sample Input And Output

JSON is used because it matches the actual model contract, preserves data types, and makes the returned plan easy to validate. This simplified example uses the three-order showcase scenario; captured training scenarios contain 12-16 orders.

<a id="sample-scenario-json"></a>

**Input scenario sent after the policy prompt**

```json
{
	"scenario_id": "balanced-three-order-demo",
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

**Representative teacher output**

```json
{
	"decisions": [
		{"order_id": "O1", "action": "ship", "warehouse_id": "W2", "sku": "A", "quantity": 3, "shipping_mode": "standard"},
		{"order_id": "O2", "action": "ship", "warehouse_id": "W2", "sku": "B", "quantity": 1, "shipping_mode": "standard"},
		{"order_id": "O3", "action": "ship", "warehouse_id": "W1", "sku": "C", "quantity": 1, "shipping_mode": "standard"}
	]
}
```

The teacher returns only the plan. The capture process separately stores the scenario, score, feasibility result, token usage, and selected attempt in the training trace.

## Outputs

- `capture_pilot.py` tests whether the teacher and grader are suitable for the experiment.
- `capture_training.py` generates train/validation scenarios, captures three candidates, and stores the best candidate in `traces/training.jsonl`.
- Plans are marked usable for SFT only when feasible and above the configured score threshold.
- The captured scenarios and plans are transformed by `02_dataset_build/build_datasets.py` into separate SFT and RFT training/validation datasets. These datasets are the direct inputs submitted to the respective SFT and RFT fine-tuning jobs.

## Why Capture Is Needed

Capture creates a reproducible record of how the teacher responds to each fixed scenario before fine-tuning begins. For every scenario it:

1. requests three candidate plans from the teacher;
2. grades each candidate with the same deterministic business scorer;
3. retains the highest-scoring plan; and
4. stores the scenario, plan, score, feasibility, token usage, and selected attempt.

The resulting traces serve two purposes: the retained teacher plan becomes the target answer for SFT, while the scenario without that answer becomes an RFT item scored by the grader during training. Fixed train and validation splits make both methods comparable and allow the capture process to resume safely without regenerating completed scenarios.

## Training Items Produced

For readability, the examples use these placeholders:

- [`<FULL_POLICY_PROMPT>`](#full-policy-prompt) refers to the complete system prompt.
- [`<SCENARIO_JSON>` / `<SAME_STRUCTURED_SCENARIO_USED_IN_THE_USER_MESSAGE>`](#sample-scenario-json) refer to the same complete sample scenario: serialized in the user message and copied as a structured object into `expected.scenario` for the grader.

**Sample SFT dataset row** - this represents one JSONL training example in [sft_train.jsonl](../02_dataset_build/data/sft_train.jsonl). It includes the teacher plan as the answer to imitate:

```json
{
	"messages": [
		{"role": "developer", "content": "<FULL_POLICY_PROMPT>"},
		{"role": "user", "content": "Produce the best feasible allocation plan for this scenario:\n<SCENARIO_JSON>"},
		{
			"role": "assistant",
			"content": "{\"decisions\":[{\"order_id\":\"O1\",\"action\":\"ship\",\"warehouse_id\":\"W2\",\"sku\":\"A\",\"quantity\":3,\"shipping_mode\":\"standard\"},{\"order_id\":\"O2\",\"action\":\"ship\",\"warehouse_id\":\"W2\",\"sku\":\"B\",\"quantity\":1,\"shipping_mode\":\"standard\"},{\"order_id\":\"O3\",\"action\":\"ship\",\"warehouse_id\":\"W1\",\"sku\":\"C\",\"quantity\":1,\"shipping_mode\":\"standard\"}]}"
		}
	]
}
```

**Sample RFT dataset row** - this represents one JSONL training example in [rft_train.jsonl](../02_dataset_build/data/rft_train.jsonl). It omits the target answer; the grader uses `expected.scenario` to score plans generated during training:

```json
{
	"messages": [
		{"role": "developer", "content": "<FULL_POLICY_PROMPT>"},
		{"role": "user", "content": "Produce the best feasible allocation plan for this scenario:\n<SCENARIO_JSON>"}
	],
	"expected": {
		"scenario": "<SAME_STRUCTURED_SCENARIO_USED_IN_THE_USER_MESSAGE>"
	}
}
```

The model does not see `expected` as an answer. It is grader context: generated RFT plans are checked against that scenario and receive their numerical reward.

The placeholder is used only to shorten this README example. In the actual [RFT training data](../02_dataset_build/data/rft_train.jsonl), `expected.scenario` contains the full structured scenario object. It is inserted by [build_datasets.py](../02_dataset_build/build_datasets.py).
