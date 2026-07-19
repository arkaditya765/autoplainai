"""Native Orchestrator Agent for framework.

Coordinates task execution by iterating through a structured query plan,
verifying dependencies, and coordinating native Gemini tool calling for each task.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from google.genai import types
from google.genai.errors import APIError

from agents.base_agent import BaseAgent
from framework.registry.tool_registry import ToolRegistry
from framework.utils.logger import get_logger
from framework.utils.exceptions import LLMError
from framework.utils.helpers import load_prompt

logger = get_logger(__name__)

_ORCHESTRATOR_SYSTEM_INSTRUCTION_FALLBACK = """You are the Orchestrator Agent for AutoPlan AI, the central execution brain of the framework.

Your role is to run the current task using the task-specific guidelines, active context variables, and tool parameters to decide which tools are required to gather data.

Active context variables (from conversation memory):
{context_variables}

Instructions:
- Review the available tools and call the most relevant tool(s) to gather data for this specific task.
- AUTOMATIC SKILL ASSESSMENT: Before calling domain-specific tools, you MUST check if a specialized skill is needed. If the task involves capacity or costs, call load_skill_tool FIRST with a generic name (e.g. `load_skill_tool(skill_name="appropriate")`). The system will automatically run semantic search (RAG) on your active task query to locate, select, and load the single correct domain expert skill for you. Do NOT call load_skill_tool multiple times, and do NOT try to load multiple skills.
- STRICT RULE: Only call tools that are directly relevant to the current task's objective. Do not invoke tools that belong to other tasks (e.g. do not call search tools if the task is only about calculating capacity, and vice versa).
- Before calling a tool, ALWAYS write a concise, one-sentence reasoning explanation explaining why you are calling that tool.
- After calling the tool(s) and receiving the data, you should stop calling tools.
- Do not formulate the final strategic recommendation; just collect the raw data.
"""

ORCHESTRATOR_SYSTEM_INSTRUCTION = load_prompt("orchestrator.md", _ORCHESTRATOR_SYSTEM_INSTRUCTION_FALLBACK)


class NativeOrchestratorAgent(BaseAgent):
    """Orchestrator Agent utilizing manual tool calling, execution, and FunctionResponse feedback loop."""

    def __init__(self, gemini_client, registry: ToolRegistry) -> None:
        super().__init__(gemini_client)
        self.registry = registry

    def _execute_single_tool(self, fc, state, task_id):
        tool_name = fc.name
        fc_args = fc.args or {}
        
        import copy
        tool_context = copy.deepcopy(state.get("context", {}))
        
        if "vehicle" in fc_args:
            v_name = fc_args["vehicle"]
            v_pct = fc_args.get("demand_change_pct") or fc_args.get("demand_increase_pct")
            
            adjustments = list(tool_context.get("adjustments", []))
            adj_map = {}
            for adj in adjustments:
                name = adj["vehicle"] if isinstance(adj, dict) else adj.get("vehicle")
                pct = adj["demand_change_pct"] if isinstance(adj, dict) else adj.get("demand_change_pct")
                if name:
                    adj_map[name.lower()] = {"vehicle": name, "demand_change_pct": pct}
            
            if v_pct is not None:
                adj_map[v_name.lower()] = {"vehicle": v_name, "demand_change_pct": float(v_pct)}
                tool_context["demand_increase_pct"] = float(v_pct)
            elif v_name.lower() not in adj_map:
                adj_map[v_name.lower()] = {"vehicle": v_name, "demand_change_pct": 0.0}
                tool_context["demand_increase_pct"] = 0.0
                
            tool_context["adjustments"] = list(adj_map.values())
            tool_context["vehicle"] = v_name
        
        if "overtime_hours" in fc_args:
            tool_context["overtime_hours"] = fc_args["overtime_hours"]
        if "component" in fc_args:
            tool_context["component"] = fc_args["component"]
        if "search_query" in fc_args:
            tool_context["search_query"] = fc_args["search_query"]
        if "skill_name" in fc_args:
            tool_context["skill_name"] = fc_args["skill_name"]
            
        tool_state = {
            **state,
            "context": tool_context
        }
        
        import time as _t
        _tool_t0 = _t.perf_counter()
        try:
            tool = self.registry.get_tool(tool_name)
            result = tool.execute(tool_state)
            status = "success"
            dur = _t.perf_counter() - _tool_t0
            logger.info("Tool executed successfully inside task (parallel)", task_id=task_id, tool_name=tool_name)
        except Exception as e:
            result = {"status": "error", "message": str(e)}
            status = "error"
            dur = 0.0
            logger.error("Tool execution failed inside task (parallel)", task_id=task_id, tool_name=tool_name, error=str(e))
            
        return {
            "tool_name": tool_name,
            "fc_id": fc.id,
            "fc_args": fc_args,
            "tool_context": tool_context,
            "result": result,
            "status": status,
            "duration_s": round(dur, 3)
        }

    def _build_function_declarations(self, available_tools: List[Dict[str, Any]]) -> List[types.FunctionDeclaration]:
        """Converts tool metadata dicts into Gemini FunctionDeclaration objects with input parameters."""
        declarations = []
        for tool_meta in available_tools:
            tool_name = tool_meta.get("name", "")
            
            # Build tool schema properties dynamically to enable Gemini native parameter extraction
            properties = {}
            required = []
            
            if tool_name == "capacity_tool":
                properties = {
                    "vehicle": {
                        "type": "STRING",
                        "description": "The vehicle model name (e.g. Brezza, Swift, Baleno, Dzire)",
                    },
                    "demand_change_pct": {
                        "type": "NUMBER",
                        "description": "The percentage demand change discussed (e.g. -10.0 for 10% decrease, 15.0 for 15% increase)",
                    }
                }
            elif tool_name == "cost_tool":
                properties = {
                    "vehicle": {
                        "type": "STRING",
                        "description": "The vehicle model name (e.g. Brezza, Swift, Baleno, Dzire)",
                    },
                    "overtime_hours": {
                        "type": "NUMBER",
                        "description": "Number of overtime hours (if discussed)",
                    }
                }
            elif tool_name == "inventory_tool":
                properties = {
                    "vehicle": {
                        "type": "STRING",
                        "description": "The vehicle model name (e.g. Brezza, Swift, Baleno, Dzire)",
                    }
                }
            elif tool_name == "supplier_tool":
                properties = {
                    "component": {
                        "type": "STRING",
                        "description": "The component name or vehicle name to check supplier capacity for",
                    }
                }
            elif tool_name == "search_tool":
                properties = {
                    "search_query": {
                        "type": "STRING",
                        "description": "The exact web search query to look up on DuckDuckGo (e.g. 'Brezza sales data 2026' or 'Maruti Suzuki latest component shortages')",
                    }
                }
            elif tool_name == "load_skill_tool":
                properties = {
                    "skill_name": {
                        "type": "STRING",
                        "description": "The name of the skill to load (available: production_analyst, financial_analyst)",
                    }
                }
                required = ["skill_name"]
            
            declarations.append(
                types.FunctionDeclaration(
                    name=tool_name,
                    description=tool_meta.get("description", ""),
                    parameters={
                        "type": "OBJECT",
                        "properties": properties,
                        "required": required,
                    },
                )
            )
        return declarations

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the task-decomposed execution plan using turn-based tool calling.

        Args:
            state: The current shared AgentState dictionary.

        Returns:
            A dictionary updating plan tasks, completed/failed trackers, tool outputs, and context.
        """
        query = state.get("query", "")
        available_tools = list(state.get("available_tools", []))
        if not any(t.get("name") == "load_skill_tool" for t in available_tools):
            try:
                skill_tool = self.registry.get_tool("load_skill_tool")
                available_tools.append(skill_tool.get_metadata())
            except Exception:
                pass
        conversation_history = state.get("conversation_history", [])

        execution_plan_dict = state.get("execution_plan")
        if not execution_plan_dict:
            logger.warning("No execution plan found in state. Mocking single default task for query.")
            execution_plan_dict = {
                "goal": query,
                "planner_reasoning": "Fallback execution without query planner.",
                "tasks": [
                    {
                        "id": "task_1",
                        "title": "Execute User Request",
                        "sub_query": query,
                        "priority": 1,
                        "status": "pending",
                        "depends_on": [],
                        "required_context": [],
                        "expected_output": "Raw metrics collected for user request."
                    }
                ]
            }

        # Deserialize using Task and ExecutionPlan
        from framework.state.state import ExecutionPlan
        try:
            plan = ExecutionPlan.model_validate(execution_plan_dict)
        except Exception as e:
            logger.error("Failed to validate execution plan from state", error=str(e))
            raise LLMError("Invalid execution plan format in state.") from e

        # Initialize tracking lists in state
        completed_tasks = list(state.get("completed_tasks", []))
        failed_tasks = list(state.get("failed_tasks", []))
        task_results = dict(state.get("task_results", {}))
        tool_outputs = dict(state.get("tool_outputs", {}))
        selected_tools = list(state.get("selected_tools", []))
        execution_trace = list(state.get("execution_trace", []))
        context = dict(state.get("context", {}))
        diagnostics = dict(state.get("diagnostics", {}))

        # Sort tasks by priority
        sorted_tasks = sorted(plan.tasks, key=lambda t: t.priority)

        for task in sorted_tasks:
            # Check dependencies
            dependency_failed = False
            for dep_id in task.depends_on:
                if dep_id in failed_tasks:
                    dependency_failed = True
                    break
                if dep_id not in completed_tasks:
                    dependency_failed = True
                    break

            if dependency_failed:
                logger.warning("Skipping task due to dependency failure", task_id=task.id, depends_on=task.depends_on)
                task.status = "failed"
                import json
                task.result = json.dumps({"error": f"Dependency check failed. Preceding task(s) failed or not completed."})
                failed_tasks.append(task.id)
                task_results[task.id] = task.result
                continue

            # Skip if already run
            if task.status in ("completed", "failed"):
                continue

            # Start executing task
            logger.info("Executing task", task_id=task.id, title=task.title)
            task.status = "running"
            state["current_task"] = task.id

            # Construct task-specific prompt
            task_prompt = (
                f"You are executing the following specific task in the execution plan:\n"
                f"Task ID: {task.id}\n"
                f"Task Title: {task.title}\n"
                f"Task Sub-Query: {task.sub_query}\n"
                f"Expected Output: {task.expected_output}\n\n"
                f"STRICT INSTRUCTION: Only execute tools that are directly required to solve this specific sub-query. "
                f"Do not invoke search tools if this task does not require web search. "
                f"Do not invoke capacity/cost/inventory tools if this task is only a search task. "
                f"Do not try to solve other tasks."
            )
            
            # Inject preceding task results
            if task_results:
                task_prompt += "\n\nResults of previously executed tasks:\n"
                for prev_id, prev_res in task_results.items():
                    task_prompt += f"- Task {prev_id} Result: {prev_res}\n"

            # Re-build system instruction dynamically with updated context
            context_str = "\n".join(f"  - {k}: {v}" for k, v in context.items()) if context else "No active context variables."
            system_instruction = ORCHESTRATOR_SYSTEM_INSTRUCTION.format(context_variables=context_str)

            # Build Gemini tool declarations
            function_declarations = self._build_function_declarations(available_tools)
            gemini_tools = [types.Tool(function_declarations=function_declarations)] if function_declarations else []

            # Prepare conversation contents for this specific task.
            # We pass only the task-prompt as the user request rather than the entire
            # mixed conversation history. This ensures the ReAct loop is focused on the current task's
            # objectives and naturally invokes the correct tools, without hardcoding any filtering.
            contents = [
                types.Content(role="user", parts=[types.Part(text=task_prompt)])
            ]

            max_turns = 5
            task_tool_outputs = {}
            task_execution_failed = False

            try:
                for turn in range(max_turns):
                    logger.debug("Native Orchestrator turn for task", task_id=task.id, turn=turn + 1)

                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=gemini_tools,
                        temperature=0.0,
                    )
                    
                    # API execution loop with 429 rate limit handling
                    max_retries = 3
                    response = None
                    import time as _t
                    _llm_t0 = _t.perf_counter()
                    for retry in range(max_retries):
                        try:
                            response = self.client.client.models.generate_content(
                                model=self.client.default_model,
                                contents=contents,
                                config=config,
                            )
                            break
                        except APIError as e:
                            if e.code == 429:
                                import time
                                wait_seconds = 10.0
                                if "retry in" in str(e).lower():
                                    try:
                                        parts = str(e).lower().split("retry in")
                                        wait_seconds = float(parts[1].split("s")[0].strip()) + 1.0
                                    except:
                                        pass
                                logger.warning(f"Rate limited (429) during task execution. Waiting {wait_seconds:.2f}s...", task_id=task.id, retry=retry + 1)
                                time.sleep(wait_seconds)
                            else:
                                raise e
                    else:
                        raise LLMError("Gemini API calls failed: Exceeded maximum retries due to rate limit (429).")
                    _llm_dur = _t.perf_counter() - _llm_t0
                    llm_calls = list(diagnostics.get("llm_calls", []))
                    llm_calls.append({
                        "type": "llm",
                        "caller": "Orchestrator ReAct",
                        "model": self.client.default_model,
                        "duration_s": round(_llm_dur, 3),
                        "purpose": f"Task {task.id} turn {turn + 1}",
                    })
                    diagnostics["llm_calls"] = llm_calls

                    candidate = response.candidates[0]
                    response_content = candidate.content

                    if not response_content or not response_content.parts:
                        break

                    text_parts = [p.text for p in response_content.parts if p.text is not None]
                    reasoning = " ".join(text_parts).strip() if text_parts else ""

                    function_call_parts = [p for p in response_content.parts if p.function_call is not None]

                    if not function_call_parts:
                        break

                    function_response_parts = []
                    concurrency_mode = context.get("concurrency_mode", "parallel")

                    if concurrency_mode == "sequential":
                        # Sequential execution (original behavior)
                        for part in function_call_parts:
                            fc = part.function_call
                            tool_name = fc.name
                            selected_tools.append(tool_name)
                            logger.info("LLM requested tool execution in task context (sequential)", task_id=task.id, tool_name=tool_name, args=fc.args)

                            fc_args = fc.args or {}
                            # Extract and update context variables
                            if "vehicle" in fc_args:
                                v_name = fc_args["vehicle"]
                                v_pct = fc_args.get("demand_change_pct") or fc_args.get("demand_increase_pct")
                                
                                adjustments = list(context.get("adjustments", []))
                                adj_map = {}
                                for adj in adjustments:
                                    name = adj["vehicle"] if isinstance(adj, dict) else adj.get("vehicle")
                                    pct = adj["demand_change_pct"] if isinstance(adj, dict) else adj.get("demand_change_pct")
                                    if name:
                                        adj_map[name.lower()] = {"vehicle": name, "demand_change_pct": pct}
                                
                                if v_pct is not None:
                                    adj_map[v_name.lower()] = {"vehicle": v_name, "demand_change_pct": float(v_pct)}
                                    context["demand_increase_pct"] = float(v_pct)
                                elif v_name.lower() not in adj_map:
                                    adj_map[v_name.lower()] = {"vehicle": v_name, "demand_change_pct": 0.0}
                                    context["demand_increase_pct"] = 0.0
                                    
                                context["adjustments"] = list(adj_map.values())
                                context["vehicle"] = v_name
                            
                            if "overtime_hours" in fc_args:
                                context["overtime_hours"] = fc_args["overtime_hours"]
                            if "component" in fc_args:
                                context["component"] = fc_args["component"]
                            if "search_query" in fc_args:
                                context["search_query"] = fc_args["search_query"]
                            if "skill_name" in fc_args:
                                context["skill_name"] = fc_args["skill_name"]

                            # Expose current task environment updates
                            state["context"] = context

                            try:
                                tool = self.registry.get_tool(tool_name)
                                import time as _t
                                _tool_t0 = _t.perf_counter()
                                result = tool.execute(state)
                                _tool_dur = _t.perf_counter() - _tool_t0
                                task_tool_outputs[tool_name] = result
                                tool_outputs[tool_name] = result
                                status = "success"
                                logger.info("Tool executed successfully inside task (sequential)", task_id=task.id, tool_name=tool_name)
                                # Record tool timing in diagnostics (parallel=False)
                                tool_execs = list(diagnostics.get("tool_executions", []))
                                tool_execs.append({"tool": tool_name, "duration_s": round(_tool_dur, 3), "status": status, "task_id": task.id, "parallel": False})
                                diagnostics["tool_executions"] = tool_execs
                            except Exception as e:
                                result = {"status": "error", "message": str(e)}
                                task_tool_outputs[tool_name] = result
                                tool_outputs[tool_name] = result
                                status = "error"
                                logger.error("Tool execution failed inside task (sequential)", task_id=task.id, tool_name=tool_name, error=str(e))
                                tool_execs = list(diagnostics.get("tool_executions", []))
                                tool_execs.append({"tool": tool_name, "duration_s": 0, "status": status, "task_id": task.id, "parallel": False})
                                diagnostics["tool_executions"] = tool_execs

                            # Log to trace
                            trace_entry = {
                                "node": "orchestrator",
                                "action": f"Task {task.id} Executed tool: {tool_name}",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "metadata": {
                                    "task_id": task.id,
                                    "tool_name": tool_name,
                                    "status": status,
                                    **result
                                },
                            }
                            if reasoning:
                                trace_entry["metadata"]["reasoning"] = reasoning
                            execution_trace.append(trace_entry)

                            function_response_parts.append(
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        id=fc.id,
                                        name=tool_name,
                                        response=result,
                                    )
                                )
                            )
                    else:
                        # Parallel execution (new behavior)
                        from concurrent.futures import ThreadPoolExecutor
                        with ThreadPoolExecutor() as executor:
                            futures = [
                                executor.submit(self._execute_single_tool, fc.function_call, state, task.id)
                                for fc in function_call_parts
                            ]
                            # Wait for all executions to complete
                            parallel_results = [f.result() for f in futures]
                        
                        # Sequentially process results to merge updates and record traces thread-safely
                        for res in parallel_results:
                            tool_name = res["tool_name"]
                            fc_id = res["fc_id"]
                            fc_args = res["fc_args"]
                            tool_res = res["result"]
                            status = res["status"]
                            dur = res["duration_s"]
                            tool_ctx = res["tool_context"]
                            
                            selected_tools.append(tool_name)
                            task_tool_outputs[tool_name] = tool_res
                            tool_outputs[tool_name] = tool_res
                            
                            # Merge context updates back sequentially
                            for key, val in tool_ctx.items():
                                if key == "adjustments":
                                    # Thread-safe merge of adjustments
                                    adj_map = {a["vehicle"].lower(): a for a in context.get("adjustments", [])}
                                    for a in val:
                                        adj_map[a["vehicle"].lower()] = a
                                    context["adjustments"] = list(adj_map.values())
                                else:
                                    context[key] = val
                            
                            state["context"] = context
                            
                            # Record tool timing in diagnostics
                            tool_execs = list(diagnostics.get("tool_executions", []))
                            tool_execs.append({"tool": tool_name, "duration_s": dur, "status": status, "task_id": task.id, "parallel": True})
                            diagnostics["tool_executions"] = tool_execs
                            
                            # Log to trace
                            trace_entry = {
                                "node": "orchestrator",
                                "action": f"Task {task.id} Executed tool: {tool_name}",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "metadata": {
                                    "task_id": task.id,
                                    "tool_name": tool_name,
                                    "status": status,
                                    **tool_res
                                },
                            }
                            if reasoning:
                                trace_entry["metadata"]["reasoning"] = reasoning
                            execution_trace.append(trace_entry)

                            function_response_parts.append(
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        id=fc_id,
                                        name=tool_name,
                                        response=tool_res,
                                    )
                                )
                            )

                    contents.append(response_content)
                    contents.append(
                        types.Content(role="user", parts=function_response_parts)
                    )

            except Exception as e:
                logger.error("Task execution raised unhandled exception", task_id=task.id, error=str(e))
                task_execution_failed = True
                task.status = "failed"
                import json
                task.result = json.dumps({"error": str(e)})
                failed_tasks.append(task.id)
                task_results[task.id] = task.result

            if not task_execution_failed:
                logger.info("Task completed successfully", task_id=task.id)
                task.status = "completed"
                import json
                task.result = json.dumps(task_tool_outputs)
                completed_tasks.append(task.id)
                task_results[task.id] = task.result

        # Serialize ExecutionPlan back
        updated_plan_dict = plan.model_dump()

        return {
            "execution_plan": updated_plan_dict,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "task_results": task_results,
            "tool_outputs": tool_outputs,
            "selected_tools": list(set(selected_tools)),
            "execution_trace": execution_trace,
            "context": context,
            "current_task": None,
            "diagnostics": diagnostics,
        }
