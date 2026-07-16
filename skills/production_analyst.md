---
name: production_analyst
description: Specialized manufacturing capacity and factory scheduling expert. Analyzes assembly line throughput, bottleneck limits, daily target demand adjustments, and equipment utilization.
---

# Production Analyst (Manufacturing Capacity Expert)

## Overview

The Production Analyst skill provides specialized capability for evaluating factory throughput, capacity constraints, assembly line speeds, and equipment utilization. In manufacturing planning, managers often propose adjustments without understanding the physical limitations of the assembly lines. This skill bridges that gap by calculating utilization rates and highlighting bottlenecks before scheduling.

## When to Use

Use this skill when:
- Evaluating whether assembly lines can support a proposed percentage demand increase.
- Identifying factory bottlenecks and line overloads.
- Running daily capacity audits for specific vehicle models (e.g. Brezza, Swift, Baleno, Dzire).
- Factoring assembly hourly rates into scheduling calculations.

Do NOT use this skill for:
- Financial cost calculations (e.g. hourly overtime premiums, standard vs overtime margins).
- Supply chain logistics or inventory turnover analysis.

## Guidelines & Process

When acting with this skill, adhere to the following analytical process:

### 1. Compute Capacity Utilization
Calculate the utilization percentage for each vehicle model line:
$$\text{Utilization (\%)} = \left(\frac{\text{Target Daily Demand}}{\text{Daily Line Capacity Limit}}\right) \times 100$$

### 2. Determine Load Category
Evaluate the utilization rate against the following standard engineering thresholds:
- **Normal Load ($< 80\%$)**: The line has comfortable headroom. No action required.
- **High Load ($80\%$ to $100\%$)**: The line is running near capacity. Monitor for fatigue and quality issues.
- **Overloaded ($> 100\%$)**: The line exceeds physical capacity. Requires immediate schedule adjustments, shift increases, or overtime.

### 3. Compute Hourly Assembly Requirements
Determine the actual hours needed to produce the target volume:
$$\text{Hours Needed} = \frac{\text{Target Daily Demand}}{\text{Assembly Rate Per Hour}}$$
*Note: A standard daily shift is 8 hours. If the hours needed exceed 8, overtime or additional shifts must be scheduled.*

---

## Output

Your analysis must include a clean markdown table summarizing the metrics, followed by a bulleted bottleneck assessment.

### Output Table Format
| Vehicle Model | Target Demand | Capacity Limit | Assembly Rate/Hr | Utilization (%) | Load Status | Deficit Units |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Baleno | 140 | 100 | 12 | 140.0% | **OVERLOADED** | 40 |

### Bottleneck Summary
- **Primary Bottleneck**: Identify the line with the highest utilization.
- **Feasibility Status**: Pass/Fail assessment based on daily limit headroom.
- **Action Plan**: Recommended adjustments (e.g. shift allocation, overtime hours to schedule).

---

## Example

**Scenario**: Baleno demand is increased by 40% (from 100 to 140 units).

**Calculation**:
- Target Demand: $140$
- Capacity Limit: $100$
- Hourly Assembly Rate: $12$ units/hour
- Utilization: $\frac{140}{100} \times 100 = 140\%$
- Hours Needed: $\frac{140}{12} = 11.67$ hours.

**Analysis**:
The Baleno line is **OVERLOADED** at 140% utilization. To meet the target, an extra $3.67$ hours of assembly line running time (overtime) must be scheduled, producing the remaining 40 deficit units.

---

## Common Rationalizations

| Rationalization | Reality |
| :--- | :--- |
| "We can run the line faster to catch up." | Assembly rates per hour are fixed mechanical constraints. Speeding up lines violates quality and safety protocols. |
| "A 110% load is fine for a few days." | Continuous load above 100% causes machine wear-and-tear and increases defect rates. It must be addressed via overtime or scheduling adjustments. |

## Red Flags

- Marking an overloaded line ($> 100\%$) as "feasible" without indicating the need for overtime shifts or extra assembly hours.
- Recommending assembly hours that exceed 12 hours total per day (the legal limit for a single line including max overtime).

## Verification

Before finalizing the capacity report, verify:
- [ ] Every active vehicle model's utilization rate is calculated correctly.
- [ ] Deficit units are quantified for any overloaded lines.
- [ ] The primary bottleneck is explicitly named.
