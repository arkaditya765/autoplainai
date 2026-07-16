"""Orchestrator Agent for framework.

Acts as the central brain of the framework. It reads the user query,
conversation history, and available tools, decides which tools are required,
executes them sequentially, stores the results in the state, and passes
control to the Strategy Agent.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from google.genai.errors import APIError

from agents.base_agent import BaseAgent
from framework.registry.tool_registry import ToolRegistry
from framework.utils.logger import get_logger
from framework.utils.exceptions import LLMError

logger = get_logger(__name__)

ORCHESTRATOR_SYSTEM_INSTRUCTION = """You are the Orchestrator Agent for AutoPlan AI, the central brain of the framework.

Your role is to read the user query, conversation history, and inspect available tools to decide which tools are required to gather data.

Active context variables (from conversation memory):
{context_variables}

Available Tools:
{available_tools_metadata}

Instructions:
- Review the available tools and select the most relevant tool(s) to gather data.
- Provide a concise, one-sentence reasoning explanation explaining why you are calling those tools.
- Do not formulate the final strategic recommendation; just select the tools needed to collect the raw data.
"""


class OrchestratorDecision(BaseModel):
    """Pydantic model representing the tool execution decision of the Orchestrator Agent."""
    selected_tools: List[str] = Field(
        ...,
        description="List of tool names selected to be executed in sequence. Return empty list if no tools are needed."
    )
    reasoning: str = Field(
        ...,
        description="A concise, one-sentence reasoning explanation explaining why you are calling these tools."
    )
    vehicle: Optional[str] = Field(
        None,
        description="The vehicle model name (e.g. Brezza, Swift, Baleno, Dzire) if discussed in the query or history."
    )
    demand_change_pct: Optional[float] = Field(
        None,
        description="The percentage demand change discussed (e.g. -10.0 for 10% decrease, 15.0 for 15% increase) if discussed."
    )
    overtime_hours: Optional[float] = Field(
        None,
        description="Number of overtime hours (if discussed)."
    )
    component: Optional[str] = Field(
        None,
        description="The component name or vehicle name to check supplier capacity for (if discussed)."
    )


class OrchestratorAgent(BaseAgent):
    """The central Orchestrator Agent coordinating tool selection and execution via Method 2."""

    def __init__(self, gemini_client, registry: ToolRegistry) -> None:
        super().__init__(gemini_client)
        self.registry = registry

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the orchestrator wrapper-bound tool selection and execution loop.

        Args:
            state: The current shared AgentState dictionary.

        Returns:
            A dictionary updating selected_tools, tool_outputs, context, and execution_trace.
        """
        query = state.get("query", "")
        available_tools = state.get("available_tools", [])
        context = dict(state.get("context", {}))
        conversation_history = state.get("conversation_history", [])

        logger.info("Orchestrator Agent running tool loop via Method 2", query=query, num_tools=len(available_tools))

        # Format current context variables
        context_str = "\n".join(f"  - {k}: {v}" for k, v in context.items()) if context else "No active context variables."

        # Build system instruction with context placeholder
        system_instruction = ORCHESTRATOR_SYSTEM_INSTRUCTION.format(
            context_variables=context_str,
            available_tools_metadata="{available_tools_metadata}"
        )

        # Build history prompt structure
        history_str = ""
        if conversation_history:
            history_str = "\n".join(f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in conversation_history[-4:])
        prompt = f"Conversation History:\n{history_str}\n\nUser Query: {query}"

        # Step 1: Bind tools to LLM client wrapper
        llm_with_tools = self.client.bind_tools(available_tools)

        # Step 2: Invoke LLM to get structured tools selection and parameter extraction
        try:
            decision: OrchestratorDecision = llm_with_tools.invoke(
                prompt=prompt,
                response_schema=OrchestratorDecision,
                system_instruction=system_instruction,
                temperature=0.0,
            )
        except APIError as e:
            logger.error("Gemini API error in Orchestrator tool selection", error=str(e))
            raise LLMError(f"Gemini API error during tool selection: {e.message}", details={"code": e.code}) from e
        except Exception as e:
            logger.error("Unexpected error in Orchestrator tool selection", error=str(e))
            raise LLMError("Unexpected error during tool selection.", details=str(e)) from e

        logger.info("Orchestrator selected tools", selected_tools=decision.selected_tools, reasoning=decision.reasoning)

        # Step 3: Inject extracted parameters back into context
        if decision.vehicle:
            v_name = decision.vehicle
            v_pct = decision.demand_change_pct or 0.0
            
            # Consolidate adjustments list
            adjustments = list(context.get("adjustments", []))
            adj_map = {}
            for adj in adjustments:
                name = adj["vehicle"] if isinstance(adj, dict) else adj.get("vehicle")
                pct = adj["demand_change_pct"] if isinstance(adj, dict) else adj.get("demand_change_pct")
                if name:
                    adj_map[name.lower()] = {"vehicle": name, "demand_change_pct": pct}
            
            adj_map[v_name.lower()] = {"vehicle": v_name, "demand_change_pct": v_pct}
            context["adjustments"] = list(adj_map.values())
            context["vehicle"] = v_name
            context["demand_increase_pct"] = v_pct
        
        if decision.overtime_hours is not None:
            context["overtime_hours"] = decision.overtime_hours
        if decision.component:
            context["component"] = decision.component

        # Update context on state before execution
        state["context"] = context

        # Step 4: Sequentially execute the selected tools
        tool_outputs = dict(state.get("tool_outputs", {}))
        execution_trace = list(state.get("execution_trace", []))

        for tool_name in decision.selected_tools:
            logger.info("Executing selected tool", tool_name=tool_name)
            try:
                tool = self.registry.get_tool(tool_name)
                result = tool.execute(state)
                tool_outputs[tool_name] = result
                status = "success"
                logger.info("Tool executed successfully", tool_name=tool_name)
            except Exception as e:
                result = {"status": "error", "message": str(e)}
                tool_outputs[tool_name] = result
                status = "error"
                logger.error("Tool execution failed", tool_name=tool_name, error=str(e))

            # Add trace entry with the reasoning and tool result
            trace_entry = {
                "node": "orchestrator",
                "action": f"Executed tool: {tool_name}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "tool_name": tool_name,
                    "status": status,
                    "reasoning": decision.reasoning,
                    **result
                },
            }
            execution_trace.append(trace_entry)

        return {
            "selected_tools": decision.selected_tools,
            "tool_outputs": tool_outputs,
            "execution_trace": execution_trace,
            "context": context,
        }
