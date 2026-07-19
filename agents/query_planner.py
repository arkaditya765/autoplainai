"""Query Planner Agent for framework.

Decomposes complex user requests into structured, logical, and executable tasks
with dependency declarations before the orchestrator begins execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from agents.base_agent import BaseAgent
from framework.state.state import ExecutionPlan
from framework.utils.logger import get_logger
from framework.utils.helpers import load_prompt

logger = get_logger(__name__)

_PLANNER_SYSTEM_INSTRUCTION_FALLBACK = """You are the Query Planner Agent for AutoPlan AI, the task decomposition brain of the framework.

Your role is to analyze the user request, conversation history, and active context variables to produce a structured ExecutionPlan.
This plan must break down the user's overall goal into a logical, sequential plan of executable tasks.

Active context variables (from memory):
{context_variables}

Instructions:
- Understand the complete user goal.
- Break down the request into a series of logical, sequential tasks.
- Detect task dependencies (e.g. if Task 2 needs the output of Task 1, specify that Task 2 depends on Task 1 using parent task IDs).
- Make sure each task is concrete, atomic, and represents a specific evaluation (e.g. checking capacity, checking cost, checking inventory, checking suppliers, or searching the web).
- Never execute tools yourself.
- Never generate final strategic recommendations.
- Keep the task plan concise and reasonable (usually 2 to 4 tasks).
"""

PLANNER_SYSTEM_INSTRUCTION = load_prompt("query_planner.md", _PLANNER_SYSTEM_INSTRUCTION_FALLBACK)

PLANNER_PROMPT_TEMPLATE = """Generate a structured ExecutionPlan for the following user request:
Query: {query}

Please inspect the conversation history if relevant to resolve references:
{history}
"""


class QueryPlannerAgent(BaseAgent):
    """Planner Agent that decomposes complex user queries into structured ExecutionPlans."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the query planner agent.

        Args:
            state: The current AgentState dictionary.

        Returns:
            A dictionary updating 'execution_plan', 'planner_reasoning', and 'execution_trace'.
        """
        query = state.get("query", "")
        context_vars = state.get("context", {})
        conversation_history = state.get("conversation_history", [])

        logger.info("Query Planner Agent running task decomposition", query=query)

        # Format context variables for the planner prompt (excluding concurrency_mode to align sequential/parallel tasks)
        planner_context = {k: v for k, v in context_vars.items() if k != "concurrency_mode"}
        context_str = "\n".join(f"  - {k}: {v}" for k, v in planner_context.items()) if planner_context else "No active context variables."

        # Format history for resolving context
        history_str = ""
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_str += f"  [{role}]: {content}\n"
        if not history_str:
            history_str = "No conversation history available."

        system_instruction = PLANNER_SYSTEM_INSTRUCTION.format(context_variables=context_str)
        prompt = PLANNER_PROMPT_TEMPLATE.format(query=query, history=history_str)

        # Generate structured plan conformant to Pydantic model
        logger.debug("Requesting Gemini to decompose query into structured tasks")
        plan: ExecutionPlan = self.client.generate_structured(
            prompt=prompt,
            response_schema=ExecutionPlan,
            system_instruction=system_instruction,
            temperature=0.0  # Zero temperature for deterministic planning
        )

        logger.info("Query Planner generated structured plan", goal=plan.goal, num_tasks=len(plan.tasks))

        # Log trace step
        trace_step = {
            "node": "planner",
            "action": f"Decomposed query into {len(plan.tasks)} tasks. Goal: {plan.goal}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "goal": plan.goal,
                "planner_reasoning": plan.planner_reasoning,
                "tasks": [t.model_dump() for t in plan.tasks]
            }
        }

        updated_trace = list(state.get("execution_trace", []))
        updated_trace.append(trace_step)

        # Convert plan Pydantic model into a dictionary for serializability in state
        plan_dict = plan.model_dump()

        return {
            "execution_plan": plan_dict,
            "planner_reasoning": plan.planner_reasoning,
            "execution_trace": updated_trace,
            "planner_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "goal": plan.goal
            }
        }
