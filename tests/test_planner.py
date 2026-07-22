"""Unit tests for QueryPlannerAgent and NativeOrchestratorAgent task decomposition.

Verifies plan generation, sequential task execution, dependency checks, and error isolation.
"""

import pytest
from typing import Dict, Any

from framework.state.state import AgentState, Task, ExecutionPlan, create_initial_state
from agents.query_planner import QueryPlannerAgent
from agents.native_orchestrator_agent import NativeOrchestratorAgent
from framework.registry.tool_registry import BaseTool, ToolRegistry
from google.genai import types


# =====================================================================
# Dummy Tool for Testing Orchestration
# =====================================================================
class SimpleTestTool(BaseTool):
    name = "capacity_tool"
    description = "Test capacity tool."
    version = "1.0.0"
    category = "testing"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"capacity_utilization": 78.5}


# =====================================================================
# Query Planner Tests
# =====================================================================
def test_query_planner_generation(mocker):
    """Verifies that the QueryPlannerAgent constructs structured plans using Gemini generate_structured."""
    mock_client = mocker.MagicMock()

    # Pre-configure the mock ExecutionPlan to return
    expected_plan = ExecutionPlan(
        goal="Evaluate production feasibility.",
        planner_reasoning="Decomposed into capacity check and supplier check.",
        tasks=[
            Task(
                id="task_1",
                title="Capacity Check",
                sub_query="Check assembly line capacity.",
                priority=1,
                status="pending",
                depends_on=[],
                required_context=[],
                expected_output="Capacity utilization metric."
            ),
            Task(
                id="task_2",
                title="Supplier Check",
                sub_query="Check tyre supplier limits.",
                priority=2,
                status="pending",
                depends_on=["task_1"],
                required_context=[],
                expected_output="Supplier feasibility status."
            )
        ]
    )
    mock_client.generate_structured.return_value = expected_plan

    planner = QueryPlannerAgent(mock_client)
    state = create_initial_state(query="Can we make 25% more cars?")

    # Run planner node
    planner_result = planner.run(state)

    # Check updates to state
    assert "execution_plan" in planner_result
    assert planner_result["planner_reasoning"] == "Decomposed into capacity check and supplier check."
    assert len(planner_result["execution_plan"]["tasks"]) == 2
    assert planner_result["execution_plan"]["tasks"][0]["id"] == "task_1"
    assert planner_result["execution_plan"]["tasks"][1]["depends_on"] == ["task_1"]


# =====================================================================
# Orchestrator Task Execution and Dependencies Tests
# =====================================================================
def test_orchestrator_dependency_skip(mocker):
    """Asserts that the orchestrator skips/fails tasks whose parent dependencies failed."""
    mock_client = mocker.MagicMock()
    registry = ToolRegistry()

    orchestrator = NativeOrchestratorAgent(mock_client, registry)

    # Build plan where task_2 depends on task_1, and task_1 has failed
    state = create_initial_state(query="Test query")
    state["failed_tasks"] = ["task_1"]
    state["execution_plan"] = {
        "goal": "Test goal",
        "planner_reasoning": "Reasoning",
        "tasks": [
            {
                "id": "task_1",
                "title": "Task 1",
                "sub_query": "Query 1",
                "priority": 1,
                "status": "failed",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Out 1",
                "result": "{\"error\": \"Preceding failure\"}"
            },
            {
                "id": "task_2",
                "title": "Task 2",
                "sub_query": "Query 2",
                "priority": 2,
                "status": "pending",
                "depends_on": ["task_1"],
                "required_context": [],
                "expected_output": "Out 2"
            }
        ]
    }

    # Execute Orchestrator
    result = orchestrator.run(state)

    # Assert that task_2 was marked failed and recorded in failed_tasks list
    assert "task_2" in result["failed_tasks"]
    assert result["execution_plan"]["tasks"][1]["status"] == "failed"
    assert "Dependency check failed" in result["task_results"]["task_2"]


def test_orchestrator_success_and_error_isolation(mocker):
    """Verifies that orchestrator handles task failure gracefully, continuing other independent tasks."""
    mock_client = mocker.MagicMock()
    registry = ToolRegistry()
    registry.register(SimpleTestTool)

    # Mock tool call output from LLM for task_1:
    # First turn: Gemini requests capacity_tool call
    # Second turn: Gemini returns final text (no tool calls) to complete task
    mock_response_1 = mocker.MagicMock()
    mock_response_1.candidates = [
        mocker.MagicMock(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text="Calling capacity tool.",
                        function_call=types.FunctionCall(
                            name="capacity_tool",
                            id="fc_1",
                            args={"vehicle": "Brezza", "demand_change_pct": 15.0}
                        )
                    )
                ]
            )
        )
    ]

    mock_response_2 = mocker.MagicMock()
    mock_response_2.candidates = [
        mocker.MagicMock(
            content=types.Content(
                role="model",
                parts=[types.Part(text="Capacity check complete.")]
            )
        )
    ]

    # Side effect for generate_content to simulate ReAct loop for task_1, and raise exception for task_2
    call_count = 0
    def mock_generate_content(*args, **kwargs):
        nonlocal call_count
        contents = kwargs.get("contents") or (args[0] if len(args) > 0 else None)
        prompt_text = ""
        if contents:
            if isinstance(contents, list) and len(contents) > 0:
                parts = getattr(contents[0], "parts", None)
                if parts and len(parts) > 0:
                    prompt_text = str(getattr(parts[0], "text", "") or "")
            else:
                prompt_text = str(contents)

        if "task_2" in prompt_text or "This will fail" in prompt_text:
            # Task 2 raises exception to verify error isolation
            raise ValueError("Simulated LLM Generation Error for Task 2.")
            
        call_count += 1
        if call_count == 1:
            return mock_response_1
        else:
            return mock_response_2

    mock_client.client.models.generate_content.side_effect = mock_generate_content

    orchestrator = NativeOrchestratorAgent(mock_client, registry)

    # Two tasks that are independent (no dependencies)
    state = create_initial_state(query="Test query")
    state["available_tools"] = [SimpleTestTool().get_metadata()]
    state["execution_plan"] = {
        "goal": "Test goal",
        "planner_reasoning": "Reasoning",
        "tasks": [
            {
                "id": "task_1",
                "title": "Capacity Check",
                "sub_query": "Check Brezza capacity.",
                "priority": 1,
                "status": "pending",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Capacity results"
            },
            {
                "id": "task_2",
                "title": "Failing Task",
                "sub_query": "This will fail.",
                "priority": 2,
                "status": "pending",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Fails"
            }
        ]
    }

    # Execute Orchestrator
    result = orchestrator.run(state)

    # Assert Task 1 completed and tool results stored
    assert "task_1" in result["completed_tasks"]
    assert "capacity_tool" in result["tool_outputs"]
    assert result["tool_outputs"]["capacity_tool"]["capacity_utilization"] == 78.5
    assert result["execution_plan"]["tasks"][0]["status"] == "completed"

    # Assert Task 2 failed, recorded in failed list, and error description recorded
    assert "task_2" in result["failed_tasks"]
    assert result["execution_plan"]["tasks"][1]["status"] == "failed"
    assert "Simulated LLM Generation Error" in result["task_results"]["task_2"]
