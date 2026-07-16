from typing import Any, Dict
from framework.registry.tool_registry import BaseTool

class WeatherTool(BaseTool):
    name = "weather_tool"
    description = "Queries daily weather forecasts, temperature ranges, precipitation levels, and meteorological updates."
    version = "1.0.0"
    category = "general"
    tags = ["weather", "temperature", "forecast", "climate"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "temperature_celsius": 28, "forecast": "Sunny with clear skies"}
