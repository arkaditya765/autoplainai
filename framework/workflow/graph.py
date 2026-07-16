"""LangGraph Workflow definition for framework.

Orchestrates execution using:
  1. OrchestratorNode - central brain of the framework (selection & execution loop)
  2. StrategyNode     - compiles raw metrics/outputs into strategic recommendations
  3. ValidatorNode    - quality assurance check against active business constraints
"""

from typing import Any, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from framework.state.state import AgentState
from framework.llm.gemini_client import GeminiClient
from agents.router_agent import RouterAgent
from agents.chatbot_agent import ChatbotAgent
from agents.query_planner import QueryPlannerAgent
from agents.native_orchestrator_agent import NativeOrchestratorAgent
from agents.strategy_agent import StrategyAgent
from agents.validator_agent import ValidatorAgent
from framework.registry.tool_registry import ToolRegistry, global_registry
from framework.utils.logger import get_logger

logger = get_logger(__name__)


def build_workflow(
    gemini_client: GeminiClient,
    registry: ToolRegistry = global_registry
) -> CompiledStateGraph:
    """Builds and compiles the multi-agent orchestrator StateGraph.

    The workflow classifies the query using a router and:
      - Decomposes both general and planning queries into structured tasks via planner_node,
        orchestrated sequentially, validated, and finalized.

    Args:
        gemini_client: An initialized GeminiClient instance to inject into agents.
        registry: The ToolRegistry containing active discovery plugins.

    Returns:
        A compiled LangGraph instance that can be executed using graph.invoke().
    """
    logger.info("Initializing LangGraph StateGraph composition")

    # 1. Instantiate agents using dependency injection
    router = RouterAgent(gemini_client)
    chatbot = ChatbotAgent(gemini_client, registry)
    planner = QueryPlannerAgent(gemini_client)
    orchestrator = NativeOrchestratorAgent(gemini_client, registry)
    strategy = StrategyAgent(gemini_client)
    validator = ValidatorAgent(gemini_client)

    # Helper: wraps an agent.run() to record wall-clock duration into state diagnostics
    def timed_node(node_name: str, agent_run_fn):
        """Wraps an agent.run() call to stamp its duration into state['diagnostics']."""
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            import time
            t0 = time.perf_counter()
            result = agent_run_fn(state)
            dur = time.perf_counter() - t0
            # Merge node timing into the RESULT's diagnostics (not the input state's),
            # so we don't overwrite data the agent already wrote (e.g. orchestrator's tool_executions)
            diag = dict(result.get("diagnostics", state.get("diagnostics", {})))
            timings = list(diag.get("node_timings", []))
            timings.append({"node": node_name, "duration_s": round(dur, 3)})
            diag["node_timings"] = timings
            result["diagnostics"] = diag
            return result
        return wrapper

    # 2. Build StateGraph using AgentState TypedDict schema
    workflow = StateGraph(AgentState)

    # 3. Define Graph Nodes (each wrapped with timing diagnostics)
    workflow.add_node("router_node", timed_node("router_node", router.run))
    workflow.add_node("chatbot_node", timed_node("chatbot_node", chatbot.run))
    workflow.add_node("planner_node", timed_node("planner_node", planner.run))
    workflow.add_node("orchestrator_node", timed_node("orchestrator_node", orchestrator.run))
    workflow.add_node("strategy_node", timed_node("strategy_node", strategy.run))
    workflow.add_node("validator_node", timed_node("validator_node", validator.run))

    # Define conditional routing condition
    def route_query(state: AgentState) -> str:
        decision = state.get("route_decision", "planning")
        if decision == "general":
            return "general"
        return "planning"

    # Define conditional routing from orchestrator based on route classification
    def route_orchestrator(state: AgentState) -> str:
        decision = state.get("route_decision", "planning")
        if decision == "general":
            return "general"
        return "planning"

    # 4. Connect edges sequentially with conditional router
    workflow.add_edge(START, "router_node")
    workflow.add_conditional_edges(
        "router_node",
        route_query,
        {
            "planning": "planner_node",
            "general": "planner_node"  # Decompose general queries too!
        }
    )
    workflow.add_edge("planner_node", "orchestrator_node")
    workflow.add_conditional_edges(
        "orchestrator_node",
        route_orchestrator,
        {
            "planning": "strategy_node",
            "general": "chatbot_node"
        }
    )
    workflow.add_edge("chatbot_node", END)
    workflow.add_edge("strategy_node", "validator_node")
    workflow.add_edge("validator_node", END)

    logger.info("Successfully compiled framework orchestrator LangGraph")
    return workflow.compile()
