"""Helper utilities for framework framework.

Includes JSON parsing helper routines and dotenv system config loaders.
"""

import json
import os
import re
from typing import Any, Dict
from dotenv import load_dotenv
from .exceptions import LLMResponseError


def load_environment() -> None:
    """Loads environment variables from a .env file if it exists."""
    load_dotenv()


def clean_json_markdown(text: str) -> str:
    """Removes markdown code blocks around JSON data if they exist.

    For example:
    ```json
    { "key": "value" }
    ```
    becomes:
    { "key": "value" }
    """
    text = text.strip()
    # Pattern to match ```json ... ``` or ``` ... ```
    pattern = r"^```(?:json)?\s*([\s\S]*?)\s*```$"
    match = re.match(pattern, text)
    if match:
        return match.group(1).strip()
    return text


def safe_parse_json(text: str) -> Dict[str, Any]:
    """Cleans markdown syntax and safely parses a string into a dictionary.

    Args:
        text: Raw text response from the LLM.

    Raises:
        LLMResponseError: If the text is not valid JSON.
    """
    cleaned = clean_json_markdown(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMResponseError(
            message=f"Failed to parse text as JSON. Text: {text[:200]}...",
            details={"original_error": str(e), "cleaned_text": cleaned}
        ) from e


def load_prompt(filename: str, default_content: str) -> str:
    """Loads a prompt from the prompts/ directory at the workspace root.
    
    If the file does not exist, returns the default fallback content.
    """
    from pathlib import Path
    
    # Locate workspace root containing 'prompts' folder
    workspace_root = None
    for parent in Path(__file__).resolve().parents:
        if (parent / "prompts").exists():
            workspace_root = parent
            break
    if not workspace_root:
        workspace_root = Path(os.getcwd())
        
    filepath = workspace_root / "prompts" / filename
    try:
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return default_content
