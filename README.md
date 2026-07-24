# Supply-Chain Allocation Recovery Showcase

This project compares SFT and RFT models on a disrupted order-fulfillment problem. Given affected orders and current warehouse conditions, each model creates a recovery plan that selects the warehouse, SKU or approved substitute, quantity, and shipping mode for every order. A deterministic grader validates and scores each plan.

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

This is normally a solver-style optimization problem. Here it provides a controlled comparison: SFT learns from high-quality teacher plans, while RFT learns directly from the business-outcome grader. The grader remains the authority for hard constraints and plan quality.

## Explore The Implementation

- [Baseline teacher](01_baseline_teacher/README.md): model, full policy prompt, and best-of-three label capture.
- [Dataset build](02_dataset_build/README.md): conversion of teacher traces into SFT and RFT fine-tuning datasets.
- [Fine-tuning](03_finetuning/README.md): managed SFT/RFT submission, monitoring, and model deployment.
- [Held-out evaluation](04_evaluation/README.md): paired quality, token cost, latency, and hill-climb comparison.
- [Experiment runbook](RUNBOOK.txt): dataset generation, fine-tuning, deployment, and evaluation.
- [Comparison application](model_comparison_app/README.md): run the interactive SFT, RFT, and teacher comparison.