"""Unit tests for PDFSearchTool.

Verifies correct text parsing, semantic lookup mocking, and similarity scoring calculations.
"""

import pytest
from unittest.mock import MagicMock
from tools.pdf_search_tool import PDFSearchTool


def test_pdf_search_tool_metadata():
    """Verifies that PDFSearchTool has the correct metadata configured."""
    tool = PDFSearchTool()
    metadata = tool.get_metadata()
    assert metadata["name"] == "pdf_search_tool"
    assert "safety manual" in tool.description.lower()
    assert "document_search" in metadata["category"]
    assert "safety" in metadata["tags"]


def test_pdf_search_tool_execution(mocker):
    """Verifies that PDFSearchTool parses the PDF, calculates cosine similarity, and returns ranked matches."""
    # Mock GeminiClient instance inside pdf_search_tool
    mock_client = mocker.MagicMock()
    mocker.patch("tools.pdf_search_tool.GeminiClient", return_value=mock_client)

    # Define mock embeddings behavior to yield predictable cosine similarities
    # Speed Limit chunk: [1.0, 0.0, 0.0]
    # PPE Gear chunk:    [0.0, 1.0, 0.0]
    # Audits chunk:      [0.0, 0.0, 1.0]
    def mock_embed(text, *args, **kwargs):
        t = text.lower()
        if "speed" in t:
            return [1.0, 0.0, 0.0]
        elif "wear" in t or "ppe" in t:
            return [0.0, 1.0, 0.0]
        else:
            return [0.0, 0.0, 1.0]

    mock_client.embed.side_effect = mock_embed

    tool = PDFSearchTool()
    
    # 1. Test querying for Speed Limit (should rank Speed Limit chunk #1)
    state = {
        "query": "What is the speed limit?",
        "context": {
            "search_query": "What is the speed limit?"
        }
    }
    result = tool.execute(state)
    assert result["status"] == "success"
    assert len(result["matches"]) == 2
    assert "Speed Limit" in result["matches"][0]["text"]
    assert result["matches"][0]["similarity_score"] > 0.9

    # 2. Test querying for PPE gear (should rank PPE Gear chunk #1)
    state_ppe = {
        "query": "PPE clothing requirements",
        "context": {
            "search_query": "PPE clothing requirements"
        }
    }
    result_ppe = tool.execute(state_ppe)
    assert result_ppe["status"] == "success"
    assert "PPE" in result_ppe["matches"][0]["text"]
    assert result_ppe["matches"][0]["similarity_score"] > 0.9
