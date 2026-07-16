"""Report tool for AutoPlan AI.

Reads and aggregates overall stats from vehicles, inventory, and suppliers CSVs,
producing a consolidated operational health report.
"""

import csv
from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from app.config import VEHICLES_CSV, INVENTORY_CSV, SUPPLIERS_CSV
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class ReportTool(BaseTool):
    """Tool that aggregates all operational stats into a high-level report."""

    name = "report_tool"
    description = (
        "Compiles a high-level operational report summarizing capacity overruns, inventory shortages, and "
        "supplier risks. Use this when you need a consolidated status dashboard or a full overview of factory health."
    )
    version = "1.0.0"
    category = "manufacturing"
    tags = ["report", "analytics", "dashboard", "summary"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregates metrics from vehicles, inventory, and suppliers datasets.

        Args:
            state: The current state containing active context variables.
        """
        logger.info("Executing Report Tool")
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

        # 1. Aggregate Capacity Overloads
        capacity_issues = 0
        total_demand = 0
        total_capacity = 0
        demands = {}
        try:
            with open(VEHICLES_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    model = row["vehicle_model"]
                    demand = int(row["daily_demand"])
                    limit = int(row["line_capacity_limit"])
                    
                    # Apply specific demand adjustment for this model if present
                    change_pct = adj_map.get(model.lower(), 0.0)
                    if change_pct != 0.0:
                        multiplier = 1.0 + (change_pct / 100.0)
                        demand = int(demand * multiplier)
                        
                    demands[model] = demand
                    total_demand += demand
                    total_capacity += limit
                    
                    if demand > limit:
                        capacity_issues += 1
        except Exception as e:
            logger.error("Failed to compile capacity stats in report tool", error=str(e))
            return {"status": "error", "message": f"Failed to load vehicles data: {str(e)}"}

        # 2. Aggregate Inventory Shortages
        shortage_items_count = 0
        total_shortage_units = 0
        try:
            with open(INVENTORY_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stock = int(row["stock_level"])
                    req = int(row["required_per_vehicle"])
                    target = row["target_model"]
                    
                    demand_qty = demands.get(target, 0)
                    total_required = demand_qty * req
                    shortage = max(0, total_required - stock)
                    
                    if shortage > 0:
                        shortage_items_count += 1
                        total_shortage_units += shortage
        except Exception as e:
            logger.error("Failed to compile inventory stats in report tool", error=str(e))
            return {"status": "error", "message": f"Failed to load inventory data: {str(e)}"}

        # 3. Aggregate Supplier Risks
        supplier_risks_count = 0
        try:
            with open(SUPPLIERS_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    delay_prob = float(row["delay_probability"])
                    if delay_prob > 0.25:
                        supplier_risks_count += 1
        except Exception as e:
            logger.error("Failed to compile supplier stats in report tool", error=str(e))
            return {"status": "error", "message": f"Failed to load supplier data: {str(e)}"}

        # Return consolidated health indicators
        return {
            "status": "success",
            "report_summary": {
                "total_daily_demand": total_demand,
                "total_line_capacity": total_capacity,
                "lines_over_capacity": capacity_issues,
                "components_with_shortages": shortage_items_count,
                "total_component_shortages": total_shortage_units,
                "high_risk_suppliers_count": supplier_risks_count,
                "overall_operational_health": "CRITICAL" if (capacity_issues > 0 or shortage_items_count > 0) else "HEALTHY"
            }
        }
