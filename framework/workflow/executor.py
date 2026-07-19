"""Workflow Executor node for framework.

Retrieves selected tools from the registry and executes them in parallel,
updating the shared state with output data and execution times.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor
from framework.registry.tool_registry import ToolRegistry, global_registry
from framework.utils.logger import get_logger
from framework.utils.exceptions import ToolExecutionError, ToolNotFoundError

logger = get_logger(__name__)


class ToolExecutor:
    """Orchestrates parallel execution of selected tools and records traces."""

    def __init__(self, registry: ToolRegistry = global_registry) -> None:
        """Initializes the ToolExecutor.

        Args:
            registry: The tool registry to fetch tools from.
        """
        self.registry = registry

    def _execute_single_tool(self, tool_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to run a single tool execution and return its outcome details."""
        start_time = datetime.now(timezone.utc)
        try:
            tool = self.registry.get_tool(tool_name)
            output = tool.execute(state)
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return {
                "tool_name": tool_name,
                "status": "success",
                "output": output,
                "duration_ms": duration_ms,
                "error": None,
                "error_type": None
            }
        except ToolNotFoundError as e:
            return {
                "tool_name": tool_name,
                "status": "missing_tool",
                "output": None,
                "duration_ms": 0.0,
                "error": e,
                "error_type": "missing"
            }
        except Exception as e:
            return {
                "tool_name": tool_name,
                "status": "failure",
                "output": None,
                "duration_ms": 0.0,
                "error": e,
                "error_type": "execution"
            }

    def execute_selected(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Node handler that runs the tools listed in state['selected_tools'] in parallel.

        Args:
            state: The current shared AgentState dictionary.

        Returns:
            A dictionary update containing 'tool_outputs' and 'execution_trace'.
        """
        selected_tools = state.get("selected_tools", [])
        tool_outputs = dict(state.get("tool_outputs", {}))
        updated_trace = list(state.get("execution_trace", []))

        logger.info("Executor node started execution", selected_tools=selected_tools)

        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self._execute_single_tool, tool_name, state)
                for tool_name in selected_tools
            ]
            results = [f.result() for f in futures]

        for res in results:
            tool_name = res["tool_name"]
            status = res["status"]
            output = res["output"]
            duration_ms = res["duration_ms"]
            error = res["error"]
            error_type = res["error_type"]

            if status == "success":
                logger.info("Tool execution succeeded", tool_name=tool_name, duration_ms=duration_ms)
                tool_outputs[tool_name] = output

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

            elif error_type == "missing":
                logger.error("Selected tool not found in registry", tool_name=tool_name)
                trace_step = {
                    "node": "executor",
                    "action": f"Failed tool lookup: {tool_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"tool_name": tool_name, "status": "missing_tool"}
                }
                updated_trace.append(trace_step)
                raise ToolExecutionError(tool_name, "Tool is not registered in the system.", original_exception=error) from error

            else:  # execution error
                logger.error("Execution failure occurred inside tool", tool_name=tool_name, error=str(error))
                trace_step = {
                    "node": "executor",
                    "action": f"Tool error: {tool_name}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"tool_name": tool_name, "status": "failure", "error_message": str(error)}
                }
                updated_trace.append(trace_step)
                raise ToolExecutionError(tool_name, f"Internal execution failed: {error}", original_exception=error) from error

        return {
            "tool_outputs": tool_outputs,
            "execution_trace": updated_trace
        }

