"""Unit tests for the ValidatorAgent dynamic guardrails loading mechanism.
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from agents.validator_agent import ValidatorAgent, ValidationResult


def test_validator_agent_loads_guardrails(mocker):
    """Verifies that ValidatorAgent loads guardrails from the guardrails folder and appends them to instructions."""
    mock_client = mocker.MagicMock()
    
    # Configure mock return value for the LLM structured check
    expected_result = ValidationResult(
        status="PASSED",
        feedback="All guardrails pass.",
        violations=[]
    )
    mock_client.generate_structured.return_value = expected_result

    agent = ValidatorAgent(mock_client)
    
    # Mock data state
    state = {
        "query": "Is our budget OK?",
        "context": {"budget": 1000},
        "recommendation": "The recommended budget plan is within bounds."
    }

    fake_guardrail = "Rule: Do not exceed $5000 budget."
    
    # Patch Path operations and builtins.open to simulate a markdown guardrails file
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.glob", return_value=[Path("/workspace/guardrails/business_guardrails.md")]), \
         patch("builtins.open", mock_open(read_data=fake_guardrail)):
        
        result = agent.run(state)
        
        # Verify LLM check was triggered
        assert mock_client.generate_structured.called
        
        # Extract the system instruction passed to the LLM
        called_kwargs = mock_client.generate_structured.call_args[1]
        system_instruction = called_kwargs.get("system_instruction", "")
        
        # Verify guardrail content was loaded and appended
        assert "Active System Guardrails" in system_instruction
        assert "business_guardrails.md" in system_instruction
        assert fake_guardrail in system_instruction
        
        # Verify state updates returned
        assert result["validation"]["status"] == "PASSED"
        assert result["validation"]["feedback"] == "All guardrails pass."
        assert len(result["validation"]["violations"]) == 0
