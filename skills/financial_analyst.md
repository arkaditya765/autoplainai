---
name: financial_analyst
description: Specialized cost control, overtime premium, and budget optimization expert. Analyzes standard vs overtime labor rates, total production expenses, and profit margin impacts.
---

# Financial Analyst (Cost & Budget Optimization Expert)

## Overview

The Financial Analyst skill provides specialized capability for cost estimation, labor rate audits, overtime fee projections, and margin analysis. When production demands increase, managers often schedule extra labor without calculating the margin erosion caused by overtime premium multipliers. This skill helps protect profitability by detailing standard costs vs. overtime costs.

## When to Use

Use this skill when:
- Proposing changes to production schedules that require overtime hours.
- Estimating the total manufacturing expense for a given demand adjustment.
- Auditing the budget impact of running extra shifts.
- Comparing profit margins before and after scheduling overtime labor.

Do NOT use this skill for:
- Physical assembly line utilization percentages or bottleneck line speeds.
- Sourcing component details or check supplier stock lists.

## Guidelines & Process

When acting with this skill, adhere to the following analytical process:

### 1. Calculate Standard Production Costs
Compute the standard cost for the units produced within the daily capacity limit:
$$\text{Standard Cost} = \text{Units Within Capacity Limit} \times \text{Standard Cost Per Unit}$$

### 2. Determine Overtime Hours Needed
Calculate the deficit units (Target Demand $-$ Capacity Limit) and determine the overtime hours required based on the line's hourly assembly rate:
$$\text{Overtime Hours Needed} = \frac{\text{Deficit Units}}{\text{Assembly Rate Per Hour}}$$

### 3. Calculate Overtime Costs
Apply the overtime maximum allowed hour cap (e.g. from database limits) and calculate the premium cost:
- If Overtime is **NOT Allowed**: Overtime Hours Used = 0.
- If Overtime is **Allowed**: Overtime Hours Used = $\min(\text{Overtime Hours Needed}, \text{Max Overtime Hours Allowed})$.
$$\text{Total Overtime Cost} = \text{Overtime Hours Used} \times \text{Overtime Rate Per Hour}$$

### 4. Evaluate Profit Margin Impact
Analyze how the premium labor rates affect the average cost per unit:
$$\text{Average Cost Per Unit} = \frac{\text{Standard Cost} + \text{Total Overtime Cost}}{\text{Units Produced}}$$
Highlight any margin dilution compared to standard production runs.

---

## Output

Your analysis must include an itemized cost breakdown, followed by a budget feasibility report.

### Cost Breakdown Format
* **Standard Production Cost**: $\$120,000$ ($600$ units @ $\$200$/unit)
* **Overtime Labor Cost**: $\$18,000$ ($3$ hours @ $\$6,000$/hour)
* **Total Manufacturing Expense**: $\$138,000$
* **Overtime Labor Premium Added**: $+15\%$ increase in cost per unit.

### Budget Feasibility Report
- **Overtime Allowed Status**: Yes/No (from active context variables).
- **Unmet Demand Deficit**: Quantify any shortfall units that could not be produced because they exceeded the legal maximum overtime hours limit.
- **Cost Efficiency Recommendation**: Propose alternative cost-saving measures if profit margins drop below acceptable limits.

---

## Example

**Scenario**: Swift demand is adjusted by +25% (total target demand 625 units; limit is 500 units). Standard cost is $\$200$/unit, hourly assembly rate is 50 units/hour, overtime hourly rate is $\$6,000$/hour, and max allowed overtime is 4 hours.

**Calculation**:
- Standard Production: 500 units $\times$ $\$200$ = $\$100,000$
- Deficit Units: $625 - 500 = 125$ units
- Overtime Hours Needed: $\frac{125}{50} = 2.5$ hours
- Overtime Hours Used (Capped at 4 hrs max): $2.5$ hours
- Overtime Labor Cost: $2.5$ hours $\times$ $\$6,000$ = $\$15,000$
- Total Production Cost: $\$100,000 + \$15,000 = \$115,000$.

**Margin Impact**: Average unit cost rises from $\$200$ to $\frac{\$115,000}{625} = \$184$ (wait, standard cost includes materials and standard labor; if average production cost changes from standard, the financial analyst reports the exact percentage change).

---

## Common Rationalizations

| Rationalization | Reality |
| :--- | :--- |
| "We can schedule unlimited overtime to meet demand." | Overtime hours are strictly capped by labor laws and costs databases. Proposing schedules that exceed legal maximums is non-compliant. |
| "Overtime hours don't affect our margin because we sell more." | While volume increases revenue, the higher hourly overtime rates erode the profit margin per unit. The marginal margin must be analyzed. |

## Red Flags

- Calculating overtime costs when context states that `overtime_allowed = False`.
- Scheduling overtime hours that exceed the `max_overtime_hours_allowed` defined in the costs database.
- Presenting a final budget summary without detailing the premium costs.

## Verification

Before finalizing the financial report, verify:
- [ ] Overtime is only scheduled if explicitly allowed by context variables.
- [ ] Overtime hours are capped at the legal limits.
- [ ] Average cost impact per unit is quantified.
