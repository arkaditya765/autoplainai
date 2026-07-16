"""Supplier tool for AutoPlan AI.

Reads supplier metrics, lead times, and delay risks from suppliers.csv.
"""

import csv
from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from app.config import SUPPLIERS_CSV, INVENTORY_CSV
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class SupplierTool(BaseTool):
    """Tool that queries supplier performance, quality, and lead times."""

    name = "supplier_tool"
    description = (
        "Queries supplier metrics, delay risks, quality ratings, lead times, and supplier-to-component mappings. "
        "Use this when the query asks about suppliers, lead times, delivery schedules, or who supplies which parts."
    )
    version = "1.0.0"
    category = "manufacturing"
    tags = ["supplier", "supply_chain", "lead_time", "delays"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Loads supplier details and filters by target vehicle model if present in context.

        Args:
            state: The current state containing active context variables.
        """
        logger.info("Executing Supplier Tool")
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

        # 1. Map component_id to vehicle models using inventory data
        comp_to_vehicle = {}
        try:
            with open(INVENTORY_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    comp_to_vehicle[row["component_id"]] = row["target_model"]
        except Exception as e:
            logger.error("Failed to load component mapping in supplier tool", error=str(e))
            return {"status": "error", "message": f"Failed to load component mappings: {str(e)}"}

        # 2. Query suppliers and associate them with vehicle models
        suppliers = []
        try:
            with open(SUPPLIERS_CSV, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    comp_id = row["component_id"]
                    sup_name = row["supplier_name"]
                    lead_time = int(row["lead_time_days"])
                    delay_prob = float(row["delay_probability"])
                    quality = float(row["quality_rating"])
                    
                    associated_vehicle = comp_to_vehicle.get(comp_id, "unknown")

                    data = {
                        "supplier_name": sup_name,
                        "component_id": comp_id,
                        "associated_vehicle_model": associated_vehicle,
                        "lead_time_days": lead_time,
                        "delay_probability": delay_prob,
                        "quality_rating": quality,
                        "high_delay_risk": delay_prob > 0.25
                    }

                    # Filter by vehicle model if requested
                    if not filter_names or associated_vehicle.lower() in filter_names:
                        suppliers.append(data)
                        
        except Exception as e:
            logger.error("Failed to load suppliers CSV", error=str(e))
            return {"status": "error", "message": f"Failed to retrieve supplier data: {str(e)}"}

        return {
            "status": "success",
            "suppliers": suppliers,
            "filter_applied": list(filter_names) if filter_names else "none"
        }
