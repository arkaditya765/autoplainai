"""Cost tool for AutoPlan AI.

Reads vehicle cost margins, labor rates, and overtime rules from costs.csv,
and estimates production cost impacts under different capacity scenarios.
"""

import csv
from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from app.config import COSTS_CSV, VEHICLES_CSV
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class CostTool(BaseTool):
    """Tool that calculates standard and overtime costs for vehicle production."""

    name = "cost_tool"
    description = (
        "Estimates manufacturing expenses, standard margin projections, labor costs, and overtime fee estimations "
        "based on vehicle demand adjustments. Use this when the query asks about overtime expenses, "
        "margins, standard costs, or financial budget calculations."
    )
    version = "1.0.0"
    category = "manufacturing"
    tags = ["cost", "budget", "overtime", "labor"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates standard and overtime cost projections.

        Args:
            state: The current state containing active context variables.
        """
        logger.info("Executing Cost Tool")
        # Read active adjustments list from context
        context = state.get("context", {})
        adjustments = context.get("adjustments") or []
        
        # Build adjustments lookup map: {vehicle_lower: change_pct}
        adj_map = {}
        for adj in adjustments:
            v_name = adj["vehicle"] if isinstance(adj, dict) else adj.get("vehicle")
            v_pct = adj["demand_change_pct"] if isinstance(adj, dict) else adj.get("demand_change_pct")
            if v_name:
                adj_map[v_name.lower()] = float(v_pct)

        # Support backward compatibility with single-value overrides if any
        target_vehicle = context.get("vehicle") or context.get("vehicle_model")
        demand_increase_pct = context.get("demand_increase_pct") or context.get("demand_change")
        if target_vehicle and target_vehicle.lower() not in adj_map and demand_increase_pct is not None:
            adj_map[target_vehicle.lower()] = float(demand_increase_pct)

        # Determine filter set (if adjustments are active, filter to show only adjusted models)
        filter_names = set(adj_map.keys())
        if target_vehicle:
            filter_names.add(target_vehicle.lower())
        
        # Check if overtime is allowed in active session context
        overtime_allowed = context.get("overtime_allowed") or context.get("overtime") or False
        # Normalize boolean from strings if necessary
        if isinstance(overtime_allowed, str):
            overtime_allowed = overtime_allowed.lower() in ("true", "1", "yes")

        # 1. Fetch vehicle assembly rates and capacity limits from vehicles data
        vehicles_data = {}
        try:
            with open(VEHICLES_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    model = row["vehicle_model"]
                    demand = int(row["daily_demand"])
                    
                    # Apply specific demand adjustment for this model if present
                    change_pct = adj_map.get(model.lower(), 0.0)
                    if change_pct != 0.0:
                        multiplier = 1.0 + (change_pct / 100.0)
                        demand = int(demand * multiplier)

                    vehicles_data[model] = {
                        "demand": demand,
                        "limit": int(row["line_capacity_limit"]),
                        "assembly_rate": int(row["assembly_rate_per_hour"])
                    }
        except Exception as e:
            logger.error("Failed to load vehicles CSV in cost tool", error=str(e))
            return {"status": "error", "message": f"Failed to load vehicles data: {str(e)}"}

        # 2. Fetch cost rules and calculate estimates
        costs = []
        try:
            with open(COSTS_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    model = row["vehicle_model"]
                    std_cost = float(row["standard_cost_per_unit"])
                    ot_rate = float(row["overtime_cost_per_hour"])
                    max_ot_hours = float(row["max_overtime_hours_allowed"])

                    v_info = vehicles_data.get(model)
                    if not v_info:
                        continue

                    demand = v_info["demand"]
                    limit = v_info["limit"]
                    assembly_rate = v_info["assembly_rate"]

                    # Base calculation
                    units_within_capacity = min(demand, limit)
                    standard_cost_total = units_within_capacity * std_cost

                    # Overtime calculations for shortfall
                    shortfall_units = max(0, demand - limit)
                    overtime_hours_needed = 0.0
                    overtime_cost_total = 0.0
                    deficit_units = shortfall_units
                    overtime_hours_used = 0.0

                    if shortfall_units > 0:
                        # Hours needed = shortfall units / assembly rate per hour
                        overtime_hours_needed = round(shortfall_units / assembly_rate, 2)
                        
                        if overtime_allowed:
                            # Cap overtime hours to the legal maximum limit
                            overtime_hours_used = min(overtime_hours_needed, max_ot_hours)
                            overtime_cost_total = overtime_hours_used * ot_rate
                            
                            # Calculate units actually produced during overtime
                            units_produced_in_overtime = int(overtime_hours_used * assembly_rate)
                            deficit_units = max(0, shortfall_units - units_produced_in_overtime)
                        else:
                            # Overtime is not allowed, so deficit is the full shortfall
                            deficit_units = shortfall_units

                    total_cost = standard_cost_total + overtime_cost_total

                    data = {
                        "vehicle_model": model,
                        "demand": demand,
                        "production_limit": limit,
                        "shortfall_units": shortfall_units,
                        "overtime_hours_needed": overtime_hours_needed,
                        "overtime_hours_used": overtime_hours_used,
                        "overtime_cost": overtime_cost_total,
                        "deficit_units": deficit_units,
                        "standard_production_cost": standard_cost_total,
                        "total_production_cost": total_cost,
                        "overtime_applied": overtime_allowed and overtime_hours_used > 0
                    }

                    # Filter by vehicle model if requested
                    if not filter_names or model.lower() in filter_names:
                        costs.append(data)

        except Exception as e:
            logger.error("Failed to load costs CSV", error=str(e))
            return {"status": "error", "message": f"Failed to retrieve cost data: {str(e)}"}

        return {
            "status": "success",
            "costs": costs,
            "overtime_allowed": overtime_allowed,
            "filter_applied": list(filter_names) if filter_names else "none"
        }
