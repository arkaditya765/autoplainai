"""Unit tests for the framework framework core components.

Tests registry registration, execution trace operations, memory context,
and custom exception handling.
"""

import pytest
from typing import Dict, Any

from framework.registry.tool_registry import BaseTool, ToolRegistry
from framework.workflow.executor import ToolExecutor
from framework.context.context_manager import ContextManager
from framework.utils.exceptions import ToolNotFoundError, ToolExecutionError


# =====================================================================
# Dummy Tool for Testing Registry and Executor
# =====================================================================
class DummyTool(BaseTool):
    name = "dummy_tool"
    description = "A simple tool that returns double the input value from context."
    version = "1.0.0"
    category = "testing"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        context = state.get("context", {})
        val = context.get("input_val", 0)
        return {"result": val * 2}


# =====================================================================
# Registry Tests
# =====================================================================
def test_tool_registration():
    """Verifies that a tool subclassing BaseTool registers correctly and exposes metadata."""
    registry = ToolRegistry()
    registry.register(DummyTool)
    
    # Check tool retrieval
    tool = registry.get_tool("dummy_tool")
    assert isinstance(tool, DummyTool)
    
    # Check metadata properties
    metadata = tool.get_metadata()
    assert metadata["name"] == "dummy_tool"
    assert metadata["category"] == "testing"
    assert metadata["version"] == "1.0.0"
    
    # Check listed tools
    all_tools = registry.list_tools()
    assert len(all_tools) == 1
    assert all_tools[0].name == "dummy_tool"


def test_registry_missing_tool():
    """Asserts that trying to fetch a missing tool raises ToolNotFoundError."""
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get_tool("non_existent_tool")


# =====================================================================
# Executor Tests
# =====================================================================
def test_executor_parallel_execution():
    """Verifies that the ToolExecutor executes selected tools in parallel and logs trace steps."""
    registry = ToolRegistry()
    registry.register(DummyTool)
    executor = ToolExecutor(registry)

    # Prepare input state
    state = {
        "selected_tools": ["dummy_tool"],
        "context": {"input_val": 5},
        "tool_outputs": {},
        "execution_trace": []
    }

    # Execute tools
    result_update = executor.execute_selected(state)
    
    # Verify outputs are updated
    outputs = result_update["tool_outputs"]
    assert "dummy_tool" in outputs
    assert outputs["dummy_tool"] == {"result": 10}

    # Verify execution trace is recorded
    trace = result_update["execution_trace"]
    assert len(trace) == 1
    assert trace[0]["node"] == "executor"
    assert "dummy_tool" in trace[0]["action"]
    assert trace[0]["metadata"]["status"] == "success"


def test_executor_execution_error():
    """Ensures that tool execution failures raise ToolExecutionError and write trace failures."""
    class BadTool(BaseTool):
        name = "bad_tool"
        description = "Throws an error."
        def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
            raise ValueError("Something went wrong!")

    registry = ToolRegistry()
    registry.register(BadTool)
    executor = ToolExecutor(registry)

    state = {
        "selected_tools": ["bad_tool"],
        "context": {},
        "tool_outputs": {},
        "execution_trace": []
    }

    with pytest.raises(ToolExecutionError):
        executor.execute_selected(state)


# =====================================================================
# Context Manager Tests
# =====================================================================
def test_context_manager_memory_aggregation():
    """Verifies conversational memory variables aggregation and message history limits."""
    cm = ContextManager(max_history_turns=2)

    # Test variable tracking
    cm.update_variables({"vehicle": "Brezza", "demand": 100})
    assert cm.get_variables() == {"vehicle": "Brezza", "demand": 100}

    # Test merging variables (should overwrite same, preserve others)
    cm.update_variables({"demand": 125, "overtime": True})
    assert cm.get_variables() == {"vehicle": "Brezza", "demand": 125, "overtime": True}

    # Test message history
    cm.add_message("user", "Hello")
    cm.add_message("assistant", "Hi there")
    assert len(cm.get_history()) == 2
    assert cm.get_history()[0]["role"] == "user"

    # Test history limits capping (max_turns=2, so max 4 messages)
    cm.add_message("user", "Query 1")
    cm.add_message("assistant", "Response 1")
    cm.add_message("user", "Query 2")
    cm.add_message("assistant", "Response 2")
    
    # Should cap history to the last 4 items (2 turns)
    assert len(cm.get_history()) == 4
    assert cm.get_history()[0]["content"] == "Query 1"
    assert cm.get_history()[-1]["content"] == "Response 2"


# =====================================================================
# Retriever Tests
# =====================================================================
def test_tool_retriever(mocker):
    """Verifies that the ToolRetriever correctly indexes tools and retrieves them by embedding similarity."""
    # 1. Create a dummy registry and register tools
    registry = ToolRegistry()
    registry.register(DummyTool)
    
    class UnrelatedTool(BaseTool):
        name = "unrelated_tool"
        description = "This tool is about checking the weather and movie reviews."
        version = "1.0.0"
        category = "testing"

        def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
            return {}

    registry.register(UnrelatedTool)

    # 2. Mock GeminiClient
    mock_client = mocker.MagicMock()
    
    # Define what the mocked .embed() should return.
    # To make similarity calculations predictable:
    # Let "dummy_tool" embed to: [1.0, 0.0]
    # Let "unrelated_tool" embed to: [0.0, 1.0]
    # Let Query matching dummy_tool embed to: [0.9, 0.1]
    # Let Query matching unrelated_tool embed to: [0.1, 0.9]
    def mock_embed(text, model="text-embedding-004"):
        if "dummy_tool" in text:
            return [1.0, 0.0]
        elif "unrelated_tool" in text:
            return [0.0, 1.0]
        elif "calculate" in text or "double" in text:
            return [0.9, 0.1]
        elif "weather" in text:
            return [0.1, 0.9]
        return [0.5, 0.5]

    mock_client.embed.side_effect = mock_embed

    # 3. Instantiate Retriever
    from framework.registry.retriever import ToolRetriever
    retriever = ToolRetriever(mock_client, registry)
    
    # Build index
    retriever.build_index()
    
    # 4. Assert indexing call count
    assert mock_client.embed.call_count == 2
    
    # 5. Retrieve for query matching dummy_tool
    results_dummy = retriever.retrieve("calculate or double this input", top_k=1)
    assert len(results_dummy) == 1
    assert results_dummy[0]["name"] == "dummy_tool"

    # 6. Retrieve for query matching unrelated_tool
    results_unrelated = retriever.retrieve("tell me the weather forecast", top_k=1)
    assert len(results_unrelated) == 1
    assert results_unrelated[0]["name"] == "unrelated_tool"
