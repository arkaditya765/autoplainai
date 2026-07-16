"""Unit tests for RouterAgent and ChatbotAgent in framework.
"""

import pytest
from agents.router_agent import RouterAgent, RouteDecision
from agents.chatbot_agent import ChatbotAgent
from framework.state.state import create_initial_state

def test_router_agent_planning(mocker):
    """Verifies that RouterAgent routes manufacturing queries to 'planning'."""
    mock_client = mocker.MagicMock()
    
    # Configure mock to return a planning classification
    mock_client.generate_structured.return_value = RouteDecision(
        category="planning",
        reason="Query is about Baleno demand increase capacity."
    )
    
    agent = RouterAgent(mock_client)
    state = create_initial_state("Can we increase Baleno production by 20%?")
    
    result = agent.run(state)
    assert result["route_decision"] == "planning"
    mock_client.generate_structured.assert_called_once()


def test_router_agent_general(mocker):
    """Verifies that RouterAgent routes non-manufacturing queries to 'general'."""
    mock_client = mocker.MagicMock()
    
    # Configure mock to return a general chatbot classification
    mock_client.generate_structured.return_value = RouteDecision(
        category="general",
        reason="Query is about the Prime Minister of India."
    )
    
    agent = RouterAgent(mock_client)
    state = create_initial_state("who is the prime minister of india")
    
    result = agent.run(state)
    assert result["route_decision"] == "general"
    mock_client.generate_structured.assert_called_once()


def test_chatbot_agent_response(mocker):
    """Verifies that ChatbotAgent generates direct responses for general queries."""
    mock_client = mocker.MagicMock()
    mock_registry = mocker.MagicMock()
    
    # Configure tool metadata mock
    mock_tool = mocker.MagicMock()
    mock_tool.get_metadata.return_value = {"name": "search_tool", "description": "Search tool."}
    mock_registry.get_tool.return_value = mock_tool

    # Mock model response structure
    mock_response = mocker.MagicMock()
    mock_candidate = mocker.MagicMock()
    mock_content = mocker.MagicMock()
    
    # Text part return
    mock_content.parts = [mocker.MagicMock(text="Narendra Modi is the Prime Minister of India.", function_call=None)]
    mock_candidate.content = mock_content
    mock_response.candidates = [mock_candidate]
    
    mock_client.client.models.generate_content.return_value = mock_response
    mock_client.default_model = "gemini-lite"

    agent = ChatbotAgent(mock_client, mock_registry)
    state = create_initial_state("who is the prime minister of india")
    state["route_decision"] = "general"
    
    result = agent.run(state)
    assert result["recommendation"] == "Narendra Modi is the Prime Minister of India."
    assert len(result["execution_trace"]) == 1
    assert result["execution_trace"][0]["node"] == "chatbot"
    assert "conversational response" in result["execution_trace"][0]["action"]
    mock_client.client.models.generate_content.assert_called_once()


def test_chatbot_agent_tool_use(mocker):
    """Verifies that ChatbotAgent executes tool calls when requested by Gemini."""
    mock_client = mocker.MagicMock()
    mock_registry = mocker.MagicMock()
    
    # Mock search tool
    mock_search_tool = mocker.MagicMock()
    mock_search_tool.get_metadata.return_value = {"name": "search_tool", "description": "Search."}
    mock_search_tool.execute.return_value = {"status": "success", "results": [{"title": "News", "body": "Modi is PM"}]}
    
    mock_registry.get_tool.return_value = mock_search_tool

    # Turn 1: LLM outputs a function call
    mock_response_1 = mocker.MagicMock()
    mock_candidate_1 = mocker.MagicMock()
    mock_content_1 = mocker.MagicMock()
    
    mock_fc = mocker.MagicMock()
    mock_fc.name = "search_tool"
    mock_fc.args = {"search_query": "prime minister of india"}
    mock_fc.id = "call_123"
    
    mock_content_1.parts = [mocker.MagicMock(text=None, function_call=mock_fc)]
    mock_candidate_1.content = mock_content_1
    mock_response_1.candidates = [mock_candidate_1]

    # Turn 2: LLM outputs final answer text after receiving tool response
    mock_response_2 = mocker.MagicMock()
    mock_candidate_2 = mocker.MagicMock()
    mock_content_2 = mocker.MagicMock()
    mock_content_2.parts = [mocker.MagicMock(text="Narendra Modi.", function_call=None)]
    mock_candidate_2.content = mock_content_2
    mock_response_2.candidates = [mock_candidate_2]

    # Set side effect for generate_content
    mock_client.client.models.generate_content.side_effect = [mock_response_1, mock_response_2]
    mock_client.default_model = "gemini-lite"

    agent = ChatbotAgent(mock_client, mock_registry)
    state = create_initial_state("who is the prime minister of india")
    state["route_decision"] = "general"

    result = agent.run(state)
    assert result["recommendation"] == "Narendra Modi."
    
    # Verification of executions
    assert len(result["execution_trace"]) == 2  # 1 for tool call, 1 for final response
    assert result["execution_trace"][0]["action"] == "Called tool 'search_tool' with args {'search_query': 'prime minister of india'}."
    assert result["execution_trace"][1]["action"] == "Generated conversational response."
    
    mock_search_tool.execute.assert_called_once()
