"""Inventory tool for AutoPlan AI.

Reads warehouse inventory levels and checks for component shortages
based on current vehicle demand metrics.
"""

import csv
from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from app.config import INVENTORY_CSV, VEHICLES_CSV
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class InventoryTool(BaseTool):
    """Tool that reports component inventory levels and checks for shortages."""

    name = "inventory_tool"
    description = (
        "Checks component inventory stock levels, component names, vehicle associations (which parts belong "
        "to which vehicle model), and determines shortages. Use this when the query asks about components, "
        "parts, bills of materials (BOM), or shared parts between vehicles."
    )
    version = "1.0.0"
    category = "manufacturing"
    tags = ["inventory", "stock", "shortage", "materials"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Loads inventory lists and computes shortages against active vehicle demands.

        Args:
            state: The current state containing active context variables.
        """
        logger.info("Executing Inventory Tool")
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

        # 1. First, fetch vehicle demands to calculate required component quantities
        demands = {}
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
                    demands[model] = demand
        except Exception as e:
            logger.error("Failed to load vehicle demands in inventory tool", error=str(e))
            return {"status": "error", "message": f"Failed to retrieve vehicle demands: {str(e)}"}

        # 2. Iterate through inventory items and compute shortages
        items = []
        shortages_found = False
        try:
            with open(INVENTORY_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    comp_id = row["component_id"]
                    comp_name = row["component_name"]
                    stock = int(row["stock_level"])
                    req_per_unit = int(row["required_per_vehicle"])
                    target_model = row["target_model"]

                    # Calculate total needed based on current demand
                    demand_qty = demands.get(target_model, 0)
                    total_required = demand_qty * req_per_unit
                    shortage = max(0, total_required - stock)
                    
                    if shortage > 0:
                        shortages_found = True

                    data = {
                        "component_id": comp_id,
                        "component_name": comp_name,
                        "target_model": target_model,
                        "stock_level": stock,
                        "required_per_vehicle": req_per_unit,
                        "total_required_for_demand": total_required,
                        "shortage": shortage,
                        "has_shortage": shortage > 0
                    }

                    # Filter by vehicle model if requested
                    if not filter_names or target_model.lower() in filter_names:
                        items.append(data)
                        
        except Exception as e:
            logger.error("Failed to load inventory CSV", error=str(e))
            return {"status": "error", "message": f"Failed to retrieve inventory data: {str(e)}"}

        return {
            "status": "success",
            "inventory": items,
            "shortages_found": shortages_found,
            "filter_applied": list(filter_names) if filter_names else "none"
        }
