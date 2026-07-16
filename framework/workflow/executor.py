"""Workflow Executor node for framework.

Retrieves selected tools from the registry and executes them sequentially,
updating the shared state with output data and execution times.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from framework.registry.tool_registry import ToolRegistry, global_registry
from framework.utils.logger import get_logger
from framework.utils.exceptions import ToolExecutionError, ToolNotFoundError

logger = get_logger(__name__)


class ToolExecutor:
    """Orchestrates sequential execution of selected tools and records traces."""

    def __init__(self, registry: ToolRegistry = global_registry) -> None:
        """Initializes the ToolExecutor.

        Args:
            registry: The tool registry to fetch tools from.
        """
        self.registry = registry

    def execute_selected(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Node handler that runs the tools listed in state['selected_tools'].

        Args:
            state: The current shared AgentState dictionary.

        Returns:
            A dictionary update containing 'tool_outputs' and 'execution_trace'.
        """
        selected_tools = state.get("selected_tools", [])
        tool_outputs = dict(state.get("tool_outputs", {}))
        updated_trace = list(state.get("execution_trace", []))

        logger.info("Executor node started execution", selected_tools=selected_tools)

        for tool_name in selected_tools:
            logger.info("Invoking tool execution", tool_name=tool_name)
            start_time = datetime.now(timezone.utc)
            
            try:
                # Retrieve the tool instance from the registry
                tool = self.registry.get_tool(tool_name)
                
                # Execute the tool using the shared state
                output = tool.execute(state)
                
                # Store output mapped to tool name
                tool_outputs[tool_name] = output
                
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                logger.info("Tool execution succeeded", tool_name=tool_name, duration_ms=duration_ms)

                # Add trace step
                trace_step = {
                    "node": "executor",
                    "action": f"Executed tool: {tool_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "tool_name": tool_name,
                        "status": "success",
                        "duration_ms": duration_ms,
                        "output_summary": str(output)[:150] + "..." if len(str(output)) > 150 else str(output)
                    }
                }
                updated_trace.append(trace_step)

            except ToolNotFoundError as e:
                logger.error("Selected tool not found in registry", tool_name=tool_name)
                trace_step = {
                    "node": "executor",
                    "action": f"Failed tool lookup: {tool_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"tool_name": tool_name, "status": "missing_tool"}
                }
                updated_trace.append(trace_step)
                raise ToolExecutionError(tool_name, "Tool is not registered in the system.", original_exception=e) from e
                
            except Exception as e:
                logger.error("Execution failure occurred inside tool", tool_name=tool_name, error=str(e))
                trace_step = {
                    "node": "executor",
                    "action": f"Tool error: {tool_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"tool_name": tool_name, "status": "failure", "error_message": str(e)}
                }
                updated_trace.append(trace_step)
                raise ToolExecutionError(tool_name, f"Internal execution failed: {e}", original_exception=e) from e

        return {
            "tool_outputs": tool_outputs,
            "execution_trace": updated_trace
        }
