"""Unit tests for the LoadSkillTool and skills architecture in framework.
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, mock_open

from tools.load_skill_tool import LoadSkillTool
from framework.registry.tool_registry import ToolRegistry


def test_load_skill_tool_registration():
    """Verifies that LoadSkillTool registers correctly and exposes metadata."""
    registry = ToolRegistry()
    registry.register(LoadSkillTool)
    
    tool = registry.get_tool("load_skill_tool")
    assert isinstance(tool, LoadSkillTool)
    
    metadata = tool.get_metadata()
    assert metadata["name"] == "load_skill_tool"
    assert "expert_skills" in metadata["category"]
    assert "skills" in metadata["tags"]


def test_load_skill_tool_missing_name():
    """Asserts that executing the tool without a skill_name in context returns an error."""
    tool = LoadSkillTool()
    state = {
        "context": {}
    }
    result = tool.execute(state)
    assert result["status"] == "error"
    assert "No skill_name was specified" in result["message"]
    assert "production_analyst" in result["available_skills"]


def test_load_skill_tool_invalid_name():
    """Asserts that executing the tool with an invalid skill_name returns an error."""
    tool = LoadSkillTool()
    state = {
        "context": {
            "skill_name": "quantum_physics"
        }
    }
    result = tool.execute(state)
    assert result["status"] == "error"
    assert "not recognized" in result["message"]
    assert "production_analyst" in result["available_skills"]


def test_load_skill_tool_success():
    """Asserts that executing the tool with a valid skill_name successfully loads it."""
    tool = LoadSkillTool()
    state = {
        "context": {
            "skill_name": "production_analyst"
        }
    }
    
    # Mocking file read since skills/production_analyst.md exists
    # but we want to assert exactly what is returned and stored in context
    fake_prompt = "You are the Production Analyst."
    
    with patch("builtins.open", mock_open(read_data=fake_prompt)), \
         patch("pathlib.Path.exists", return_value=True):
        
        result = tool.execute(state)
        
        assert result["status"] == "success"
        assert result["skill_name"] == "production_analyst"
        assert result["prompt"] == fake_prompt
        assert "loaded_skills" in state["context"]
        assert state["context"]["loaded_skills"]["production_analyst"] == fake_prompt
