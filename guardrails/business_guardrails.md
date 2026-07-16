# Business Guardrails

These rules define strict operational limits and commercial compliance thresholds. Recommendations that violate these business policies must be marked as `FAILED`.

## 1. Capacity Exceedance Limit
- Even if overtime is allowed and active, total target demand for any vehicle model must not exceed its daily line capacity limit by more than **40%**. 
- Any overload greater than 40% represents a severe equipment wear-and-tear risk and is prohibited.

## 2. Overtime Hours Hard Cap
- Overtime shifts scheduled per model must never exceed the legal maximum limits defined in the costs database (e.g. typically 3.0 to 4.0 hours max per day).
- If a recommended plan assumes working more overtime hours than the legal threshold, it is illegal and must fail validation.

## 3. Critical Supplier Thresholds
- Recommendations must not exceed the maximum supply capacity of critical tier-1 suppliers.
- If supplier utilization is projected to exceed 100% of their maximum daily limits, the plan is unfeasible and must fail.
