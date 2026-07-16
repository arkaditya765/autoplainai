"""Planner Agent implementation for framework.

Analyzes the query and available tools, producing a structured JSON plan 
indicating which tools to run and in what order.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from framework.llm.prompts import PLANNER_SYSTEM_INSTRUCTION, PLANNER_PROMPT_TEMPLATE
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class PlannerDecision(BaseModel):
    """Pydantic model representing the output of the Planner Agent."""
    selected_tools: List[str] = Field(
        ..., 
        description="List of tool names selected to be executed in sequence. Return empty list if no tools are needed."
    )
    reason: str = Field(
        ..., 
        description="The reasoning behind selecting these tools or why no tools are needed."
    )


class PlannerAgent(BaseAgent):
    """Planner Agent that determines the required tools to resolve a user request."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the planner agent logic.

        Args:
            state: The current shared AgentState dictionary.

        Returns:
            A dictionary updating 'selected_tools' and 'execution_trace'.
        """
        query = state.get("query", "")
        available_tools = state.get("available_tools", [])
        context_vars = state.get("context", {})
        
        logger.info("Planner Agent running", query=query, num_tools=len(available_tools))

        # Format tool metadata for the system instruction
        tools_metadata_str = json.dumps(available_tools, indent=2) if available_tools else "No tools available."

        # Format current context variables
        context_str = "\n".join(f"  - {k}: {v}" for k, v in context_vars.items()) if context_vars else "No active context variables."

        # Leave {available_tools_metadata} as placeholder — BoundLLM fills it in at invoke time
        system_instruction = PLANNER_SYSTEM_INSTRUCTION.format(
            available_tools_metadata="{available_tools_metadata}",
            context_variables=context_str
        )

        prompt = PLANNER_PROMPT_TEMPLATE.format(query=query)

        # Step 1 — bind tools to LLM: llmwithtool = llm.bind_tools([...])
        llm_with_tools = self.client.bind_tools(available_tools)

        # Step 2 — invoke: query + llmwithtool + System Prompt -> Answer
        # decision_test: raw invoke result (same call, shows the Pydantic object returned)
        decision_test = llm_with_tools.invoke(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.0,
        )

        decision: PlannerDecision = llm_with_tools.invoke(
            prompt=prompt,
            response_schema=PlannerDecision,
            system_instruction=system_instruction,
            temperature=0.0,
        )

        print("=== decision_test ===", decision_test)
        print("=== decision       ===", decision)
        print("=== decision.selected_tools ===", decision.selected_tools)
        print("=== decision.reason         ===", decision.reason)

        logger.info("Planner Agent decided plan", selected_tools=decision.selected_tools, reason=decision.reason)

        # Log to execution trace
        trace_step = {
            "node": "planner",
            "action": f"Selected tools: {decision.selected_tools}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "reason": decision.reason,
                "available_tools_considered": [t.get("name") for t in available_tools]
            }
        }

        # Keep existing execution trace and append the new step
        updated_trace = list(state.get("execution_trace", []))
        updated_trace.append(trace_step)

        return {
            "selected_tools": decision.selected_tools,
            "execution_trace": updated_trace
        }
