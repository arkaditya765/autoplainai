"""Router Agent for framework.

Classifies incoming user queries as either 'planning' (requiring multi-agent planning/data-gathering)
or 'general' (conversational chatbot queries).
"""

from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from framework.utils.logger import get_logger
from framework.utils.helpers import load_prompt

logger = get_logger(__name__)


class RouteDecision(BaseModel):
    category: str = Field(..., description="The routing category: MUST be either 'planning' or 'general'")
    reason: str = Field(..., description="Reasoning behind this routing classification")


_ROUTER_SYSTEM_INSTRUCTION_FALLBACK = """You are the Router Agent. Your job is to classify the User's Query into one of two categories:
1. "planning" - The query is about manufacturing, production limits, vehicle demands, assembly lines, labor costs, overtime, suppliers, inventory, or standard planning reports.
2. "general" - The query is a general knowledge question (e.g. prime minister of India, capital cities, code help, recipes), greeting, chit-chat, or anything unrelated to manufacturing and supply chain planning.

You must output a JSON object containing 'category' (either 'planning' or 'general') and 'reason'.
"""


class RouterAgent(BaseAgent):
    """Router Agent that classifies and routes queries dynamically in the workflow."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Classifies the user query.

        Args:
            state: The current state of the workflow graph.

        Returns:
            A state update dict containing the routing decision under 'route_decision'.
        """
        query = state.get("query", "")
        logger.info("Routing query classification starting", query=query)

        system_instruction = load_prompt("router.md", _ROUTER_SYSTEM_INSTRUCTION_FALLBACK)

        prompt = f"User Query: {query}"

        try:
            decision: RouteDecision = self.client.generate_structured(
                prompt=prompt,
                response_schema=RouteDecision,
                system_instruction=system_instruction,
                temperature=0.0
            )
            category = decision.category.strip().lower()
            if category not in ("planning", "general"):
                logger.warning("Router generated invalid category, defaulting to planning", category=category)
                category = "planning"

            logger.info("Router decision completed", category=category, reason=decision.reason)

            trace_step = {
                "node": "router",
                "action": f"Classified query as '{category}'.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "reasoning": decision.reason
                }
            }
            updated_trace = list(state.get("execution_trace", []))
            updated_trace.append(trace_step)

            return {
                "route_decision": category,
                "execution_trace": updated_trace
            }
        except Exception as e:
            logger.error("Failed to run RouterAgent, defaulting to planning", error=str(e))

            trace_step = {
                "node": "router",
                "action": "Failed to run query router. Defaulted to 'planning'.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "error": str(e)
                }
            }
            updated_trace = list(state.get("execution_trace", []))
            updated_trace.append(trace_step)

            return {
                "route_decision": "planning",
                "execution_trace": updated_trace
            }
