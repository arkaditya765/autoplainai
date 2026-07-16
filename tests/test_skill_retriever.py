"""Unit tests for the SkillRetriever and semantic skill selection fallback.
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import numpy as np

from framework.registry.retriever import SkillRetriever
from tools.load_skill_tool import LoadSkillTool


def test_skill_retriever_parsing():
    """Verifies that YAML front-matter metadata is parsed correctly."""
    mock_client = MagicMock()
    retriever = SkillRetriever(mock_client)
    
    content_with_yaml = """---
name: production_analyst
description: Capacity limits check.
---
# Action Plan"""
    
    meta = retriever._parse_yaml_metadata(content_with_yaml)
    assert meta["name"] == "production_analyst"
    assert meta["description"] == "Capacity limits check."
    
    content_without_yaml = "# Title\nNo yaml here."
    meta_empty = retriever._parse_yaml_metadata(content_without_yaml)
    assert meta_empty == {}


def test_skill_retriever_indexing_and_retrieval(mocker):
    """Verifies indexing skills from directory and retrieving them semantically."""
    mock_client = mocker.MagicMock()
    
    # Mocking client embed calls
    # 1. During index building for skill (dimension 3 vector)
    # 2. During query retrieval
    mock_client.embed.side_effect = [
        [0.1, 0.2, 0.3],  # skill 1 vector
        [0.4, 0.5, 0.6],  # skill 2 vector
        [0.1, 0.2, 0.3],  # query vector matching skill 1
    ]
    
    # Instantiate retriever
    retriever = SkillRetriever(mock_client, skills_dir="/fake/skills")
    
    # Mock file reading and globbing in skills_dir
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("pathlib.Path.glob", return_value=[
        Path("/fake/skills/production_analyst.md"),
        Path("/fake/skills/financial_analyst.md")
    ])
    
    # Mock reading file content
    fake_content_1 = "---\nname: production_analyst\ndescription: capacity check\n---\ncontent 1"
    fake_content_2 = "---\nname: financial_analyst\ndescription: cost check\n---\ncontent 2"
    
    # Side effects for open()
    mocker.patch("builtins.open", mock_open())
    mocker.patch("builtins.open", side_effect=[
        mock_open(read_data=fake_content_1).return_value,
        mock_open(read_data=fake_content_2).return_value
    ])
    
    # Build vector index
    retriever.build_index()
    assert len(retriever._skill_embeddings) == 2
    assert retriever._skill_embeddings[0]["name"] == "production_analyst"
    assert retriever._skill_embeddings[1]["name"] == "financial_analyst"
    
    # Retrieve
    matches = retriever.retrieve("Check line utilization limits", top_k=1)
    assert len(matches) == 1
    assert matches[0]["name"] == "production_analyst"
    assert matches[0]["similarity_score"] > 0.99  # Identical vector


def test_load_skill_tool_semantic_fallback(mocker):
    """Verifies that LoadSkillTool uses SkillRetriever as fallback for unknown skills."""
    tool = LoadSkillTool()
    
    # State with unrecognized skill_name
    state = {
        "query": "Check assembly overload limits",
        "context": {
            "skill_name": "overload metrics analyst"
        }
    }
    
    # Mock SkillRetriever retrieval
    mock_retriever = mocker.MagicMock()
    mock_retriever.retrieve.return_value = [
        {
            "name": "production_analyst",
            "similarity_score": 0.85,
            "content": "Specialized production analyst guidelines."
        }
    ]
    
    mocker.patch("framework.registry.retriever.SkillRetriever", return_value=mock_retriever)
    
    # Mock file system open for loading the matching skill
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data="Specialized production analyst guidelines."))
    
    result = tool.execute(state)
    
    # Assert successful resolution and load
    assert result["status"] == "success"
    assert result["skill_name"] == "production_analyst"
    assert result["prompt"] == "Specialized production analyst guidelines."
