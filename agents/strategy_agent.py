"""Strategy Agent implementation for framework.

Synthesizes conversation history, context parameters, and tool execution outputs 
into a comprehensive strategic recommendation.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict
from agents.base_agent import BaseAgent
from framework.llm.prompts import STRATEGY_SYSTEM_INSTRUCTION, STRATEGY_PROMPT_TEMPLATE
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class StrategyAgent(BaseAgent):
    """Strategy Agent that compiles raw metrics and outputs into a strategic recommendation."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the strategy agent.

        Args:
            state: The current AgentState dictionary.

        Returns:
            A dictionary updating 'recommendation' and 'execution_trace'.
        """
        query = state.get("query", "")
        context_vars = state.get("context", {})
        tool_outputs = state.get("tool_outputs", {})

        logger.info("Strategy Agent running", query=query, num_tool_outputs=len(tool_outputs))

        # Format context variables for the prompt
        context_str = "\n".join(f"  - {k}: {v}" for k, v in context_vars.items()) if context_vars else "No active context variables."

        # Format tool outputs for the prompt
        tool_outputs_str = json.dumps(tool_outputs, indent=2) if tool_outputs else "No tool outputs available."

        # Interpolate variables into instructions and templates
        system_instruction = STRATEGY_SYSTEM_INSTRUCTION.format(
            context_variables=context_str,
            tool_outputs=tool_outputs_str
        )
        prompt = STRATEGY_PROMPT_TEMPLATE.format(query=query)

        # Generate recommendation
        logger.debug("Requesting Gemini to generate strategy recommendation")
        recommendation = self.client.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.4  # Slightly higher temperature for richer synthesis
        )

        logger.info("Strategy Agent finished formulating strategy.")

        # Log trace step
        trace_step = {
            "node": "strategy",
            "action": "Generated strategic recommendation.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "recommendation_snippet": recommendation[:200] + "..." if len(recommendation) > 200 else recommendation
            }
        }

        updated_trace = list(state.get("execution_trace", []))
        updated_trace.append(trace_step)

        return {
            "recommendation": recommendation,
            "execution_trace": updated_trace
        }
