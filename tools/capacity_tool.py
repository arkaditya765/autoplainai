"""Capacity tool for AutoPlan AI.

Reads daily vehicle demands and capacities from vehicles.csv.
"""

import csv
from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from app.config import VEHICLES_CSV
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class CapacityTool(BaseTool):
    """Tool that queries production line capacity and demand details."""

    name = "capacity_tool"
    description = (
        "Calculates daily assembly line capacities, current target demands, and line utilization metrics "
        "for specific vehicles (such as Brezza, Swift, Baleno, Dzire). Use this when the query asks "
        "to check assembly limits, line overloads, line capabilities, or whether production lines "
        "can accommodate demand changes."
    )
    version = "1.0.0"
    category = "manufacturing"
    tags = ["capacity", "demand", "assembly"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Reads capacity data and filters by active vehicle model if present in context.

        Args:
            state: The current workflow state containing active context variables.
        """
        logger.info("Executing Capacity Tool")
        
        # Read the active adjustments list from context
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
        
        results = []
        try:
            with open(VEHICLES_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    model_name = row["vehicle_model"]
                    daily_demand = int(row["daily_demand"])
                    line_limit = int(row["line_capacity_limit"])
                    assembly_rate = int(row["assembly_rate_per_hour"])
                    
                    # Apply specific demand adjustment for this model if present
                    change_pct = adj_map.get(model_name.lower(), 0.0)
                    if change_pct != 0.0:
                        multiplier = 1.0 + (change_pct / 100.0)
                        daily_demand = int(daily_demand * multiplier)

                    # Compute capacity utilization rate
                    utilization = round((daily_demand / line_limit) * 100.0, 1)

                    data = {
                        "vehicle_model": model_name,
                        "daily_demand": daily_demand,
                        "line_capacity_limit": line_limit,
                        "assembly_rate_per_hour": assembly_rate,
                        "capacity_utilization_percent": utilization,
                        "capacity_exceeded": daily_demand > line_limit
                    }
                    
                    if not filter_names or model_name.lower() in filter_names:
                        results.append(data)
                        
        except Exception as e:
            logger.error("Failed to read vehicle capacity csv", error=str(e))
            return {"status": "error", "message": f"Failed to retrieve capacity data: {str(e)}"}

        return {
            "status": "success",
            "vehicles": results,
            "filter_applied": list(filter_names) if filter_names else "none"
        }
