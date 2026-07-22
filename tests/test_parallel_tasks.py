"""Unit tests for NativeOrchestratorAgent parallel task execution scheduling.
"""

import pytest
import time
import threading
from typing import Dict, Any
from unittest.mock import MagicMock

from framework.state.state import Task, create_initial_state
from agents.native_orchestrator_agent import NativeOrchestratorAgent
from framework.registry.tool_registry import ToolRegistry
from google.genai import types


def test_parallel_task_concurrency_overlap(mocker):
    """Verifies that two independent tasks (no dependencies) execute concurrently in parallel threads."""
    mock_client = mocker.MagicMock()
    registry = ToolRegistry()
    orchestrator = NativeOrchestratorAgent(mock_client, registry)

    task_start_times = {}
    task_end_times = {}

    def mock_generate_content(*args, **kwargs):
        # Determine which task is calling by inspecting the prompt in kwargs or args
        contents = kwargs.get("contents") or (args[0] if len(args) > 0 else None)
        prompt = ""
        if contents:
            if isinstance(contents, list) and len(contents) > 0:
                parts = getattr(contents[0], "parts", None)
                if parts and len(parts) > 0:
                    prompt = str(getattr(parts[0], "text", "") or "")
            else:
                prompt = str(contents)
        
        task_id = "unknown"
        if "task_1" in prompt:
            task_id = "task_1"
        elif "task_2" in prompt:
            task_id = "task_2"

        # Record start, sleep, and record end to verify overlap
        task_start_times[task_id] = time.perf_counter()
        time.sleep(0.3)
        task_end_times[task_id] = time.perf_counter()

        # Return a simple mock response to complete task
        resp = MagicMock()
        resp.candidates = [
            MagicMock(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Completed {task_id}")]
                )
            )
        ]
        return resp

    mock_client.client.models.generate_content.side_effect = mock_generate_content

    state = create_initial_state(query="Run both tasks")
    state["available_tools"] = []
    state["execution_plan"] = {
        "goal": "Concurrently run independent tasks",
        "planner_reasoning": "Reasoning",
        "tasks": [
            {
                "id": "task_1",
                "title": "Task 1",
                "sub_query": "Query 1 for task_1",
                "priority": 1,
                "status": "pending",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Out 1"
            },
            {
                "id": "task_2",
                "title": "Task 2",
                "sub_query": "Query 2 for task_2",
                "priority": 2,
                "status": "pending",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Out 2"
            }
        ]
    }

    # Execute orchestrator
    result = orchestrator.run(state)

    # Check that both tasks completed successfully
    assert "task_1" in result["completed_tasks"]
    assert "task_2" in result["completed_tasks"]

    # Verify concurrency overlap:
    # Both tasks must have started before either finished
    assert "task_1" in task_start_times and "task_2" in task_start_times
    assert task_start_times["task_1"] < task_end_times["task_2"]
    assert task_start_times["task_2"] < task_end_times["task_1"]


def test_parallel_task_dependency_serialization(mocker):
    """Verifies that a dependent task (depends on task_1) waits until task_1 completes before execution starts."""
    mock_client = mocker.MagicMock()
    registry = ToolRegistry()
    orchestrator = NativeOrchestratorAgent(mock_client, registry)

    task_start_times = {}
    task_end_times = {}

    def mock_generate_content(*args, **kwargs):
        contents = kwargs.get("contents") or (args[0] if len(args) > 0 else None)
        prompt = ""
        if contents:
            if isinstance(contents, list) and len(contents) > 0:
                parts = getattr(contents[0], "parts", None)
                if parts and len(parts) > 0:
                    prompt = str(getattr(parts[0], "text", "") or "")
            else:
                prompt = str(contents)
        
        task_id = "task_2" if "task_2" in prompt else "task_1"

        task_start_times[task_id] = time.perf_counter()
        time.sleep(0.2)
        task_end_times[task_id] = time.perf_counter()

        resp = MagicMock()
        resp.candidates = [
            MagicMock(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Completed {task_id}")]
                )
            )
        ]
        return resp

    mock_client.client.models.generate_content.side_effect = mock_generate_content

    state = create_initial_state(query="Run dependent tasks")
    state["available_tools"] = []
    state["execution_plan"] = {
        "goal": "Run task_2 only after task_1 completes",
        "planner_reasoning": "Reasoning",
        "tasks": [
            {
                "id": "task_1",
                "title": "Task 1",
                "sub_query": "Query 1 for task_1",
                "priority": 1,
                "status": "pending",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Out 1"
            },
            {
                "id": "task_2",
                "title": "Task 2",
                "sub_query": "Query 2 for task_2",
                "priority": 2,
                "status": "pending",
                "depends_on": ["task_1"],
                "required_context": [],
                "expected_output": "Out 2"
            }
        ]
    }

    result = orchestrator.run(state)

    assert "task_1" in result["completed_tasks"]
    assert "task_2" in result["completed_tasks"]

    # Verify task serialization:
    # task_2 must start AFTER task_1 has completely finished
    assert task_start_times["task_2"] >= task_end_times["task_1"]


def test_parallel_task_dependency_failure_propagation(mocker):
    """Verifies that if a prerequisite task fails, the dependent task fails immediately without running."""
    mock_client = mocker.MagicMock()
    registry = ToolRegistry()
    orchestrator = NativeOrchestratorAgent(mock_client, registry)

    task_run_count = {"task_1": 0, "task_2": 0}

    def mock_generate_content(*args, **kwargs):
        contents = kwargs.get("contents") or (args[0] if len(args) > 0 else None)
        prompt = ""
        if contents:
            if isinstance(contents, list) and len(contents) > 0:
                parts = getattr(contents[0], "parts", None)
                if parts and len(parts) > 0:
                    prompt = str(getattr(parts[0], "text", "") or "")
            else:
                prompt = str(contents)
        
        task_id = "task_2" if "task_2" in prompt else "task_1"
        task_run_count[task_id] += 1

        if task_id == "task_1":
            # Simulate failure in task_1
            raise ValueError("Task 1 execution failure.")
            
        resp = MagicMock()
        resp.candidates = [
            MagicMock(
                content=types.Content(role="model", parts=[types.Part(text="Done")])
            )
        ]
        return resp

    mock_client.client.models.generate_content.side_effect = mock_generate_content

    state = create_initial_state(query="Failure cascade test")
    state["available_tools"] = []
    state["execution_plan"] = {
        "goal": "Verify failure cascade",
        "planner_reasoning": "Reasoning",
        "tasks": [
            {
                "id": "task_1",
                "title": "Task 1",
                "sub_query": "Query 1",
                "priority": 1,
                "status": "pending",
                "depends_on": [],
                "required_context": [],
                "expected_output": "Out 1"
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

    result = orchestrator.run(state)

    # task_1 and task_2 should both be marked failed
    assert "task_1" in result["failed_tasks"]
    assert "task_2" in result["failed_tasks"]

    # task_1 was run once (and failed)
    assert task_run_count["task_1"] == 1
    # task_2 was never run/entered because its prerequisite task_1 failed
    assert task_run_count["task_2"] == 0
    
    assert "Dependency check failed" in result["task_results"]["task_2"]
